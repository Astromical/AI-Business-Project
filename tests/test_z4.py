"""Tests voor zachte regel Z4 (zware vakken liever niet in het laatste uur)."""

from src.checker import tel_per_regel, tel_straf, tel_zware_laatste_uren
from src.config import STANDAARD_CONFIG, laad_instellingen
from src.loader import maak_lesuren
from src.models import (
    Instellingen, Leraar, Les, Lokaal, ProbleemData, Resultaat, Tijdslot, Toewijzing,
)
from src.solver import solve

ALLEEN_Z4 = {"Z1": 0, "Z2": 0, "Z3": 0, "Z4": 2}
ZWAAR = ("wiskunde",)
LOKAAL = (Lokaal("R1", "Lokaal 1", "regulier"),)


def _solve_z4(data: ProbleemData, zware_vakken: tuple[str, ...] = ZWAAR) -> Resultaat:
    """Los op met alleen Z4 aan."""
    return solve(data, Instellingen(10, ALLEEN_Z4, zware_vakken=zware_vakken))


def _een_dag(lessen: tuple[Les, ...]) -> ProbleemData:
    """Eén klas en één leraar op maandag met 3 uur."""
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    return ProbleemData(slots, LOKAAL, (Leraar("JAN", "Jan", 3),), lessen, maak_lesuren(lessen))


def _korte_woensdag() -> ProbleemData:
    """Maandag 3 uur (slots 1-3), woensdag 2 uur (slots 4-5); Jan kan alleen op woensdag."""
    maandag = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    slots = (*maandag, Tijdslot(4, "woensdag", 1), Tijdslot(5, "woensdag", 2))
    leraren = (Leraar("JAN", "Jan", 3, frozenset({1, 2, 3})),)
    lessen = (Les("A", "Wiskunde", "1A", "JAN", 1, "regulier"),)
    return ProbleemData(slots, LOKAAL, leraren, lessen, maak_lesuren(lessen))


def test_checker_telt_laatste_uur_per_dag():
    data = _korte_woensdag()
    (uur,) = data.lesuren
    assert tel_zware_laatste_uren(data, (Toewijzing(uur, 5, "R1"),), ZWAAR) == 1  # woensdag uur 2
    assert tel_zware_laatste_uren(data, (Toewijzing(uur, 2, "R1"),), ZWAAR) == 0  # maandag uur 2
    assert tel_zware_laatste_uren(data, (Toewijzing(uur, 3, "R1"),), ZWAAR) == 1  # maandag uur 3


def test_zwaar_vak_niet_in_het_laatste_uur():
    lessen = (
        Les("A", "wiskunde", "1A", "JAN", 2, "regulier"),
        Les("B", "nederlands", "1A", "JAN", 1, "regulier"),
    )
    data = _een_dag(lessen)
    resultaat = _solve_z4(data)
    assert resultaat.straf_per_regel == {"Z4": 0}
    laatste = next(t for t in resultaat.toewijzingen if t.tijdslot_id == 3)
    assert laatste.lesuur.vak == "nederlands"


def test_korte_dag_heeft_een_eigen_laatste_uur():
    data = _korte_woensdag()
    resultaat = _solve_z4(data)
    assert resultaat.straf_per_regel == {"Z4": 0}
    assert [t.tijdslot_id for t in resultaat.toewijzingen] == [4]


def test_onvermijdelijk_laatste_uur_wordt_gestraft():
    data = _een_dag((Les("A", "wiskunde", "1A", "JAN", 3, "regulier"),))
    resultaat = _solve_z4(data)
    assert resultaat.straf_per_regel == {"Z4": 2}
    assert tel_straf(data, resultaat.toewijzingen, ALLEEN_Z4, ZWAAR) == resultaat.straf_per_regel


def test_lege_lijst_geeft_geen_straf():
    data = _een_dag((Les("A", "wiskunde", "1A", "JAN", 3, "regulier"),))
    resultaat = _solve_z4(data, ())
    assert resultaat.straf_per_regel == {"Z4": 0}
    assert tel_per_regel(data, resultaat.toewijzingen)["Z4"] == 0


def test_checker_gelijk_aan_solver_op_klein_probleem(klein_probleem):
    resultaat = _solve_z4(klein_probleem)
    assert tel_straf(klein_probleem, resultaat.toewijzingen, ALLEEN_Z4, ZWAAR) == resultaat.straf_per_regel


def test_zware_vakken_uit_config(tmp_path):
    assert laad_instellingen(STANDAARD_CONFIG).zware_vakken == ("wiskunde",)
    pad = tmp_path / "c.toml"
    pad.write_text('zware_vakken = ["wiskunde", "frans"]\n', encoding="utf-8")
    assert laad_instellingen(pad).zware_vakken == ("wiskunde", "frans")
    pad.write_text("tijdslimiet_s = 5\n", encoding="utf-8")
    assert laad_instellingen(pad).zware_vakken == ()
