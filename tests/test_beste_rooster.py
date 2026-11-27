"""Tests voor 'Verder verbeteren': het beste geldige rooster en de bestaande data blijven bewaard."""

import sqlite3

import pytest

from src import service
from src import solver as solver_module
from src.checker import controleer
from src.loader import maak_lesuren
from src.models import Instellingen, Leraar, Les, Lokaal, ProbleemData, Resultaat, Tijdslot, Toewijzing

ALLEEN_Z1 = {"Z1": 10}


def _een_dag() -> ProbleemData:
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    lessen = (Les("A", "wis", "1A", "JAN", 2, "regulier"),)
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    return ProbleemData(slots, lokalen, (Leraar("JAN", "Jan", 3),), lessen, maak_lesuren(lessen))


def _met_tussenuur(data):
    return (Toewijzing(data.lesuren[0], 1, "R1"), Toewijzing(data.lesuren[1], 3, "R1"))


def _berekening(data, rooster):
    return service.Berekening(Resultaat("geldig", rooster, 1.0, 10, {"Z1": 10}), (), data=data,
                              gewichten=dict(ALLEEN_Z1))


def test_slechtere_poging_overschrijft_het_rooster_niet(monkeypatch):
    """Meldt de solver ten onrechte strafscore 0, dan telt de checker na en blijft het oude staan."""
    data = _een_dag()
    oud = _met_tussenuur(data)
    # hetzelfde rooster in een andere volgorde: echt 10 strafpunten, maar gemeld als 0
    nep = Resultaat("geldig", oud[::-1], 2.0, 0, {"Z1": 0})
    monkeypatch.setattr(service, "verbeter_verder", lambda *a, **k: nep)
    nieuw = service.reken_verder(data, _berekening(data, oud), Instellingen(5, ALLEEN_Z1))
    assert set(nieuw.resultaat.toewijzingen) == set(oud)
    assert nieuw.resultaat.strafscore == 10
    assert nieuw.geschiedenis[-1].verbeterd is False


def test_ongeldig_resultaat_wordt_nooit_overgenomen(monkeypatch):
    data = _een_dag()
    oud = _met_tussenuur(data)
    dubbel = (Toewijzing(data.lesuren[0], 1, "R1"), Toewijzing(data.lesuren[1], 1, "R1"))
    monkeypatch.setattr(
        service, "verbeter_verder", lambda *a, **k: Resultaat("geldig", dubbel, 1.0, 0, {"Z1": 0})
    )
    nieuw = service.reken_verder(data, _berekening(data, oud), Instellingen(5, ALLEEN_Z1))
    assert nieuw.resultaat.toewijzingen == oud
    assert nieuw.schendingen == ()


def test_slechtere_poging_laat_database_en_gegevens_staan(tmp_path, monkeypatch):
    pad = str(tmp_path / "rooster.db")
    service.vul_voorbeeld(pad, "voorbeeld")
    data, _ = service.laad(pad)
    instellingen = Instellingen(2, ALLEEN_Z1, num_workers=1)
    eerste = service.bereken(data, Instellingen(1, {"Z1": 0}, num_workers=1))
    service.bewaar(pad, eerste.resultaat.toewijzingen)
    with sqlite3.connect(pad) as con:
        lessen_voor = con.execute("SELECT * FROM les ORDER BY id").fetchall()
    slechter = Resultaat("geldig", eerste.resultaat.toewijzingen, 1.0, 10**6, {"Z1": 10**6})
    monkeypatch.setattr(solver_module, "_verbeter", lambda *args: slechter)
    bewaarde = service.bewaard_rooster(pad, data, instellingen)
    nieuw = service.reken_verder(data, bewaarde, instellingen)
    assert set(nieuw.resultaat.toewijzingen) == set(eerste.resultaat.toewijzingen)
    assert controleer(data, nieuw.resultaat.toewijzingen) == []
    # het rooster in de database en de gegevens zijn ongewijzigd
    na = service.bewaard_rooster(pad, data, instellingen)
    assert set(na.resultaat.toewijzingen) == set(eerste.resultaat.toewijzingen)
    with sqlite3.connect(pad) as con:
        assert con.execute("SELECT * FROM les ORDER BY id").fetchall() == lessen_voor


def test_geschiedenis_toont_score_voor_en_na():
    data = _een_dag()
    eerste = service.Berekening(
        Resultaat("geldig", _met_tussenuur(data), 1.0, 10, {"Z1": 10}), (), data=data,
        geschiedenis=(service.Poging("berekenen", None, 10, 1.0, True),),
    )
    nieuw = service.reken_verder(data, eerste, Instellingen(5, ALLEEN_Z1))
    assert [p.soort for p in nieuw.geschiedenis] == ["berekenen", "verder verbeteren"]
    laatste = nieuw.geschiedenis[-1]
    assert (laatste.voor, laatste.na, laatste.verbeterd) == (10, 0, True)


@pytest.mark.parametrize("nieuw_score, beter", [(5, True), (10, False), (20, False)])
def test_is_beter_vergelijkt_strafscores(nieuw_score, beter):
    data = _een_dag()
    rooster = _met_tussenuur(data)

    def b(score):
        return service.Berekening(Resultaat("geldig", rooster, 1.0, score), (), data=data, gewichten={"Z1": 10})

    assert service.is_beter(b(nieuw_score), b(10)) is beter


def test_rooster_met_schendingen_is_nooit_beter():
    data = _een_dag()
    rooster = _met_tussenuur(data)
    fout = service.Berekening(Resultaat("geldig", rooster, 1.0, 0), (object(),), data=data)
    goed = service.Berekening(Resultaat("geldig", rooster, 1.0, 50), (), data=data)
    assert not service.is_beter(fout, goed)
    assert service.is_beter(goed, fout)


def test_pagina_toont_strafuitleg_en_geschiedenis(tmp_path):
    """Pagina Rooster: harde en zachte regels apart, uitleg bij de strafpunten, en na
    Verder verbeteren de geschiedenis met de score voor en na."""
    from pathlib import Path

    from conftest import log_in_op_pagina
    from streamlit.testing.v1 import AppTest

    from src.solver import GEEN_ZACHTE_REGELS, solve

    pad = str(tmp_path / "rooster.db")
    service.vul_voorbeeld(pad, "voorbeeld")
    data, _ = service.laad(pad)
    service.bewaar(pad, solve(data, Instellingen(1, dict(GEEN_ZACHTE_REGELS))).toewijzingen)
    pagina = Path(__file__).resolve().parent.parent / "paginas" / "2_Rooster.py"
    at = log_in_op_pagina(AppTest.from_file(str(pagina), default_timeout=120), pad).run()
    assert not at.exception
    assert any("Harde regels" in m.value for m in at.success)
    assert "Waar komen de strafpunten vandaan?" in [e.label for e in at.expander]
    at = next(b for b in at.button if b.label == "Verder verbeteren").click().run()
    assert not at.exception
    assert "Geschiedenis van de strafscore" in [e.label for e in at.expander]
