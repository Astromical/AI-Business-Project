"""Tests voor het beheren van gegevens: opslaan, weigeren, rollback en tijdslots."""

from pathlib import Path

import pandas as pd
import pytest
from conftest import log_in_op_pagina
from streamlit.testing.v1 import AppTest

from src import beheer, service
from src.db import OpslaanFout, lees_tabel, maak_schema, sla_tabel_op, verbind
from src.models import DAGEN
from src.seed import seed

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def con(tmp_path):
    """Database met voorbeelddata."""
    verbinding = verbind(tmp_path / "t.db")
    maak_schema(verbinding)
    seed(verbinding)
    yield verbinding
    verbinding.close()


def _tel(con, sql):
    return con.execute(sql).fetchone()[0]


def test_geldige_wijziging_wordt_opgeslagen(con):
    tabel = beheer.lees(con, "leraar")
    tabel.loc[tabel["id"] == "PEE", "max_uren_per_dag"] = 4
    tabel.loc[len(tabel)] = ["NEW", "Nieuw (voorbeeld)", 3]
    assert beheer.sla_op(con, "leraar", tabel) == 2
    nu = {r["id"]: r for r in lees_tabel(con, "leraar")}
    assert nu["PEE"]["max_uren_per_dag"] == 4
    assert nu["NEW"]["naam"] == "Nieuw (voorbeeld)"
    assert len(nu) == 11


def test_onbekende_leraar_wordt_geweigerd_en_db_blijft_ongewijzigd(con):
    voor = lees_tabel(con, "les")
    tabel = beheer.lees(con, "les")
    tabel.loc[len(tabel)] = ["X-1", "tekenen", "1A", "NIEMAND", 1, "regulier"]
    with pytest.raises(OpslaanFout, match="verwijzing"):
        beheer.sla_op(con, "les", tabel)
    assert lees_tabel(con, "les") == voor


def test_rollback_na_een_fout_slaat_niets_half_op(con):
    voor = lees_tabel(con, "leraar")
    tabel = beheer.lees(con, "leraar")
    tabel.loc[len(tabel)] = ["OK", "Geldig", 3]
    tabel.loc[len(tabel)] = ["FOUT", "Ongeldig", 99]  # boven het maximum van 8
    with pytest.raises(OpslaanFout, match="niet toegestaan"):
        beheer.sla_op(con, "leraar", tabel)
    assert lees_tabel(con, "leraar") == voor


def test_leraar_wijzigen_laat_onbeschikbaarheid_staan(con):
    voor = _tel(con, "SELECT COUNT(*) FROM onbeschikbaar WHERE leraar_id = 'DUB'")
    assert voor == 2
    tabel = beheer.lees(con, "leraar")
    tabel.loc[tabel["id"] == "DUB", "naam"] = "Dubois (gewijzigd)"
    beheer.sla_op(con, "leraar", tabel)
    assert _tel(con, "SELECT COUNT(*) FROM onbeschikbaar WHERE leraar_id = 'DUB'") == voor
    assert _tel(con, "SELECT COUNT(*) FROM les WHERE leraar_id = 'DUB'") == 12


def test_alleen_echt_verwijderde_rijen_worden_verwijderd(con):
    tabel = beheer.lees(con, "onbeschikbaar")
    assert len(tabel) == 5
    beheer.sla_op(con, "onbeschikbaar", tabel.iloc[1:])
    assert _tel(con, "SELECT COUNT(*) FROM onbeschikbaar") == 4
    assert _tel(con, "SELECT COUNT(*) FROM leraar") == 10  # niets anders verdwenen
    assert _tel(con, "SELECT COUNT(*) FROM les") == 54  # 9 vakken x 6 klassen


def test_leraar_met_lessen_verwijderen_mislukt_zonder_gevolgen(con):
    tabel = beheer.lees(con, "leraar")
    with pytest.raises(OpslaanFout, match="verwijzing"):
        beheer.sla_op(con, "leraar", tabel[tabel["id"] != "PEE"])
    assert _tel(con, "SELECT COUNT(*) FROM leraar") == 10


def test_onbeschikbaar_via_dag_en_uur(con):
    tabel = beheer.lees(con, "onbeschikbaar")
    tabel.loc[len(tabel)] = ["PEE", "maandag", 1]
    beheer.sla_op(con, "onbeschikbaar", tabel)
    assert _tel(con, "SELECT COUNT(*) FROM onbeschikbaar WHERE leraar_id = 'PEE'") == 1
    tabel.loc[len(tabel)] = ["PEE", "maandag", 7]
    with pytest.raises(OpslaanFout, match="bestaat niet"):
        beheer.sla_op(con, "onbeschikbaar", tabel)


