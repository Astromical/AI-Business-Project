"""Tests voor inloggen, accounts en de rechten per rol."""

import sqlite3
from pathlib import Path

import pytest
from conftest import log_in_op_pagina
from streamlit.testing.v1 import AppTest

from src import auth, service
from src.db import OpslaanFout, bewaar_rooster, lees_gebruiker, verbind
from src.models import Gebruiker, Lesuur, Toewijzing

ROOT = Path(__file__).resolve().parent.parent
WACHTWOORD = "geheim-wachtwoord"
PAGINAS = ("1_Gegevens.py", "2_Rooster.py", "3_Mijn_rooster.py", "4_Gebruikers.py")


@pytest.fixture
def pad(tmp_path):
    return str(tmp_path / "rooster.db")


def _pagina(naam):
    return AppTest.from_file(str(ROOT / "paginas" / naam), default_timeout=60)


def _app(pad):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.session_state["pad"] = pad
    return at


def _vul_formulier_in(at, naam, wachtwoord, knop, herhaal=None):
    at.text_input[0].set_value(naam)
    at.text_input[1].set_value(wachtwoord)
    if herhaal is not None:  # alleen bij het aanmaken van het eerste account
        at.text_input[2].set_value(herhaal)
    return next(b for b in at.button if b.label == knop).click().run()


# --- wachtwoorden ---


def test_hash_klopt_alleen_met_het_juiste_wachtwoord():
    opgeslagen = auth.hash_wachtwoord(WACHTWOORD)
    assert WACHTWOORD not in opgeslagen
    assert auth.controleer_wachtwoord(WACHTWOORD, opgeslagen)
    assert not auth.controleer_wachtwoord("iets anders", opgeslagen)


def test_hetzelfde_wachtwoord_geeft_een_andere_hash():
    assert auth.hash_wachtwoord(WACHTWOORD) != auth.hash_wachtwoord(WACHTWOORD)


@pytest.mark.parametrize("onzin", ["", "scrypt$1", "md5$1$1$1$AAAA$AAAA", "scrypt$x$8$1$AAAA$AAAA"])
def test_onleesbare_hash_klopt_nooit(onzin):
    assert not auth.controleer_wachtwoord(WACHTWOORD, onzin)


def test_wachtwoord_staat_niet_leesbaar_in_de_database(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "leraar")
    assert WACHTWOORD.encode() not in Path(pad).read_bytes()


# --- rechten ---


@pytest.mark.parametrize(
    ("rol", "recht", "verwacht"),
    [
        ("roostermaker", "accounts", True),
        ("roostermaker", "demodata", True),
        ("roostermaker", "gegevens", True),
        ("roostermaker", "rooster", True),
        ("leraar", "accounts", False),
        ("leraar", "demodata", False),
        ("beheerder", "rooster", False),  # de rol beheerder bestaat niet meer
        ("leraar", "eigen_rooster", True),
        ("roostermaker", "eigen_rooster", False),
        ("leraar", "rooster", False),
        ("leraar", "gegevens", False),
        ("onbekend", "eigen_rooster", False),
    ],
)
def test_mag(rol, recht, verwacht):
    assert auth.mag(rol, recht) is verwacht


# --- accounts ---


def test_inloggen(pad):
    service.maak_gebruiker(pad, "An", WACHTWOORD, "leraar")
    assert service.log_in(pad, " an ", WACHTWOORD) == Gebruiker("an", "leraar")
    assert service.log_in(pad, "an", "fout wachtwoord") is None
    assert service.log_in(pad, "onbekend", WACHTWOORD) is None


def test_tweede_eerste_roostermaker_wordt_geweigerd(pad):
    service.maak_eerste_roostermaker(pad, "baas", WACHTWOORD)
    with pytest.raises(OpslaanFout, match="al een account"):
        service.maak_eerste_roostermaker(pad, "indringer", WACHTWOORD)
    assert [g.naam for g in service.gebruikers(pad)] == ["baas"]


def test_ongeldige_invoer_wordt_geweigerd(pad):
    with pytest.raises(OpslaanFout, match="minstens"):
        service.maak_gebruiker(pad, "an", "kort", "leraar")
    with pytest.raises(OpslaanFout, match="gebruikersnaam"):
        service.maak_gebruiker(pad, "  ", WACHTWOORD, "leraar")
    service.maak_gebruiker(pad, "an", WACHTWOORD, "leraar")
    with pytest.raises(OpslaanFout, match="bestaat al"):
        service.maak_gebruiker(pad, "AN", WACHTWOORD, "roostermaker")
    assert service.gebruikers(pad) == [Gebruiker("an", "leraar")]


