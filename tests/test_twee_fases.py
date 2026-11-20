"""Tests voor het oplossen in twee fases: eerst een werkbaar rooster, dan verbeteren."""

import pytest

from src import solver as solver_module
from src.checker import controleer, tel_tussenuren
from src.db import maak_schema, verbind
from src.loader import laad_probleem, maak_lesuren
from src.models import Instellingen, Leraar, Les, Lokaal, ProbleemData, Tijdslot
from src.seed import seed
from src.solver import bouw_model, solve, waardeer


def _een_dag_met_tussenuur() -> ProbleemData:
    """Eén klas met twee lessen; de leraar kan niet op uur 2, dus er is altijd een tussenuur."""
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    leraren = (Leraar("JAN", "Jan", 3, frozenset({2})),)
    lessen = (Les("A", "wis", "1A", "JAN", 2, "regulier"),)
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    return ProbleemData(slots, lokalen, leraren, lessen, maak_lesuren(lessen))


def test_waardeer_telt_hetzelfde_als_de_checker():
    data = _een_dag_met_tussenuur()
    _, x, _ = bouw_model(data)
    gepland = {(0, 1), (1, 3)}
    oplossing = {sleutel: int(sleutel in gepland) for sleutel in x}
    straf = waardeer(data, frozenset(), {"Z1": 10}, oplossing)
    assert straf == {"Z1": 10}


def test_rooster_uit_fase_1_blijft_als_fase_2_niets_vindt(klein_probleem, monkeypatch):
    """Fase 2 wordt hier bewust onderbroken (de tweede aanroep van CP-SAT 'vindt niets'),
    om de terugvaloptie te testen: het rooster uit fase 1 moet dan getoond worden."""
    echte_los_op = solver_module._los_op
    aanroepen = []

    def los_op_met_mislukte_fase_2(model, tijdslimiet_s, *args):
        aanroepen.append(tijdslimiet_s)
        solver, status = echte_los_op(model, tijdslimiet_s, *args)
        if len(aanroepen) == 2:  # fase 2
            return solver, "geen_oplossing_binnen_tijd"
        return solver, status

    monkeypatch.setattr(solver_module, "_los_op", los_op_met_mislukte_fase_2)
    resultaat = solve(klein_probleem, Instellingen(10, {"Z1": 10}))
    assert resultaat.status == "geldig"
    assert len(resultaat.toewijzingen) == len(klein_probleem.lesuren)
    assert controleer(klein_probleem, resultaat.toewijzingen) == []
    gaten = sum(tel_tussenuren(klein_probleem, resultaat.toewijzingen).values())
    assert resultaat.straf_per_regel == {"Z1": 10 * gaten}


def test_rooster_blijft_als_ook_de_strafpunten_niet_lukken(klein_probleem, monkeypatch):
    """Fase 2 en het uitrekenen van de strafpunten mislukken allebei: geen crash, het
    rooster uit fase 1 blijft staan en de strafscore is onbekend (None)."""
    echte_los_op = solver_module._los_op
    aanroepen = []

    def los_op_alleen_fase_1(model, tijdslimiet_s, *args):
        aanroepen.append(tijdslimiet_s)
        solver, status = echte_los_op(model, tijdslimiet_s, *args)
        return solver, status if len(aanroepen) == 1 else "geen_oplossing_binnen_tijd"

    monkeypatch.setattr(solver_module, "_los_op", los_op_alleen_fase_1)
    monkeypatch.setattr(solver_module, "_vast_rooster", lambda *args: (None, None, 0.0))
    resultaat = solve(klein_probleem, Instellingen(10))
    assert len(aanroepen) == 2  # fase 1 en fase 2 (zonder hint)
    assert resultaat.status == "geldig"
    assert controleer(klein_probleem, resultaat.toewijzingen) == []
    assert resultaat.strafscore is None
    assert resultaat.straf_per_regel == {}


def test_zonder_zachte_regel_alleen_fase_1(klein_probleem, monkeypatch):
    aanroepen = []
    echte_los_op = solver_module._los_op
    monkeypatch.setattr(
        solver_module, "_los_op", lambda m, t, *a: aanroepen.append(t) or echte_los_op(m, t, *a)
    )
    resultaat = solve(klein_probleem, Instellingen(10, {"Z1": 0}))
    assert resultaat.status in ("optimaal", "geldig")
    assert len(aanroepen) == 1


def test_tijdslimiet_loopt_pas_na_een_geldig_rooster(klein_probleem, monkeypatch):
    """Fase 1 krijgt de zoekgrens, fase 2 de volledige tijdslimiet (niet wat er overblijft)."""
    limieten = []
    echte_los_op = solver_module._los_op
    monkeypatch.setattr(
        solver_module, "_los_op", lambda m, t, *a: limieten.append(t) or echte_los_op(m, t, *a)
    )
    resultaat = solve(klein_probleem, Instellingen(7, {"Z1": 10}, max_tijd_zoeken_s=40))
    assert limieten == [40, 7]
    assert 0 < resultaat.tijd_zoeken_s <= resultaat.oplostijd_s


def test_zoekgrens_bereikt_geeft_geen_rooster(monkeypatch, klein_probleem):
    """Vindt fase 1 niets binnen de zoekgrens, dan is er geen rooster (en geen fase 2)."""
    echte_los_op = solver_module._los_op
    monkeypatch.setattr(
        solver_module,
        "_los_op",
        lambda m, t, *a: (echte_los_op(m, t, *a)[0], "geen_oplossing_binnen_tijd"),
    )
    resultaat = solve(klein_probleem, Instellingen(10))
    assert resultaat.status == "geen_oplossing_binnen_tijd"
    assert resultaat.toewijzingen == ()


@pytest.fixture(scope="module")
def groot(tmp_path_factory):
    con = verbind(tmp_path_factory.mktemp("groot") / "g.db")
    maak_schema(con)
    seed(con, "groot")
    data = laad_probleem(con)
    con.close()
    return data


def test_grote_variant_geeft_binnen_de_limiet_een_werkbaar_rooster(groot):
    resultaat = solve(groot, Instellingen(30, {"Z1": 10}))
    print(f"groot: {resultaat.status}, {resultaat.oplostijd_s:.1f} s, strafscore {resultaat.strafscore}")
    assert resultaat.status in ("optimaal", "geldig")
    assert len(resultaat.toewijzingen) == 512
    assert controleer(groot, resultaat.toewijzingen) == []
    gaten = sum(tel_tussenuren(groot, resultaat.toewijzingen).values())
    assert resultaat.strafscore == 10 * gaten
