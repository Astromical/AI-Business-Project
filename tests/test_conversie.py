"""Tests voor het omzetten van allerlei invoer naar de lessen-CSV (met verzonnen gegevens)."""

import io
import json
from datetime import time
from pathlib import Path

import pytest
from conftest import log_in_op_pagina
from openpyxl import Workbook
from streamlit.testing.v1 import AppTest

from src import beheer, service
from src.auth import mag
from src.conversie import ConversieFout, LesRij, converteer, is_webuntis, naar_csv, uit_rijen

ROOT = Path(__file__).resolve().parent.parent
RIJ = LesRij("1A", "wiskunde", "Jan", 4, "regulier")


def _excel(rijen) -> bytes:
    boek = Workbook()
    for rij in rijen:
        boek.active.append(rij)
    uit = io.BytesIO()
    boek.save(uit)
    return uit.getvalue()


def _waarde(soort, naam):
    return [{"current": {"type": soort, "status": "REGULAR", "shortName": naam[:3], "longName": naam}, "removed": None}]


def _blok(start, einde, vak="Project", docenten=("Jansen",), klassen=(), status="REGULAR", lokalen=("A1",)):
    return {
        "duration": {"start": f"2026-01-05T{start}", "end": f"2026-01-05T{einde}"},
        "status": status,
        "position1": _waarde("SUBJECT", vak),
        "position2": [p for d in docenten for p in _waarde("TEACHER", d)],
        "position3": [p for r in lokalen for p in _waarde("ROOM", r)],
        "position4": [p for k in klassen for p in _waarde("CLASS", k)],
    }


def _webuntis(blokken, type_="CLASS", dagen=1):
    return {
        "format": 2,
        "days": [
            {
                "date": f"2026-01-{i + 5:02d}",
                "resourceType": type_,
                "resource": {"id": 1, "shortName": "9X"},
                "status": "REGULAR",
                "dayEntries": [],
                "gridEntries": blokken if i == 0 else [],
            }
            for i in range(dagen)
        ],
    }


# --- vaste formaten ---


def test_csv_met_puntkomma_en_windows_codering():
    tekst = "Klas;Vak;Docent;Uren\n1A;Français;Jan;4\n".encode("cp1252")
    assert converteer("x.csv", tekst).rijen == (LesRij("1A", "Français", "Jan", 4, "regulier"),)


@pytest.mark.parametrize(
    ("tekst", "scheiding"), [("klas,vak,leraar,uren\n", ","), ("klas\tvak\tleraar\turen\n", "\t")]
)
def test_andere_scheidingstekens(tekst, scheiding):
    inhoud = (tekst + scheiding.join(["1A", "wiskunde", "Jan", "4"]) + "\n").encode()
    assert converteer("x.txt", inhoud).rijen == (RIJ,)


def test_excel_met_lege_rij_boven_de_kop_en_tijden():
    inhoud = _excel([[None, None], ["Klas", "Vak", "Leerkracht", "Van", "Tot"], ["1A", "wiskunde", "Jan", time(9), time(13)]])
    assert converteer("x.xlsx", inhoud).rijen == (RIJ,)


def test_json_lijst_en_json_met_lijst_erin():
    rijen = [{"class": "1A", "subject": "wiskunde", "teacher": "Jan", "hours": 4}]
    assert converteer("a.json", json.dumps(rijen).encode()).rijen == (RIJ,)
    assert converteer("b.json", json.dumps({"meta": 1, "lessen": rijen}).encode()).rijen == (RIJ,)


def test_bestand_zonder_extensie_wordt_herkend():
    assert converteer("download", b'[{"klas": "1A", "vak": "wiskunde", "leraar": "Jan", "uren": 4}]').rijen == (RIJ,)


def test_uren_uit_start_en_einde_worden_opgeteld():
    rijen = [
        {"klas": "1A", "vak": "wiskunde", "leraar": "Jan", "start": "09:00", "einde": "11:00"},
        {"klas": "1a", "vak": "Wiskunde", "leraar": "JAN", "start": "2026-01-06T13:00", "einde": "2026-01-06T15:00"},
    ]
    assert uit_rijen(rijen).rijen == (RIJ,)


def test_halve_uren_worden_eerst_opgeteld_en_dan_afgerond():
    half = {"klas": "1A", "vak": "wiskunde", "leraar": "Jan", "uren": "1,5"}
    assert uit_rijen([half, half]).rijen[0].uren_per_week == 3
    uitkomst = uit_rijen([half])
    assert uitkomst.rijen[0].uren_per_week == 2
    assert any("afgerond" in m.tekst for m in uitkomst.meldingen)