def test_laatste_roostermaker_blijft_bestaan(pad):
    service.maak_eerste_roostermaker(pad, "baas", WACHTWOORD)
    with pytest.raises(OpslaanFout, match="minstens één roostermaker"):
        service.verwijder_gebruiker(pad, "baas")
    with pytest.raises(OpslaanFout, match="minstens één roostermaker"):
        service.wijzig_gebruiker(pad, Gebruiker("baas", "leraar"))
    service.maak_gebruiker(pad, "tweede", WACHTWOORD, "roostermaker")
    service.wijzig_gebruiker(pad, Gebruiker("baas", "leraar"))
    assert service.zoek_gebruiker(pad, "baas").rol == "leraar"
    with pytest.raises(OpslaanFout, match="minstens één roostermaker"):
        service.verwijder_gebruiker(pad, "tweede")


def test_oude_beheerder_wordt_roostermaker(tmp_path):
    pad = tmp_path / "oud.db"
    con = sqlite3.connect(pad)  # een database van vóór het schrappen van de rol beheerder
    con.execute(
        """CREATE TABLE gebruiker (naam TEXT PRIMARY KEY, wachtwoord_hash TEXT NOT NULL,
           rol TEXT NOT NULL CHECK (rol IN ('beheerder','roostermaker','leraar')),
           leraar_id TEXT UNIQUE)"""
    )
    con.execute("INSERT INTO gebruiker VALUES ('baas', ?, 'beheerder', NULL)", (auth.hash_wachtwoord(WACHTWOORD),))
    con.commit()
    con.close()
    assert service.log_in(str(pad), "baas", WACHTWOORD) == Gebruiker("baas", "roostermaker")


def test_nieuw_wachtwoord_vervangt_het_oude(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "leraar")
    service.zet_wachtwoord(pad, "an", "nieuw-wachtwoord")
    assert service.log_in(pad, "an", WACHTWOORD) is None
    assert service.log_in(pad, "an", "nieuw-wachtwoord") is not None


def test_ongeldige_rol_wordt_door_de_database_geweigerd(pad):
    con = service.open_database(pad)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO gebruiker VALUES ('x', 'hash', 'directeur', NULL)")
    con.close()


