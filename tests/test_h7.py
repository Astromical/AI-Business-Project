"""Tests voor H7 (maximum uren per dag)."""

from collections import Counter

from src.loader import maak_lesuren, valideer
from src.models import Leraar, Les, Lokaal, ProbleemData, Tijdslot
from src.models import Instellingen
from src.solver import solve

DAGEN = ("maandag", "dinsdag", "woensdag")


def _data(maximum: int, uren: int) -> ProbleemData:
    """Eén leraar met `uren` lesuren in een week van 3 dagen x 3 uur."""
    slots = tuple(Tijdslot(i * 3 + u, dag, u) for i, dag in enumerate(DAGEN) for u in (1, 2, 3))
    leraren = (Leraar("JAN", "Jan", maximum),)
    lessen = (Les("A", "wis", "1A", "JAN", uren, "regulier"),)
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    return ProbleemData(slots, lokalen, leraren, lessen, maak_lesuren(lessen))


def _per_dag(data, resultaat):
    return Counter(data.tijdslot_per_id[t.tijdslot_id].dag for t in resultaat.toewijzingen)


def test_h7_spreidt_lesuren_over_drie_dagen():
    data = _data(maximum=1, uren=3)
    resultaat = solve(data, Instellingen(10))
    assert _per_dag(data, resultaat) == {dag: 1 for dag in DAGEN}


def test_h7_faalt_zonder_regel():
    # 4 uren met maximum 1 per dag over 3 dagen kan niet; zonder H7 wel
    data = _data(maximum=1, uren=4)
    assert solve(data, Instellingen(10)).status == "onoplosbaar"
    zonder = solve(data, Instellingen(10), uitgeschakeld=frozenset({"H7"}))
    assert zonder.status in ("optimaal", "geldig")


def test_h7_respecteert_hoger_maximum():
    data = _data(maximum=2, uren=5)
    resultaat = solve(data, Instellingen(10))
    assert max(_per_dag(data, resultaat).values()) <= 2


def test_valideer_leraar_boven_weekmaximum():
    meldingen = valideer(_data(maximum=1, uren=4))
    assert any("maximaal 1 uur" in m.tekst and "Jan" in m.tekst for m in meldingen)


def test_valideer_geen_melding_als_maximum_genoeg_is():
    assert not any("maximaal" in m.tekst for m in valideer(_data(maximum=2, uren=5)))
