"""Tests voor de uitleg bij een onoplosbaar rooster.

Elke dataset komt zonder fouten door `valideer` en is toch onoplosbaar.
"""

from src.loader import maak_lesuren, valideer
from src.models import Instellingen, Leraar, Les, Lokaal, ProbleemData, Tijdslot
from src.solver import solve
from src.uitleg import minimale_oorzaak, verklaar

REGULIER = (Lokaal("R1", "Lokaal 1", "regulier"), Lokaal("R2", "Lokaal 2", "regulier"))
MET_LAB = (Lokaal("R1", "Lokaal 1", "regulier"), Lokaal("L1", "Lab", "lab"))


def _data(tijdslots, lokalen, leraren, lessen) -> ProbleemData:
    return ProbleemData(tuple(tijdslots), lokalen, tuple(leraren), tuple(lessen), maak_lesuren(tuple(lessen)))


def dataset_onbeschikbaarheid() -> ProbleemData:
    """Twee lessen van één klas, maar beide leraren kunnen alleen op uur 1."""
    slots = [Tijdslot(1, "maandag", 1), Tijdslot(2, "maandag", 2)]
    leraren = [Leraar("JAN", "Jan", 2, frozenset({2})), Leraar("AN", "An", 2, frozenset({2}))]
    lessen = [
        Les("1A-WIS", "wiskunde", "1A", "JAN", 1, "regulier"),
        Les("1A-NED", "nederlands", "1A", "AN", 1, "regulier"),
    ]
    return _data(slots, REGULIER, leraren, lessen)


def dataset_lokaaltype() -> ProbleemData:
    """Twee klassen, twee uur, een gewoon lokaal en een lab: de lessen botsen op de lokalen
    en op de leraren, dus alleen versoepelen van beide lokaaltypes helpt."""
    slots = [Tijdslot(1, "maandag", 1), Tijdslot(2, "maandag", 2)]
    leraren = [Leraar("JAN", "Jan", 2), Leraar("AN", "An", 2)]
    lessen = [
        Les("1A-BIO", "biologie", "1A", "JAN", 1, "lab"),
        Les("1A-WIS", "wiskunde", "1A", "AN", 1, "regulier"),
        Les("1B-BIO", "biologie", "1B", "AN", 1, "lab"),
        Les("1B-WIS", "wiskunde", "1B", "JAN", 1, "regulier"),
    ]
    return _data(slots, MET_LAB, leraren, lessen)


def dataset_maximum_per_dag() -> ProbleemData:
    """Jan mag 1 uur per dag, maar An kan alleen dinsdag: Jan moet twee uur op maandag geven."""
    slots = [Tijdslot(1, "maandag", 1), Tijdslot(2, "maandag", 2), Tijdslot(3, "dinsdag", 1)]
    leraren = [Leraar("JAN", "Jan", 1), Leraar("AN", "An", 3, frozenset({1, 2}))]
    lessen = [
        Les("1A-WIS", "wiskunde", "1A", "JAN", 2, "regulier"),
        Les("1A-NED", "nederlands", "1A", "AN", 1, "regulier"),
    ]
    return _data(slots, REGULIER, leraren, lessen)


def _onoplosbaar_zonder_validatiefout(data: ProbleemData) -> None:
    assert [m for m in valideer(data) if m.ernst == "fout"] == []
    assert solve(data, Instellingen(10)).status == "onoplosbaar"


def test_onbeschikbaarheid_wordt_als_oorzaak_genoemd():
    data = dataset_onbeschikbaarheid()
    _onoplosbaar_zonder_validatiefout(data)
    uitleg = verklaar(data)
    assert [regel for regel, _ in uitleg.oorzaken] == ["H6"]
    tekst = " ".join(uitleg.teksten)
    assert "Zonder de onbeschikbaarheid van" in tekst
    assert "maandag uur 2" in tekst  # blijkt uit de analyse: dat tijdslot lost het op


def test_lokaaltype_wordt_als_oorzaak_genoemd():
    data = dataset_lokaaltype()
    _onoplosbaar_zonder_validatiefout(data)
    uitleg = verklaar(data)
    # beide typen samen: met alleen lab versoepeld botsen de gewone lessen op het ene gewone lokaal
    assert uitleg.oorzaken == (("H5", "lab"), ("H5", "regulier"))
    assert uitleg.teksten[0].startswith("Meerdere regels samen")
    assert "type 'lab'" in uitleg.teksten[1] and "type 'regulier'" in uitleg.teksten[2]


def test_maximum_per_dag_wordt_als_oorzaak_genoemd():
    data = dataset_maximum_per_dag()
    _onoplosbaar_zonder_validatiefout(data)
    uitleg = verklaar(data)
    assert uitleg.oorzaken == (("H7", "JAN"),)
    assert "maximum van 1 uur per dag voor Jan" in uitleg.teksten[0]


def test_oorzaak_lost_het_probleem_echt_op():
    from src.uitleg import _oplosbaar

    for data in (dataset_onbeschikbaarheid(), dataset_lokaaltype(), dataset_maximum_per_dag()):
        oorzaken = minimale_oorzaak(data)
        assert oorzaken
        assert _oplosbaar(data, set(oorzaken), 10)
        for weg in oorzaken:  # minimaal: zonder één van de versoepelingen lukt het niet
            assert not _oplosbaar(data, set(oorzaken) - {weg}, 10)


def test_oplosbaar_probleem_heeft_geen_oorzaak_nodig(klein_probleem):
    assert minimale_oorzaak(klein_probleem) == ()
