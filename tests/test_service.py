"""Tests voor de app-logica en de Streamlit-pagina's (met AppTest)."""

from pathlib import Path

import pytest
from conftest import log_in_op_pagina
from streamlit.testing.v1 import AppTest

from src import service
from src.ui import ZACHTE_REGEL_NAMEN

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def pad(tmp_path):
    return str(tmp_path / "rooster.db")


def test_laad_nieuwe_database_is_leeg_met_fouten(pad):
    data, meldingen = service.laad(pad)
    assert len(data.lesuren) == 0
    assert service.heeft_fouten(meldingen)


def test_voorbeeld_laden_en_berekenen(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    data, meldingen = service.laad(pad)
    assert not service.heeft_fouten(meldingen)
    assert service.aantallen(data)["Lesuren"] == 144
    berekening = service.bereken(data)
    assert berekening.resultaat.status in ("optimaal", "geldig")
    assert berekening.schendingen == ()


def test_onmogelijk_voorbeeld_geeft_fout(pad):
    service.vul_voorbeeld(pad, "onmogelijk")
    _, meldingen = service.laad(pad)
    assert service.heeft_fouten(meldingen)


def test_leeg_maken(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    service.maak_leeg(pad)
    data, _ = service.laad(pad)
    assert len(data.lesuren) == 0


def _pagina(pad):
    at = AppTest.from_file(str(ROOT / "paginas" / "2_Rooster.py"), default_timeout=90)
    return log_in_op_pagina(at, pad).run()


def test_pagina_zonder_gegevens_toont_uitleg(tmp_path):
    at = _pagina(str(tmp_path / "leeg.db"))
    assert not at.exception
    assert any("Voeg eerst lessen toe" in i.value for i in at.info)
    assert not at.error  # een lege database is geen fout


def test_pagina_knop_uit_bij_fout(pad):
    service.vul_voorbeeld(pad, "onmogelijk")
    at = _pagina(pad)
    assert not at.exception
    assert at.error
    knop = next(b for b in at.button if b.label == "Rooster berekenen")
    assert knop.disabled


def test_pagina_berekent_rooster(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = _pagina(pad)
    knop = next(b for b in at.button if b.label == "Rooster berekenen")
    assert not knop.disabled
    at = knop.click().run()
    assert not at.exception
    waarden = {m.label: m.value for m in at.metric}
    assert waarden["Schendingen"] == "0"
    assert waarden["Status"] in ("optimaal", "geldig")
    # de drie weergaven staan er, elk met een keuzelijst en een tabel
    assert len(at.tabs) == 3
    assert len(at.main.selectbox) == 3  # de keuzelijst in de zijbalk telt niet mee
    assert len(at.get("html")) == 3  # een rooster per weergave


def test_startpagina_start(pad):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.session_state["pad"] = pad
    assert not at.run().exception


def test_zijbalk_gewicht_verandert_resultaat(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = _pagina(pad)
    assert at.slider(key="gewicht_z1").value == 10
    at = next(b for b in at.button if b.label == "Rooster berekenen").click().run()
    met = {m.label: m.value for m in at.metric}
    assert met["Tussenuren klassen"] == "0"
    for regel in ZACHTE_REGEL_NAMEN:  # alle zachte regels uit: strafscore 0
        at.slider(key=f"gewicht_{regel.lower()}").set_value(0)
    at = next(b for b in at.run().button if b.label == "Rooster berekenen").click().run()
    zonder = {m.label: m.value for m in at.metric}
    assert int(zonder["Tussenuren klassen"]) > 0
    assert zonder["Strafscore"] == "0"


def _maak_onoplosbare_database(pad):
    """Een database die door valideer komt, maar waarvoor geen rooster bestaat."""
    con = service.open_database(pad)
    with con:
        con.executemany(
            "INSERT INTO tijdslot VALUES (?, ?, ?)",
            [(1, "maandag", 1), (2, "maandag", 2), (3, "dinsdag", 1)],
        )
        con.execute("INSERT INTO lokaal VALUES ('R1', 'Lokaal 1', 'regulier')")
        con.execute("INSERT INTO leraar VALUES ('JAN', 'Jan', 1)")
        con.execute("INSERT INTO leraar VALUES ('AN', 'An', 3)")
        con.executemany("INSERT INTO onbeschikbaar VALUES ('AN', ?)", [(1,), (2,)])
        con.execute("INSERT INTO les VALUES ('1A-WIS', 'wiskunde', '1A', 'JAN', 2, 'regulier')")
        con.execute("INSERT INTO les VALUES ('1A-NED', 'nederlands', '1A', 'AN', 1, 'regulier')")
    con.close()


def test_onoplosbaar_probleem_geeft_uitleg_in_service(pad):
    _maak_onoplosbare_database(pad)
    data, meldingen = service.laad(pad)
    assert not service.heeft_fouten(meldingen)
    berekening = service.bereken(data)
    assert berekening.resultaat.status == "onoplosbaar"
    assert any("maximum van 1 uur per dag voor Jan" in regel for regel in berekening.uitleg)


def test_pagina_crasht_niet_op_onoplosbaar_probleem(pad):
    _maak_onoplosbare_database(pad)
    at = _pagina(pad)
    at = next(b for b in at.button if b.label == "Rooster berekenen").click().run()
    assert not at.exception
    assert any("geen rooster" in e.value for e in at.error)
    assert any("maximum van 1 uur per dag" in i.value for i in at.info)


def test_pagina_gooit_verouderd_rooster_weg_als_de_gegevens_veranderen(pad):
    """Regressie: KeyError als de database na het rekenen verandert (bijv. in een ander tabblad)."""
    from src import beheer

    service.vul_voorbeeld(pad, "voorbeeld")
    at = _pagina(pad)
    at = next(b for b in at.button if b.label == "Rooster berekenen").click().run()
    assert len(at.get("html")) == 3  # een rooster per weergave
    # buiten deze sessie om: minder tijdslots, dus tijdslot-ids uit het oude rooster bestaan niet meer
    con = service.open_database(pad)
    beheer.maak_tijdslots(con, {"maandag": 3})
    con.close()
    at.run()
    assert not at.exception
    assert len(at.get("html")) == 0
    assert any("gegevens zijn veranderd" in i.value for i in at.info)


def test_is_actueel(pad, klein_probleem):
    from dataclasses import replace

    service.vul_voorbeeld(pad, "voorbeeld")
    data, _ = service.laad(pad)
    berekening = service.Berekening(service.Resultaat("geldig", (), 0.0), (), data=data)
    assert service.is_actueel(berekening, service.laad(pad)[0])  # opnieuw ingelezen: gelijk
    assert not service.is_actueel(berekening, replace(data, tijdslots=data.tijdslots[:3]))
    assert not service.is_actueel(berekening, klein_probleem)


def test_pagina_toont_streepjes_zonder_rooster(pad):
    _maak_onoplosbare_database(pad)
    at = _pagina(pad)
    at = next(b for b in at.button if b.label == "Rooster berekenen").click().run()
    waarden = {m.label: m.value for m in at.metric}
    assert waarden["Status"] == "onoplosbaar"
    assert waarden["Schendingen"] == waarden["Strafscore"] == waarden["Tussenuren klassen"] == "-"


def _startpagina(pad: str, rol: str, leraar_id: str | None = None) -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    return log_in_op_pagina(at, pad, rol, leraar_id).run()


def _links(at: AppTest) -> list[str]:
    return [link.proto.label for link in at.get("page_link")]


def test_startpagina_toont_de_stappen_voor_een_lege_database(pad):
    at = _startpagina(pad, "roostermaker")
    assert not at.exception
    assert [k.value for k in at.subheader] == [
        "Roostermaker", "1. Gegevens invoeren", "2. Rooster berekenen", "3. Rooster delen"
    ]
    assert any("Voeg eerst lessen toe" in i.value for i in at.info)
    assert not at.error  # een lege database is geen fout
    assert any("Voorbeelddata" in c.value for c in at.caption)
    assert _links(at) == [
        "Lessen importeren uit Excel, CSV of JSON", "Lessen zelf invullen", "Rooster berekenen",
        "Accounts voor leraren beheren",
    ]


def test_startpagina_toont_wat_er_al_ingevoerd_is(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = _startpagina(pad, "roostermaker")
    assert any("144 lesuren" in s.value for s in at.success)
    assert not at.info


def test_startpagina_van_een_leraar_wijst_naar_mijn_rooster(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    leraar = service.laad(pad)[0].leraren[0].id
    at = _startpagina(pad, "leraar", leraar)
    assert not at.exception
    assert [k.value for k in at.subheader] == ["Docent"]
    assert _links(at) == ["Mijn rooster bekijken"]


def test_dataset_vervangt_de_gegevens_en_laat_accounts_staan(pad, tmp_path, monkeypatch):
    map_ = tmp_path / "datasets"
    map_.mkdir()
    (map_ / "Testklas.csv").write_text(
        "klas,vak,leraar,uren_per_week,soort_lokaal\n9Z,wiskunde,Jan,4,regulier\n9Z,taal,An,3,regulier\n"
    )
    monkeypatch.setattr(service, "DATASETS_MAP", map_)
    service.vul_voorbeeld(pad, "voorbeeld")
    service.maak_gebruiker(pad, "an", "wachtwoord123", "roostermaker")
    assert list(service.datasets()) == ["Testklas"]
    service.laad_dataset(pad, service.datasets()["Testklas"])
    data, meldingen = service.laad(pad)
    assert data.klassen == ("9Z",) and len(data.lesuren) == 7  # voorbeelddata is weg
    assert len(data.tijdslots) == 40  # 5 dagen x 8 uur
    assert not service.heeft_fouten(meldingen)
    assert service.zoek_gebruiker(pad, "an") is not None


def test_dataset_is_te_kiezen_in_de_zijbalk(pad, tmp_path, monkeypatch):
    map_ = tmp_path / "datasets"
    map_.mkdir()
    (map_ / "Testklas.csv").write_text("klas,vak,leraar,uren_per_week\n9Z,wiskunde,Jan,4\n")
    monkeypatch.setattr(service, "DATASETS_MAP", map_)
    at = log_in_op_pagina(AppTest.from_file(str(ROOT / "paginas" / "2_Rooster.py"), default_timeout=60), pad).run()
    at.sidebar.selectbox(key="voorbeeld_variant").set_value("dataset:Testklas").run()
    at = next(b for b in at.sidebar.button if b.label == "Voorbeeld laden").click().run()
    assert not at.exception
    assert service.laad(pad)[0].klassen == ("9Z",)


def test_regels_staan_in_het_blok_geavanceerd(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    at = _pagina(pad)
    assert not at.exception
    geavanceerd = next(e for e in at.sidebar.expander if e.label == "Geavanceerd")
    sleutels = {s.key for s in geavanceerd.slider}
    assert {"tijdslimiet_s", "gewicht_z1", "gewicht_z4"} <= sleutels
    assert "Database leegmaken" in [b.label for b in geavanceerd.button]
    assert not at.sidebar.header  # geen losse kop "Instellingen" meer


def test_startpagina_toont_welke_fouten_er_zijn(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    service.maak_leeg(pad)
    con = service.open_database(pad)
    con.execute("INSERT INTO leraar VALUES ('JAN', 'Jan', 5)")
    con.execute("INSERT INTO les VALUES ('1A-WIS', 'wiskunde', '1A', 'JAN', 2, 'regulier')")
    con.commit()
    con.close()
    at = _startpagina(pad, "roostermaker")
    assert any("geen tijdslots" in e.value for e in at.error)