def test_accounts_overleven_leegmaken_en_voorbeelddata(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    leraar_id = service.laad(pad)[0].leraren[0].id
    service.maak_gebruiker(pad, "an", WACHTWOORD, "leraar", leraar_id)
    service.vul_voorbeeld(pad, "voorbeeld")  # wist de leraren: de koppeling valt weg
    assert service.log_in(pad, "an", WACHTWOORD) == Gebruiker("an", "leraar", None)
    service.maak_leeg(pad)
    assert service.heeft_gebruikers(pad)


def test_bestaande_database_krijgt_de_tabel_gebruiker(pad):
    con = verbind(pad)
    con.execute("CREATE TABLE lokaal (id TEXT PRIMARY KEY, naam TEXT NOT NULL, type TEXT NOT NULL)")
    con.execute("INSERT INTO lokaal VALUES ('R1', 'Lokaal 1', 'regulier')")
    con.commit()
    con.close()
    assert not service.heeft_gebruikers(pad)
    con = verbind(pad)
    assert con.execute("SELECT COUNT(*) FROM lokaal").fetchone()[0] == 1
    assert lees_gebruiker(con, "niemand") is None
    con.close()


# --- pagina's ---


@pytest.mark.parametrize("pagina", PAGINAS)
def test_pagina_weigert_zonder_inloggen(pad, pagina):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = _pagina(pagina)
    at.session_state["pad"] = pad
    at.run()
    assert not at.exception
    assert any("Log eerst in" in w.value for w in at.warning)
    assert not at.button and not at.get("html") and not at.tabs


@pytest.mark.parametrize(
    ("pagina", "rol", "toegelaten"),
    [
        ("1_Gegevens.py", "leraar", False),
        ("1_Gegevens.py", "roostermaker", True),
        ("2_Rooster.py", "leraar", False),
        ("2_Rooster.py", "roostermaker", True),
        ("4_Gebruikers.py", "leraar", False),
        ("4_Gebruikers.py", "roostermaker", True),
    ],
)
def test_pagina_toegang_per_rol(pad, pagina, rol, toegelaten):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = log_in_op_pagina(_pagina(pagina), pad, rol).run()
    assert not at.exception
    geweigerd = any("geen toegang" in e.value for e in at.error)
    assert geweigerd is not toegelaten
    if not toegelaten:  # de pagina stopt vóór de zijbalk en de inhoud
        assert [b.label for b in at.button] == []
        assert not at.get("html") and not at.tabs and not at.dataframe


def test_alleen_de_roostermaker_ziet_de_databaseknoppen(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    leraar = log_in_op_pagina(_pagina("3_Mijn_rooster.py"), pad, "leraar").run()
    labels = [b.label for b in leraar.button]
    assert "Uitloggen" in labels and "Database leegmaken" not in labels
    assert not any(t.label == "Databasepad" for t in leraar.text_input)
    roostermaker = log_in_op_pagina(_pagina("2_Rooster.py"), pad, "roostermaker").run()
    assert "Database leegmaken" in [b.label for b in roostermaker.button]


def test_roostermaker_laadt_een_gekozen_voorbeeld(pad):
    service.maak_eerste_roostermaker(pad, "baas", WACHTWOORD)
    at = log_in_op_pagina(_pagina("2_Rooster.py"), pad, "roostermaker").run()
    at.sidebar.selectbox(key="voorbeeld_variant").set_value("onmogelijk").run()
    at = next(b for b in at.sidebar.button if b.label == "Voorbeeld laden").click().run()
    assert not at.exception
    assert service.aantallen(service.laad(pad)[0])["Klassen"] == 6
    assert any("Onmogelijk rooster geladen" in t.value for t in at.toast)


def test_verwijderd_account_verliest_meteen_de_toegang(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = log_in_op_pagina(_pagina("2_Rooster.py"), pad, "roostermaker").run()
    assert not at.warning
    service.maak_gebruiker(pad, "tweede", WACHTWOORD, "roostermaker")  # de laatste blijft altijd
    service.verwijder_gebruiker(pad, "test_roostermaker")
    at.run()
    assert any("Log eerst in" in w.value for w in at.warning)


def test_gewijzigde_rol_geldt_meteen(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = log_in_op_pagina(_pagina("2_Rooster.py"), pad, "roostermaker").run()
    service.maak_gebruiker(pad, "tweede", WACHTWOORD, "roostermaker")  # de laatste blijft altijd
    service.wijzig_gebruiker(pad, Gebruiker("test_roostermaker", "leraar"))
    at.run()
    assert any("geen toegang" in e.value for e in at.error)


def _vul_rooster_met_twee_leraren(pad):
    """Bewaar één les van elke leraar; geef hun ids en vakken terug."""
    service.vul_voorbeeld(pad, "voorbeeld")
    data, _ = service.laad(pad)
    eerste = data.lessen[0]
    tweede = next(les for les in data.lessen if les.leraar_id != eerste.leraar_id)
    rooster = tuple(
        Toewijzing(Lesuur(les.id, 1, les.vak, les.klas, les.leraar_id, les.lokaaltype), slot.id, lokaal.id)
        for les, slot, lokaal in zip((eerste, tweede), data.tijdslots, data.lokalen)
    )
    con = verbind(pad)
    bewaar_rooster(con, rooster)
    con.close()
    return eerste, tweede


def test_leraar_ziet_alleen_het_eigen_rooster(pad):
    eerste, tweede = _vul_rooster_met_twee_leraren(pad)
    at = log_in_op_pagina(_pagina("3_Mijn_rooster.py"), pad, "leraar", eerste.leraar_id).run()
    assert not at.exception
    assert len(at.get("html")) == 1
    rooster = at.get("html")[0].proto.body
    assert rooster.count('class="les"') == 1  # alleen de eigen les, niet die van de andere leraar
    assert f"<b>{eerste.vak}</b><span>{eerste.klas}</span>" in rooster
    assert tweede.leraar_id != eerste.leraar_id
    assert not [b for b in at.button if b.label != "Uitloggen"]  # alleen bekijken


def test_mijn_rooster_zonder_koppeling_of_rooster(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = log_in_op_pagina(_pagina("3_Mijn_rooster.py"), pad, "leraar").run()
    assert any("geen docent gekoppeld" in i.value for i in at.info)
    leraar_id = service.laad(pad)[0].leraren[0].id
    service.wijzig_gebruiker(pad, Gebruiker("test_leraar", "leraar", leraar_id))
    at.run()
    assert any("nog geen rooster" in i.value for i in at.info)


# --- de hele weg door app.py ---


def test_eerste_start_maakt_een_roostermaker_en_logt_in(pad):
    at = _app(pad).run()
    assert not at.exception
    assert at.title[0].value == "Account aanmaken"
    assert len(at.text_input) == 3  # met "Herhaal het wachtwoord", anders dan inloggen
    at = _vul_formulier_in(at, "Baas", WACHTWOORD, "Account aanmaken", herhaal=WACHTWOORD)
    assert not at.exception  # meteen ingelogd, zonder nog eens in te loggen
    assert at.title[0].value == "Schoolrooster-solver"
    assert at.subheader[0].value == "Roostermaker"  # de rol staat linksboven
    assert not any("Uitloggen" in b.label for b in at.sidebar.button)


def test_kort_wachtwoord_bij_eerste_roostermaker_geeft_melding(pad):
    at = _vul_formulier_in(_app(pad).run(), "baas", "kort", "Account aanmaken", herhaal="kort")
    assert any("minstens" in e.value for e in at.error)
    assert not service.heeft_gebruikers(pad)


def test_fout_wachtwoord_laat_niet_binnen(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "roostermaker")
    at = _vul_formulier_in(_app(pad).run(), "an", "fout wachtwoord", "Inloggen")
    assert any("klopt niet" in e.value for e in at.error)
    assert "gebruiker" not in at.session_state


def test_uitloggen_wist_de_sessie(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "roostermaker")
    at = _vul_formulier_in(_app(pad).run(), "an", WACHTWOORD, "Inloggen")
    at.session_state["berekening"] = "rooster van an"
    at = next(b for b in at.button if b.label == "Uitloggen").click().run()
    assert not at.exception
    assert at.title[0].value == "Inloggen"
    assert "gebruiker" not in at.session_state and "berekening" not in at.session_state


def test_roostermaker_maakt_een_account_op_de_pagina(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = log_in_op_pagina(_pagina("4_Gebruikers.py"), pad, "roostermaker").run()
    assert not at.exception
    velden = {t.label: t for t in at.text_input}
    velden["Gebruikersnaam"].set_value("nieuw")
    velden["Wachtwoord"].set_value(WACHTWOORD)
    at = next(b for b in at.button if b.label == "Account aanmaken").click().run()
    assert not at.exception
    assert service.log_in(pad, "nieuw", WACHTWOORD) == Gebruiker("nieuw", "leraar")


@pytest.mark.parametrize("pagina", ["paginas/1_Gegevens.py", "paginas/2_Rooster.py", "paginas/4_Gebruikers.py"])
def test_leraar_kan_niet_naar_een_verboden_pagina_springen(pad, pagina):
    service.vul_voorbeeld(pad, "voorbeeld")
    service.maak_gebruiker(pad, "an", WACHTWOORD, "leraar")
    at = _vul_formulier_in(_app(pad).run(), "an", WACHTWOORD, "Inloggen")
    with pytest.raises(ValueError, match="Could not find a navigation page"):
        at.switch_page(pagina)


def test_uitgelogde_bezoeker_krijgt_alleen_het_inlogscherm(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "roostermaker")
    at = _app(pad).run()
    assert at.title[0].value == "Inloggen"
    with pytest.raises(ValueError, match="Could not find a navigation page"):
        at.switch_page("paginas/2_Rooster.py")


# --- ingelogd blijven na vernieuwen ---


def test_sessiecode_klopt_alleen_ongewijzigd_en_op_tijd():
    sleutel = b"s" * 32
    code = auth.maak_sessiecode("an", sleutel, nu=1000)
    assert auth.lees_sessiecode(code, sleutel, nu=1000) == "an"
    assert auth.lees_sessiecode(code, b"x" * 32, nu=1000) is None  # andere sleutel
    assert auth.lees_sessiecode(code, sleutel, nu=1000 + auth.SESSIE_DUUR_S + 1) is None  # verlopen
    naam, vervalt, handtekening = code.split(".")
    vervalst = auth.maak_sessiecode("baas", sleutel, nu=1000).split(".")[0]
    assert auth.lees_sessiecode(f"{vervalst}.{vervalt}.{handtekening}", sleutel, nu=1000) is None
    assert auth.lees_sessiecode("onzin", sleutel, nu=1000) is None
    assert auth.lees_sessiecode("a.b.é", sleutel, nu=1000) is None


def test_vernieuwen_houdt_de_gebruiker_ingelogd(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "roostermaker")
    at = _vul_formulier_in(_app(pad).run(), "an", WACHTWOORD, "Inloggen")
    code = at.query_params["sessie"]
    assert code
    vernieuwd = _app(pad)  # nieuwe sessie, zelfde adres
    vernieuwd.query_params["sessie"] = code
    vernieuwd.run()
    assert not vernieuwd.exception
    assert vernieuwd.title[0].value == "Schoolrooster-solver"
    vervalst = _app(pad)
    vervalst.query_params["sessie"] = code[:-2] + "xx"
    assert vervalst.run().title[0].value == "Inloggen"


def test_uitloggen_haalt_de_sessiecode_weg(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "roostermaker")
    at = _vul_formulier_in(_app(pad).run(), "an", WACHTWOORD, "Inloggen")
    at = next(b for b in at.button if b.label == "Uitloggen").click().run()
    assert "sessie" not in at.query_params
    assert at.title[0].value == "Inloggen"


def test_verwijderd_account_kan_niet_terug_met_een_oude_code(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "roostermaker")
    service.maak_gebruiker(pad, "tweede", WACHTWOORD, "roostermaker")
    code = service.maak_sessiecode(pad, "an")
    service.verwijder_gebruiker(pad, "an")
    at = _app(pad)
    at.query_params["sessie"] = code
    assert at.run().title[0].value == "Inloggen"


def test_verschillende_wachtwoorden_maken_geen_account(pad):
    at = _vul_formulier_in(_app(pad).run(), "baas", WACHTWOORD, "Account aanmaken", herhaal="iets-anders-1")
    assert any("niet gelijk" in e.value for e in at.error)
    assert not service.heeft_gebruikers(pad)


def test_inlogscherm_verschilt_van_aanmaken(pad):
    service.maak_gebruiker(pad, "an", WACHTWOORD, "roostermaker")
    at = _app(pad).run()
    assert at.title[0].value == "Inloggen"
    assert len(at.text_input) == 2
    assert [b.label for b in at.button] == ["Inloggen"]


# --- accounts voor alle leraren in een keer ---


def test_accounts_voor_alle_leraren(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    leraren = {l.id for l in service.laad(pad)[0].leraren}
    service.maak_gebruiker(pad, "pee", WACHTWOORD, "leraar", "PEE")  # heeft al een account
    service.maak_gebruiker(pad, "mae", WACHTWOORD, "roostermaker")  # naam bezet, geen koppeling
    assert service.leraren_zonder_account(pad) == len(leraren) - 1
    namen = service.maak_leraaraccounts(pad)
    assert len(namen) == len(leraren) - 1 and "mae-2" in namen  # bezette naam krijgt een volgnummer
    for naam in namen:
        gebruiker = service.log_in(pad, naam, auth.LERAAR_WACHTWOORD)
        assert gebruiker.rol == "leraar" and gebruiker.leraar_id in leraren
    assert service.log_in(pad, "pee", WACHTWOORD) is not None  # bestaand account ongemoeid
    assert service.maak_leraaraccounts(pad) == []  # tweede keer: niets nieuws


def test_knop_maakt_accounts_met_het_gedeelde_wachtwoord(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = log_in_op_pagina(_pagina("4_Gebruikers.py"), pad, "roostermaker").run()
    assert any(auth.LERAAR_WACHTWOORD in m.value for m in at.markdown)
    at = next(b for b in at.button if b.label == "Accounts maken voor alle leraren").click().run()
    assert not at.exception
    assert any(auth.LERAAR_WACHTWOORD in s.value for s in at.success)
    assert service.log_in(pad, "pee", auth.LERAAR_WACHTWOORD) is not None
    assert any("Elke leraar heeft een account" in c.value for c in at.caption)


def test_wachtwoord_van_een_leraar_terugzetten(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    service.maak_gebruiker(pad, "casw", WACHTWOORD, "leraar", "PEE")
    at = log_in_op_pagina(_pagina("4_Gebruikers.py"), pad, "roostermaker").run()
    at.selectbox(key="account_keuze").set_value(next(g for g in service.gebruikers(pad) if g.naam == "casw")).run()
    at = next(b for b in at.button if b.label == f"Terugzetten naar {auth.LERAAR_WACHTWOORD}").click().run()
    assert not at.exception
    assert service.log_in(pad, "casw", auth.LERAAR_WACHTWOORD) is not None
    assert service.log_in(pad, "casw", WACHTWOORD) is None
