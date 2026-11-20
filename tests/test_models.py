"""Tests voor de domeinklassen en de opzoekingen op ProbleemData."""

import dataclasses

import pytest

from src.models import (
    Instellingen,
    Leraar,
    Lokaal,
    ProbleemData,
    Resultaat,
    Tijdslot,
)


def test_klassen_gesorteerd_zonder_dubbels(klein_probleem: ProbleemData) -> None:
    """klassen geeft elke klas één keer, gesorteerd."""
    assert klein_probleem.klassen == ("1A", "1B")


def test_dagen_in_weekvolgorde() -> None:
    """dagen volgt de weekvolgorde, niet de volgorde van de tijdslots."""
    slots = (Tijdslot(1, "vrijdag", 1), Tijdslot(2, "maandag", 1))
    data = ProbleemData(slots, (), (), (), ())
    assert data.dagen == ("maandag", "vrijdag")


def test_uren_per_dag_met_kortere_dag() -> None:
    """uren_per_dag telt de tijdslots per dag, ook als een dag korter is."""
    slots = (
        Tijdslot(1, "maandag", 1),
        Tijdslot(2, "maandag", 2),
        Tijdslot(3, "woensdag", 1),
    )
    data = ProbleemData(slots, (), (), (), ())
    assert data.uren_per_dag == {"maandag": 2, "woensdag": 1}


def test_klein_probleem_afmetingen(klein_probleem: ProbleemData) -> None:
    """De fixture heeft de afgesproken omvang."""
    assert len(klein_probleem.tijdslots) == 6
    assert len(klein_probleem.lokalen) == 2
    assert len(klein_probleem.leraren) == 2
    assert len(klein_probleem.lesuren) == 8
    assert klein_probleem.uren_per_dag == {"maandag": 3, "dinsdag": 3}


def test_opzoekingen_per_id(klein_probleem: ProbleemData) -> None:
    """De dictionaries vinden elk object terug op zijn id."""
    assert klein_probleem.tijdslot_per_id[4] == Tijdslot(4, "dinsdag", 1)
    assert klein_probleem.lokaal_per_id["L1"].type == "lab"
    assert klein_probleem.leraar_per_id["AN"].naam == "An"
    assert klein_probleem.les_per_id["1B-BIO"].aantal_per_week == 2
    assert set(klein_probleem.les_per_id) == {les.id for les in klein_probleem.lessen}


def test_lesuren_volgnummers(klein_probleem: ProbleemData) -> None:
    """Elke les geeft lesuren met volgnummer 1 tot aantal_per_week."""
    for les in klein_probleem.lessen:
        nummers = [u.volgnummer for u in klein_probleem.lesuren if u.les_id == les.id]
        assert nummers == list(range(1, les.aantal_per_week + 1))


def test_onmogelijk_probleem_te_veel_lesuren(onmogelijk_probleem: ProbleemData) -> None:
    """Klas 1A heeft meer lesuren dan er tijdslots zijn."""
    lesuren_1a = [u for u in onmogelijk_probleem.lesuren if u.klas == "1A"]
    assert len(lesuren_1a) > len(onmogelijk_probleem.tijdslots)


def test_dataclasses_zijn_frozen() -> None:
    """Domeinobjecten zijn onveranderlijk."""
    lokaal = Lokaal("R1", "Lokaal 1", "regulier")
    with pytest.raises(dataclasses.FrozenInstanceError):
        lokaal.naam = "Ander"  # type: ignore[misc]


def test_standaardwaarden() -> None:
    """Leraar, Resultaat en Instellingen hebben bruikbare standaardwaarden."""
    assert Leraar("X", "X", 4).onbeschikbaar == frozenset()
    resultaat = Resultaat("onoplosbaar", (), 0.1)
    assert resultaat.strafscore == 0 and resultaat.straf_per_regel == {}
    assert Instellingen().tijdslimiet_s == 30
    assert Instellingen().gewichten["Z1"] == 10
