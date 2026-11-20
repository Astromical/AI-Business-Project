"""Tests voor verder rekenen vanaf een bestaand rooster (de veilige versie)."""

from pathlib import Path

import pytest
from conftest import log_in_op_pagina
from streamlit.testing.v1 import AppTest

from src import service
from src import solver as solver_module
from src.checker import controleer
from src.loader import maak_lesuren
from src.models import (
    Instellingen, Leraar, Les, Lokaal, ProbleemData, Resultaat, Tijdslot, Toewijzing,
)
from src.solver import solve, verbeter_verder
from src.ui import ZACHTE_REGEL_NAMEN

ALLEEN_Z1 = {"Z1": 10}
ROOT = Path(__file__).resolve().parent.parent


def _een_dag() -> ProbleemData:
    """Eén klas met twee lesuren op een dag van 3 uur; uur 1 en 3 geeft een tussenuur."""
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    lessen = (Les("A", "wis", "1A", "JAN", 2, "regulier"),)
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    return ProbleemData(slots, lokalen, (Leraar("JAN", "Jan", 3),), lessen, maak_lesuren(lessen))


def _met_tussenuur(data: ProbleemData) -> tuple[Toewijzing, ...]:
    """Een geldig rooster met een tussenuur (uur 1 en 3)."""
    return (Toewijzing(data.lesuren[0], 1, "R1"), Toewijzing(data.lesuren[1], 3, "R1"))


def test_verder_rekenen_vindt_een_beter_rooster():
    data = _een_dag()
    resultaat = verbeter_verder(data, _met_tussenuur(data), Instellingen(10, ALLEEN_Z1))
    assert resultaat.strafscore == 0
    assert resultaat.status == "optimaal"
    assert controleer(data, resultaat.toewijzingen) == []


def test_veilige_versie_blijft_als_de_solver_niets_vindt(monkeypatch):
    """Het verbeteren (tijdslimiet 10 s) mislukt bewust; waardeer (30 s) werkt gewoon."""
    echte_los_op = solver_module._los_op

    def los_op(model, tijdslimiet_s, *args):
        solver, status = echte_los_op(model, tijdslimiet_s, *args)
        return solver, "geen_oplossing_binnen_tijd" if tijdslimiet_s == 10 else status

    monkeypatch.setattr(solver_module, "_los_op", los_op)
    data = _een_dag()
    start = _met_tussenuur(data)
    resultaat = verbeter_verder(data, start, Instellingen(10, ALLEEN_Z1))
    assert resultaat.toewijzingen == start
    assert resultaat.strafscore == 10
    assert resultaat.status == "geldig"


def test_nooit_een_slechter_rooster(monkeypatch):
    data = _een_dag()
    start = _met_tussenuur(data)
    slechter = Resultaat("geldig", start, 1.0, 999, {"Z1": 999})
    monkeypatch.setattr(solver_module, "_verbeter", lambda *args: slechter)
    resultaat = verbeter_verder(data, start, Instellingen(10, ALLEEN_Z1))
    assert resultaat.strafscore == 10
    assert resultaat.straf_per_regel == {"Z1": 10}


def test_rooster_zonder_strafpunten_is_al_optimaal(monkeypatch):
    data = _een_dag()
    start = (Toewijzing(data.lesuren[0], 1, "R1"), Toewijzing(data.lesuren[1], 2, "R1"))
    monkeypatch.setattr(solver_module, "_verbeter", lambda *args: pytest.fail("geen fase 2 nodig"))
    resultaat = verbeter_verder(data, start, Instellingen(10, ALLEEN_Z1))
    assert resultaat.status == "optimaal"
    assert resultaat.toewijzingen == start


def test_onvolledig_rooster_geeft_een_fout():
    data = _een_dag()
    with pytest.raises(ValueError):
        verbeter_verder(data, _met_tussenuur(data)[:1], Instellingen(10, ALLEEN_Z1))


def test_service_onthoudt_de_vorige_strafscore():
    data = _een_dag()
    oud = service.Berekening(Resultaat("geldig", _met_tussenuur(data), 1.0), (), data=data)
    assert service.kan_verder(oud)
    nieuw = service.reken_verder(data, oud, Instellingen(10, ALLEEN_Z1))
    assert nieuw.vorige_strafscore == 10
    assert nieuw.resultaat.strafscore == 0
    assert nieuw.tellingen["Z1"] == 0
    assert not service.kan_verder(nieuw)  # nu bewezen optimaal


def test_kan_niet_verder_zonder_geldig_rooster():
    leeg = service.Berekening(Resultaat("onoplosbaar", (), 1.0), ())
    assert not service.kan_verder(leeg)


@pytest.fixture
def pad(tmp_path):
    return str(tmp_path / "rooster.db")


def test_pagina_reken_verder_vanaf_bewaard_rooster(pad):
    service.vul_voorbeeld(pad, "voorbeeld")
    data, _ = service.laad(pad)
    # een geldig rooster zonder zachte regels: heeft bijna zeker strafpunten
    zonder_zachte_regels = Instellingen(10, dict.fromkeys(ZACHTE_REGEL_NAMEN, 0))
    service.bewaar(pad, solve(data, zonder_zachte_regels).toewijzingen)
    at = AppTest.from_file(str(ROOT / "paginas" / "2_Rooster.py"), default_timeout=120)
    at = log_in_op_pagina(at, pad).run()  # de pagina Rooster vraagt een login
    at = next(b for b in at.button if b.label == "Verder verbeteren").click().run()
    assert not at.exception
    meldingen = [m.value for m in at.success] + [m.value for m in at.info]
    assert any("strafscore" in tekst for tekst in meldingen)
    assert {m.label: m.value for m in at.metric}["Schendingen"] == "0"
