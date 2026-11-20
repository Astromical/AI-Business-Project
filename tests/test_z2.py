"""Tests voor zachte regel Z2 (geen tussenuren voor leraren)."""

import pytest

from src.checker import tel_straf, tel_tussenuren_leraren
from src.db import maak_schema, verbind
from src.loader import laad_probleem, maak_lesuren
from src.models import Instellingen, Leraar, Les, Lokaal, ProbleemData, Tijdslot, Toewijzing
from src.seed import seed
from src.solver import solve

ALLEEN_Z2 = {"Z1": 0, "Z2": 5}


def _twee_klassen(onbeschikbaar: frozenset[int]) -> ProbleemData:
    """Eén leraar geeft twee klassen elk één uur, op een dag van 3 uur (geen tussenuur voor klassen)."""
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    leraren = (Leraar("JAN", "Jan", 3, onbeschikbaar),)
    lessen = (
        Les("A", "wis", "1A", "JAN", 1, "regulier"),
        Les("B", "wis", "1B", "JAN", 1, "regulier"),
    )
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    return ProbleemData(slots, lokalen, leraren, lessen, maak_lesuren(lessen))


def test_checker_telt_tussenuur_van_leraar():
    data = _twee_klassen(frozenset())
    a, b = data.lesuren
    assert tel_tussenuren_leraren(data, (Toewijzing(a, 1, "R1"), Toewijzing(b, 3, "R1"))) == {"JAN": 1}
    assert tel_tussenuren_leraren(data, (Toewijzing(a, 1, "R1"), Toewijzing(b, 2, "R1"))) == {"JAN": 0}


def test_z2_vermijdt_tussenuur_van_leraar():
    data = _twee_klassen(frozenset())
    resultaat = solve(data, Instellingen(10, ALLEEN_Z2))
    assert resultaat.straf_per_regel == {"Z2": 0}
    assert sum(tel_tussenuren_leraren(data, resultaat.toewijzingen).values()) == 0


def test_onvermijdelijk_tussenuur_van_leraar_wordt_gestraft():
    # Jan kan niet op uur 2: zijn tussenuur is niet te vermijden
    data = _twee_klassen(frozenset({2}))
    resultaat = solve(data, Instellingen(10, ALLEEN_Z2))
    assert resultaat.straf_per_regel == {"Z2": 5}
    assert tel_straf(data, resultaat.toewijzingen, ALLEEN_Z2) == {"Z2": 5}


def test_gewicht_nul_schakelt_z2_uit():
    data = _twee_klassen(frozenset({2}))
    resultaat = solve(data, Instellingen(10, {"Z1": 0, "Z2": 0}))
    assert resultaat.straf_per_regel == {}


@pytest.fixture(scope="module")
def voorbeeld(tmp_path_factory):
    con = verbind(tmp_path_factory.mktemp("db") / "t.db")
    maak_schema(con)
    seed(con)
    data = laad_probleem(con)
    con.close()
    return data


def test_voorbeelddata_met_z1_en_z2(voorbeeld):
    gewichten = {"Z1": 10, "Z2": 5}
    met = solve(voorbeeld, Instellingen(30, gewichten))
    zonder = solve(voorbeeld, Instellingen(30, {"Z1": 10, "Z2": 0}))
    met_gaten = sum(tel_tussenuren_leraren(voorbeeld, met.toewijzingen).values())
    zonder_gaten = sum(tel_tussenuren_leraren(voorbeeld, zonder.toewijzingen).values())
    print(f"tussenuren leraren: zonder Z2 {zonder_gaten}, met Z2 {met_gaten}; "
          f"{met.status} in {met.oplostijd_s:.1f}s (zoeken {met.tijd_zoeken_s:.1f}s)")
    assert met.status in ("optimaal", "geldig")
    assert met.oplostijd_s - met.tijd_zoeken_s <= 31
    assert met_gaten <= zonder_gaten
    assert tel_straf(voorbeeld, met.toewijzingen, gewichten) == met.straf_per_regel