@pytest.mark.parametrize(("waarde", "soort"), [("Labo", "lab"), ("Sporthal", "gym"), ("Theorie", "regulier"), (None, "regulier")])
def test_soort_lokaal_wordt_vertaald(waarde, soort):
    rij = {"klas": "1A", "vak": "x", "leraar": "Jan", "uren": 1, "lokaaltype": waarde}
    assert uit_rijen([rij]).rijen[0].soort_lokaal == soort


def test_lege_soort_lokaal_geeft_geen_melding_per_rij():
    uitkomst = uit_rijen([{"klas": "1A", "vak": "x", "leraar": "Jan", "uren": 1}])
    assert len(uitkomst.meldingen) == 1 and "None" not in uitkomst.meldingen[0].tekst


def test_onbekende_soort_lokaal_geeft_melding():
    rij = {"klas": "1A", "vak": "x", "leraar": "Jan", "uren": 1, "lokaaltype": "kelder"}
    uitkomst = uit_rijen([rij], standaard_lokaal="lab")
    assert uitkomst.rijen[0].soort_lokaal == "lab"
    assert any("kelder" in m.tekst for m in uitkomst.meldingen)


def test_eigen_kolomkoppeling():
    rij = {"Groepje": "1A", "Cursus": "wiskunde", "Wie": "Jan", "Duur": 4}
    koppeling = {"klas": "Groepje", "vak": "Cursus", "leraar": "Wie", "uren_per_week": "Duur"}
    assert uit_rijen([rij], koppeling).rijen == (RIJ,)


# --- weigeren ---


def test_uren_ontbreken_wordt_uitgelegd():
    with pytest.raises(ConversieFout, match="hoeveel uur"):
        uit_rijen([{"klas": "1A", "vak": "x", "leraar": "Jan"}])


def test_ontbrekende_kolom_wordt_genoemd():
    with pytest.raises(ConversieFout, match="leraar"):
        uit_rijen([{"klas": "1A", "vak": "x", "uren": 1}])


def test_foute_rij_wordt_overgeslagen_en_gemeld():
    rijen = [
        {"klas": "1A", "vak": "wiskunde", "leraar": "Jan", "uren": 4},
        {"klas": "", "vak": "x", "leraar": "Jan", "uren": 1},
        {"klas": "1B", "vak": "x", "leraar": "Jan", "uren": "veel"},
        {"klas": "1C", "vak": "x", "leraar": "Jan", "uren": -2},
        {"klas": "1D", "vak": "x", "leraar": "Jan", "uren": "nan"},
    ]
    uitkomst = uit_rijen(rijen)
    assert uitkomst.rijen == (RIJ,) and uitkomst.heeft_fouten
    assert sum(m.ernst == "fout" for m in uitkomst.meldingen) == 4


@pytest.mark.parametrize(
    ("inhoud", "stukje"),
    [
        (b"%PDF-1.7 rest", "PDF"),
        (b"\xd0\xcf\x11\xe0oud", ".xlsx"),
        (b"\x89PNG\r\n\x00\x00", "geen tekst"),
        (b"PK\x03\x04kapot", "niet gelezen"),
        (b"{kapot", "niet gelezen"),
        (b'{"a": 1}', "lijst met rijen"),
    ],
)
def test_onbruikbare_bestanden_geven_een_duidelijke_fout(inhoud, stukje):
    with pytest.raises(ConversieFout, match=stukje):
        converteer("x", inhoud)


def test_ongeldige_standaardsoort():
    with pytest.raises(ConversieFout, match="Soort lokaal"):
        uit_rijen([{"klas": "1A", "vak": "x", "leraar": "J", "uren": 1}], standaard_lokaal="zolder")


# --- WebUntis ---


def test_webuntis_telt_uren_per_vak_en_slaat_afgelaste_lessen_over():
    gegevens = _webuntis([_blok("09:00", "12:00"), _blok("13:00", "14:00"), _blok("14:00", "16:00", status="CANCELLED")])
    assert is_webuntis(gegevens)
    assert converteer("x", json.dumps(gegevens).encode()).rijen == (LesRij("9X", "Project", "Jansen", 4, "regulier"),)


def test_webuntis_meldt_wat_niet_past():
    blokken = [
        _blok("09:00", "11:00", klassen=("9X", "9Y")),
        _blok("10:00", "12:00", vak="Ander", docenten=("Jansen", "Peters"), lokalen=("A1", "A2")),
    ]
    uitkomst = converteer("x", json.dumps(_webuntis(blokken)).encode())
    teksten = " ".join(m.tekst for m in uitkomst.meldingen)
    assert uitkomst.heeft_fouten
    for stukje in ("gedeeld", "overlappen", "meerdere docenten", "meerdere lokalen", "losse lesuren", "Onbeschikbaarheid"):
        assert stukje in teksten


