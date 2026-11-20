"""Tests voor zachte regel Z1 (geen tussenuren voor klassen)."""

import pytest

from src.checker import tel_tussenuren
from src.db import maak_schema, verbind
from src.loader import laad_probleem, maak_lesuren
from src.models import Leraar, Les, Lokaal, ProbleemData, Tijdslot, Toewijzing
from src.seed import seed
from src.models import Instellingen
from src.solver import solve

GEEN_Z1 = {"Z1": 0}
ALLEEN_Z1 = {"Z1": 10}  # andere zachte regels uit, zodat alleen Z1 getest wordt


def _een_dag(onbeschikbaar: frozenset[int]) -> ProbleemData:
    """Eén klas, één leraar, twee lessen op één dag van 3 uur."""
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    leraren = (Leraar("JAN", "Jan", 3, onbeschikbaar),)
    lessen = (Les("A", "wis", "1A", "JAN", 2, "regulier"),)
    return ProbleemData(slots, (Lokaal("R1", "Lokaal 1", "regulier"),), leraren, lessen, maak_lesuren(lessen))


def _toewijzing(data, tijdslot_id, volgnummer=1):
    return Toewijzing(data.lesuren[volgnummer - 1], tijdslot_id, "R1")


def test_checker_telt_tussenuur():
    data = _een_dag(frozenset())
    assert tel_tussenuren(data, (_toewijzing(data, 1), _toewijzing(data, 3, 2))) == {"1A": 1}
    assert tel_tussenuren(data, (_toewijzing(data, 1), _toewijzing(data, 2, 2))) == {"1A": 0}


def test_klein_geval_beste_rooster_heeft_geen_tussenuren(klein_probleem):
    resultaat = solve(klein_probleem, Instellingen(10, ALLEEN_Z1))
    assert resultaat.straf_per_regel == {"Z1": 0}
    assert sum(tel_tussenuren(klein_probleem, resultaat.toewijzingen).values()) == 0


def test_z1_kiest_het_rooster_zonder_tussenuur():
    # drie vrije uren, twee lessen: uur 1 en 3 zou een tussenuur geven
    data = _een_dag(frozenset())
    resultaat = solve(data, Instellingen(10, ALLEEN_Z1))
    assert sorted(t.tijdslot_id for t in resultaat.toewijzingen) != [1, 3]
    assert resultaat.strafscore == 0


def test_onvermijdelijk_tussenuur_wordt_gestraft():
    # Jan kan alleen op uur 1 en 3: het tussenuur is niet te vermijden
    data = _een_dag(frozenset({2}))
    resultaat = solve(data, Instellingen(10, ALLEEN_Z1))
    assert resultaat.straf_per_regel == {"Z1": 10}
    assert resultaat.strafscore == 10
    assert sum(tel_tussenuren(data, resultaat.toewijzingen).values()) == 1


def test_gewicht_bepaalt_strafscore():
    data = _een_dag(frozenset({2}))
    assert solve(data, Instellingen(10, {"Z1": 3})).strafscore == 3


def test_gewicht_nul_schakelt_z1_uit():
    data = _een_dag(frozenset({2}))
    resultaat = solve(data, Instellingen(10, GEEN_Z1))
    assert resultaat.strafscore == 0
    assert resultaat.straf_per_regel == {}


@pytest.fixture(scope="module")
def voorbeeld(tmp_path_factory):
    con = verbind(tmp_path_factory.mktemp("db") / "t.db")
    maak_schema(con)
    seed(con)
    data = laad_probleem(con)
    con.close()
    return data


def test_voorbeelddata_z1_beter_dan_nulmeting(voorbeeld):
    nul = solve(voorbeeld, Instellingen(30, GEEN_Z1))
    met = solve(voorbeeld, Instellingen(30, ALLEEN_Z1))
    nul_gaten = sum(tel_tussenuren(voorbeeld, nul.toewijzingen).values())
    met_gaten = sum(tel_tussenuren(voorbeeld, met.toewijzingen).values())
    print(f"nulmeting {nul_gaten} tussenuren, met Z1 {met_gaten}, tijd {met.oplostijd_s:.1f}s")
    assert met_gaten < nul_gaten
    assert met.oplostijd_s < 30
    # de checker telt hetzelfde aantal als de solver rapporteert
    assert met.straf_per_regel["Z1"] == 10 * met_gaten
    assert met.strafscore == met.straf_per_regel["Z1"]
