"""Tests voor zachte regel Z3 (hetzelfde vak niet twee keer op één dag voor een klas)."""

from src.checker import tel_dubbele_vakken, tel_straf
from src.loader import maak_lesuren
from src.models import (
    Instellingen, Leraar, Les, Lokaal, ProbleemData, Resultaat, Tijdslot, Toewijzing,
)
from src.solver import solve

ALLEEN_Z3 = {"Z1": 0, "Z2": 0, "Z3": 5}
# maandag uur 1-3 zijn slots 1-3, dinsdag uur 1-3 slots 4-6
SLOTS = tuple(Tijdslot(i * 3 + u, dag, u) for i, dag in enumerate(("maandag", "dinsdag")) for u in (1, 2, 3))


def _twee_dagen(uren_per_week: int) -> ProbleemData:
    """Eén klas met één vak, op twee dagen van 3 uur."""
    leraren = (Leraar("JAN", "Jan", 3),)
    lessen = (Les("A", "wiskunde", "1A", "JAN", uren_per_week, "regulier"),)
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    return ProbleemData(SLOTS, lokalen, leraren, lessen, maak_lesuren(lessen))


def solve_z3(data: ProbleemData) -> Resultaat:
    """Los op met alleen Z3 aan."""
    return solve(data, Instellingen(10, ALLEEN_Z3))


def test_checker_telt_dubbel_vakuur():
    data = _twee_dagen(3)
    a, b, c = data.lesuren
    zelfde_dag = (Toewijzing(a, 1, "R1"), Toewijzing(b, 2, "R1"), Toewijzing(c, 3, "R1"))
    gespreid = (Toewijzing(a, 1, "R1"), Toewijzing(b, 2, "R1"), Toewijzing(c, 4, "R1"))
    assert tel_dubbele_vakken(data, zelfde_dag) == {"1A": 2}
    assert tel_dubbele_vakken(data, gespreid) == {"1A": 1}


def test_twee_uur_op_twee_dagen_geeft_geen_straf():
    data = _twee_dagen(2)
    resultaat = solve_z3(data)
    assert resultaat.straf_per_regel == {"Z3": 0}
    dagen = {data.tijdslot_per_id[t.tijdslot_id].dag for t in resultaat.toewijzingen}
    assert dagen == {"maandag", "dinsdag"}


def test_meer_uren_dan_dagen_geeft_kleinste_straf():
    # 3 uur op 2 dagen: één dubbel uur is onvermijdelijk, meer is niet nodig
    data = _twee_dagen(3)
    resultaat = solve_z3(data)
    assert resultaat.straf_per_regel == {"Z3": 5}
    assert tel_straf(data, resultaat.toewijzingen, ALLEEN_Z3) == resultaat.straf_per_regel


def test_twee_lessen_met_hetzelfde_vak_tellen_samen():
    lessen = (
        Les("A", "wiskunde", "1A", "JAN", 1, "regulier"),
        Les("B", "wiskunde", "1A", "JAN", 1, "regulier"),
    )
    data = ProbleemData(
        SLOTS, (Lokaal("R1", "Lokaal 1", "regulier"),), (Leraar("JAN", "Jan", 3),), lessen,
        maak_lesuren(lessen),
    )
    resultaat = solve_z3(data)
    assert resultaat.straf_per_regel == {"Z3": 0}
    assert tel_dubbele_vakken(data, resultaat.toewijzingen) == {"1A": 0}


def test_checker_gelijk_aan_solver_op_klein_probleem(klein_probleem):
    resultaat = solve_z3(klein_probleem)
    assert tel_straf(klein_probleem, resultaat.toewijzingen, ALLEEN_Z3) == resultaat.straf_per_regel