def test_parallelle_vakken_komen_in_een_eigen_groep():
    blokken = [
        _blok("09:00", "12:00", "Groot"),
        _blok("13:00", "15:00", "Groot"),
        _blok("09:00", "10:00", "Keuze", docenten=("Peters",)),
        _blok("15:00", "16:00", "Los", docenten=("Maes",)),
    ]
    rijen = converteer("x", json.dumps(_webuntis(blokken)).encode()).rijen
    assert {(r.klas, r.vak, r.uren_per_week) for r in rijen} == {
        ("9X", "Groot", 5),
        ("9X-2", "Keuze", 1),
        ("9X", "Los", 1),
    }


def test_groepen_veranderen_niet_tussen_twee_keer_omzetten():
    blokken = [_blok("09:00", "11:00", f"Vak{i}", docenten=(f"D{i}",)) for i in range(4)]
    inhoud = json.dumps(_webuntis(blokken)).encode()
    eerste = converteer("x", inhoud).rijen
    assert eerste == converteer("x", inhoud).rijen
    assert len({r.klas for r in eerste}) == 4


def test_webuntis_van_meer_dan_een_week_wordt_gemeld():
    uitkomst = converteer("x", json.dumps(_webuntis([_blok("09:00", "10:00")], dagen=14)).encode())
    assert any("14 dagen" in m.tekst for m in uitkomst.meldingen)


def test_webuntis_van_een_docent_wordt_geweigerd():
    with pytest.raises(ConversieFout, match="rooster van een klas"):
        converteer("x", json.dumps(_webuntis([_blok("09:00", "10:00")], "TEACHER")).encode())


def test_blok_zonder_docent_wordt_gemeld():
    uitkomst = converteer("x", json.dumps(_webuntis([_blok("09:00", "10:00", docenten=())])).encode())
    assert uitkomst.rijen == () and uitkomst.heeft_fouten


# --- CSV ---


def test_csv_gaat_heen_en_terug():
    rijen = (RIJ, LesRij("2B", 'vak, met "tekens"', "De Wit", 2, "lab"))
    tekst = naar_csv(rijen)
    assert tekst.splitlines()[0] == "klas,vak,leraar,uren_per_week,soort_lokaal"
    assert converteer("x.csv", tekst.encode()).rijen == tuple(sorted(rijen, key=lambda r: r.klas))


# --- database ---


@pytest.fixture
def pad(tmp_path):
    return str(tmp_path / "rooster.db")


@pytest.fixture
def con(pad):
    verbinding = service.open_database(pad)
    yield verbinding
    verbinding.close()


def test_importeren_maakt_leraren_en_lessen_en_is_te_herhalen(con):
    rijen = (RIJ, LesRij("1B", "wiskunde", "Jan", 3, "lab"), LesRij("1A", "frans", "An De Wit", 2, "regulier"))
    assert beheer.importeer(con, rijen) == (2, 3)
    assert beheer.importeer(con, rijen) == (0, 0)
    assert beheer.importeer(con, (LesRij("1A", "Wiskunde", "JAN", 5, "regulier"),)) == (0, 0)
    lessen = beheer.lees(con, "les")
    assert len(lessen) == 3 and len(beheer.lees(con, "leraar")) == 2
    assert lessen[lessen["klas"] == "1A"]["aantal_per_week"].max() == 5


def test_importeren_herkent_bestaande_leraar_en_laat_de_rest_staan(pad, con):
    service.vul_voorbeeld(pad, "voorbeeld")
    voor = service.laad(pad)[0]
    naam = voor.leraren[0].naam.upper()
    assert beheer.importeer(con, (LesRij("9Z", "nieuw vak", naam, 2, "regulier"),)) == (0, 1)
    na = service.laad(pad)[0]
    assert len(na.leraren) == len(voor.leraren) and len(na.lessen) == len(voor.lessen) + 1


def test_mislukte_import_laat_niets_achter(con):
    with pytest.raises(service.OpslaanFout):
        beheer.importeer(con, (LesRij("1A", "x", "Nieuw", 2, "zolder"),))
    assert beheer.lees(con, "leraar").empty and beheer.lees(con, "les").empty


def test_upload_op_lege_database_geeft_meteen_een_rooster(con):
    from src.checker import controleer
    from src.loader import laad_probleem, valideer
    from src.models import Instellingen
    from src.solver import solve

    blokken = [_blok("09:00", "12:00", "Wiskunde"), _blok("09:00", "10:00", "Keuze", docenten=("Peters",))]
    rijen = converteer("x", json.dumps(_webuntis(blokken)).encode()).rijen
    assert beheer.vul_basis_aan(con, rijen)[0] > 0
    beheer.importeer(con, rijen)
    data = laad_probleem(con)
    assert valideer(data) == []
    resultaat = solve(data, Instellingen(2))
    assert resultaat.toewijzingen and controleer(data, resultaat.toewijzingen) == []