def test_lege_sleutel_en_dubbele_rij_worden_geweigerd(con):
    tabel = beheer.lees(con, "lokaal")
    fout = pd.concat([tabel, pd.DataFrame([{"id": None, "naam": "Naamloos", "type": "regulier"}])])
    with pytest.raises(OpslaanFout, match="Vul bij elke rij"):
        beheer.sla_op(con, "lokaal", fout)
    dubbel = pd.concat([tabel, tabel.iloc[[0]]])
    with pytest.raises(OpslaanFout, match="meer dan eens"):
        beheer.sla_op(con, "lokaal", dubbel)


def test_volledig_lege_rijen_worden_genegeerd(con):
    tabel = beheer.lees(con, "lokaal")
    leeg = pd.concat([tabel, pd.DataFrame([{"id": None, "naam": None, "type": None}])])
    assert beheer.sla_op(con, "lokaal", leeg) == 0


def test_onbekende_tabel_wordt_geweigerd(con):
    with pytest.raises(ValueError):
        sla_tabel_op(con, "sqlite_master; DROP TABLE les", [], [])
    with pytest.raises(ValueError):
        lees_tabel(con, "les; DROP TABLE les")


def test_tijdslots_opnieuw_aanmaken_wist_onbeschikbaarheid_en_rooster(con):
    from src.db import bewaar_rooster
    from src.loader import laad_probleem
    from src.solver import solve
    from src.models import Instellingen

    data = laad_probleem(con)
    bewaar_rooster(con, solve(data, Instellingen(30, {"Z1": 0})).toewijzingen)
    assert _tel(con, "SELECT COUNT(*) FROM ingepland") == 144
    beheer.maak_tijdslots(con, {dag: 5 for dag in DAGEN})
    assert _tel(con, "SELECT COUNT(*) FROM tijdslot") == 25
    assert _tel(con, "SELECT COUNT(*) FROM onbeschikbaar") == 0
    assert _tel(con, "SELECT COUNT(*) FROM ingepland") == 0
    assert _tel(con, "SELECT COUNT(*) FROM les") > 0  # lessen blijven staan


def test_van_een_lege_database_alles_invullen_en_rooster_maken(tmp_path):
    """Via dezelfde functies als de beheerpagina, vanuit een lege database."""
    pad = str(tmp_path / "leeg.db")
    con = service.open_database(pad)
    beheer.maak_tijdslots(con, {"maandag": 3, "dinsdag": 3})
    beheer.sla_op(con, "leraar", pd.DataFrame([["A", "Anna", 3], ["B", "Bram", 3]], columns=["id", "naam", "max_uren_per_dag"]))
    beheer.sla_op(con, "lokaal", pd.DataFrame([["R1", "Lokaal 1", "regulier"], ["L1", "Lab", "lab"]], columns=["id", "naam", "type"]))
    beheer.sla_op(con, "onbeschikbaar", pd.DataFrame([["A", "maandag", 1]], columns=["leraar_id", "dag", "uur"]))
    lessen = pd.DataFrame(
        [["1A-WIS", "wiskunde", "1A", "A", 3, "regulier"], ["1A-BIO", "biologie", "1A", "B", 2, "lab"]],
        columns=["id", "vak", "klas", "leraar_id", "aantal_per_week", "lokaaltype"],
    )
    beheer.sla_op(con, "les", lessen)
    con.close()
    data, meldingen = service.laad(pad)
    assert not service.heeft_fouten(meldingen)
    berekening = service.bereken(data)
    assert berekening.resultaat.status in ("optimaal", "geldig")
    assert len(berekening.resultaat.toewijzingen) == 5
    assert berekening.schendingen == ()


def _pagina(pad):
    at = AppTest.from_file(str(ROOT / "paginas" / "1_Gegevens.py"), default_timeout=60)
    return log_in_op_pagina(at, pad).run()


def test_beheerpagina_start_met_lege_database(tmp_path):
    at = _pagina(str(tmp_path / "leeg.db"))
    assert not at.exception
    assert len(at.tabs) == 4
    assert next(b for b in at.button if b.label == "Tijdslots aanmaken")


def test_beheerpagina_waarschuwt_bij_bestaande_tijdslots(tmp_path):
    pad = str(tmp_path / "t.db")
    service.vul_voorbeeld(pad, "voorbeeld")
    at = _pagina(pad)
    assert not at.exception
    assert any("wist de onbeschikbaarheid" in w.value for w in at.warning)
    knop = next(b for b in at.button if b.label == "Tijdslots aanmaken")
    assert knop.disabled  # pas actief na bevestigen
