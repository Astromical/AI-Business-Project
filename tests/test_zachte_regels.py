"""Tests voor de gedeelde afhandeling van zachte regels (S4.1)."""

from src import solver as solver_module
from src.checker import tel_straf
from src.models import STANDAARD_GEWICHTEN, Instellingen
from src.solver import GEEN_ZACHTE_REGELS, ZACHTE_REGELS, actieve_regels, solve
from src.uitleg import GEEN_ZACHTE_REGELS as UITLEG_GEEN


def test_geen_zachte_regels_zet_alles_uit():
    assert GEEN_ZACHTE_REGELS == dict.fromkeys(STANDAARD_GEWICHTEN, 0)
    assert UITLEG_GEEN is GEEN_ZACHTE_REGELS
    assert actieve_regels(GEEN_ZACHTE_REGELS) == []


def test_actieve_regels_alleen_gebouwd_en_gewicht_boven_nul():
    assert actieve_regels({"Z1": 3, "ONBEKEND": 5}) == ["Z1"]
    assert actieve_regels({}) == []
    assert set(actieve_regels(STANDAARD_GEWICHTEN)) == set(ZACHTE_REGELS)


def test_alle_gewichten_nul_alleen_fase_1(klein_probleem, monkeypatch):
    aanroepen = []
    echte_los_op = solver_module._los_op
    monkeypatch.setattr(
        solver_module, "_los_op", lambda m, t, *a: aanroepen.append(t) or echte_los_op(m, t, *a)
    )
    resultaat = solve(klein_probleem, Instellingen(10, dict(GEEN_ZACHTE_REGELS)))
    assert len(aanroepen) == 1
    assert resultaat.straf_per_regel == {}
    assert resultaat.oplostijd_s == resultaat.tijd_zoeken_s


def test_tel_straf_gelijk_aan_solver(klein_probleem):
    gewichten = dict(STANDAARD_GEWICHTEN)
    resultaat = solve(klein_probleem, Instellingen(10, gewichten))
    assert tel_straf(klein_probleem, resultaat.toewijzingen, gewichten) == resultaat.straf_per_regel


def test_tel_straf_slaat_gewicht_nul_over(klein_rooster, klein_probleem):
    assert tel_straf(klein_probleem, klein_rooster, {"Z1": 0}) == {}
    assert set(tel_straf(klein_probleem, klein_rooster, {"Z1": 4})) == {"Z1"}