def test_aanvullen_wist_niets_en_voegt_niets_toe_als_het_past(pad, con):
    service.vul_voorbeeld(pad, "voorbeeld")
    voor = service.laad(pad)[0]
    rijen = (LesRij("9Z", "x", "Nieuw", 2, "regulier"),)
    assert beheer.vul_basis_aan(con, rijen) == (0, 0)
    groot = (LesRij("9Z", "x", "Nieuw", 35, "regulier"),)
    tijdslots, _ = beheer.vul_basis_aan(con, groot)
    na = service.laad(pad)[0]
    assert tijdslots == 10 and len(na.tijdslots) == 40
    assert {s.id for s in voor.tijdslots} <= {s.id for s in na.tijdslots}
    assert len(na.lessen) == len(voor.lessen) and na.lokalen[:len(voor.lokalen)] != ()


def test_webuntis_json_wordt_een_geldig_rooster(con):
    from src.checker import controleer
    from src.db import lees_tabel, maak_tijdslots
    from src.loader import laad_probleem
    from src.models import Instellingen
    from src.solver import solve

    maak_tijdslots(con, {"maandag": 3, "dinsdag": 3})
    con.execute("INSERT INTO lokaal VALUES ('R1', 'Lokaal 1', 'regulier')")
    con.commit()
    blokken = [_blok("09:00", "11:00", "Wiskunde"), _blok("13:00", "15:00", "Frans", docenten=("Peters",))]
    uitkomst = converteer("rooster", json.dumps(_webuntis(blokken)).encode())
    assert not uitkomst.heeft_fouten
    beheer.importeer(con, uitkomst.rijen)
    data = laad_probleem(con)
    resultaat = solve(data, Instellingen(2))
    assert resultaat.status in ("optimaal", "geldig")
    assert len(resultaat.toewijzingen) == 4 and controleer(data, resultaat.toewijzingen) == []
    assert len(lees_tabel(con, "leraar")) == 2


# --- pagina ---


def _pagina(pad, rol="roostermaker"):
    bestand = str(ROOT / "paginas" / "6_Importeren.py")
    return log_in_op_pagina(AppTest.from_file(bestand, default_timeout=30), pad, rol).run()


def test_importeren_alleen_voor_wie_gegevens_beheert(pad):
    assert mag("roostermaker", "importeren")
    assert not mag("leraar", "importeren")
    leraar = _pagina(pad, "leraar")
    assert any("geen toegang" in e.value for e in leraar.error)
    assert not leraar.file_uploader


def test_uploaden_toont_eerst_een_voorbeeld_en_voegt_pas_daarna_toe(pad):
    at = _pagina(pad)
    assert not at.exception and at.title[0].value == "Importeren"
    at.file_uploader[0].upload("lessen.csv", b"klas;vak;docent;uren\n1A;wiskunde;Jan;4\n", "text/csv").run()
    assert not at.exception
    assert len(at.dataframe) == 1
    voorbeeld = at.dataframe[0].value
    assert voorbeeld["leraar"].tolist() == ["Jan"]  # de leraar staat in het voorbeeld, niet leeg
    assert len(service.laad(pad)[0].lessen) == 0  # nog niets opgeslagen
    at = next(b for b in at.button if b.label == "Lessen toevoegen").click().run()
    assert not at.exception
    data = service.laad(pad)[0]
    assert [(l.klas, l.aantal_per_week) for l in data.lessen] == [("1A", 4)]
    assert any("1 nieuwe lessen" in m.value for m in at.success)
    assert not at.dataframe  # de uploadzone is weer leeg, klaar voor het volgende bestand
    assert not [b for b in at.button if b.label == "Lessen toevoegen"]
    assert service.laad(pad)[0].tijdslots and service.laad(pad)[0].lokalen


def test_onvolledig_rooster_vraagt_eerst_bevestiging(pad):
    blokken = [_blok("09:00", "11:00", klassen=("9X", "9Y"))]
    at = _pagina(pad)
    at.file_uploader[0].upload("rooster", json.dumps(_webuntis(blokken)).encode(), "application/json").run()
    assert at.error
    knop = next(b for b in at.button if b.label == "Lessen toevoegen")
    assert knop.disabled
    at.checkbox[0].check().run()
    assert not next(b for b in at.button if b.label == "Lessen toevoegen").disabled


def test_kapot_bestand_geeft_melding_en_geen_knop(pad):
    at = _pagina(pad)
    at.file_uploader[0].upload("rooster.pdf", b"%PDF-1.7 rest", "application/pdf").run()
    assert not at.exception
    assert any("PDF" in e.value for e in at.error)
    assert not [b for b in at.button if b.label == "Lessen toevoegen"]
