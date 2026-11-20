"""Tests voor laden en valideren."""

from dataclasses import replace

import pytest

from src.db import maak_schema, verbind
from src.loader import laad_probleem, maak_lesuren, valideer
from src.models import Leraar, Les, Lokaal
from src.seed import seed


@pytest.fixture
def con(tmp_path):
    """Database met schema in een tijdelijke map."""
    verbinding = verbind(tmp_path / "test.db")
    maak_schema(verbinding)
    yield verbinding
    verbinding.close()


def _met_lessen(data, lessen):
    """Kopie van data met andere lessen (en de bijbehorende lesuren)."""
    return replace(data, lessen=lessen, lesuren=maak_lesuren(lessen))


def _teksten(meldingen):
    return [m.tekst for m in meldingen]


def test_voorbeelddata_laadt_zonder_fouten(con):
    seed(con)
    data = laad_probleem(con)
    assert len(data.lesuren) == 144
    assert len(data.klassen) == 6
    assert len(data.leraren) == 10
    assert len(data.lokalen) == 7
    assert len(data.tijdslots) == 30
    assert [m for m in valideer(data) if m.ernst == "fout"] == []
    assert any(l.onbeschikbaar for l in data.leraren)


def test_lesuren_hebben_volgnummers(con):
    seed(con)
    data = laad_probleem(con)
    nummers = [u.volgnummer for u in data.lesuren if u.les_id == "1A-WIS"]
    assert nummers == [1, 2, 3, 4]


def test_klein_probleem_is_geldig(klein_probleem):
    assert valideer(klein_probleem) == []


def test_melding_klas_te_veel_lesuren(onmogelijk_probleem):
    meldingen = valideer(onmogelijk_probleem)
    assert any("Klas 1A heeft 7 lesuren" in t for t in _teksten(meldingen))
    assert all(m.ernst == "fout" for m in meldingen)


def test_melding_leraar_te_veel_lesuren(klein_probleem):
    leraren = (replace(klein_probleem.leraren[0], onbeschikbaar=frozenset(range(5))),
               klein_probleem.leraren[1])
    data = replace(klein_probleem, leraren=leraren)
    meldingen = valideer(data)
    assert any("Leraar Jan" in t and "beschikbaar" in t for t in _teksten(meldingen))


def test_melding_geen_lokaal_van_type(klein_probleem):
    data = replace(klein_probleem, lokalen=(Lokaal("R1", "Lokaal 1", "regulier"),))
    meldingen = valideer(data)
    assert any("geen lokaal van het type 'lab'" in t for t in _teksten(meldingen))


def test_melding_te_weinig_plaatsen_per_type(klein_probleem):
    lessen = (
        Les("A", "bio", "1A", "JAN", 3, "lab"),
        Les("B", "bio", "1B", "AN", 3, "lab"),
        Les("C", "bio", "2A", "JAN", 1, "lab"),
    )
    # 7 labuuren, maar 1 lab x 6 tijdslots = 6 plaatsen
    meldingen = valideer(_met_lessen(klein_probleem, lessen))
    assert any("'lab'" in t and "6 plaatsen" in t for t in _teksten(meldingen))


def test_melding_geen_tijdslots(klein_probleem):
    meldingen = valideer(replace(klein_probleem, tijdslots=()))
    assert _teksten(meldingen) == ["Er zijn geen tijdslots. Maak eerst tijdslots aan."]


def test_melding_geen_lessen(klein_probleem):
    meldingen = valideer(_met_lessen(klein_probleem, ()))
    assert _teksten(meldingen) == ["Er zijn geen lessen om in te plannen."]


def test_leraar_zonder_lessen_geeft_geen_melding(klein_probleem):
    leraren = klein_probleem.leraren + (Leraar("X", "Xavier", 2),)
    assert valideer(replace(klein_probleem, leraren=leraren)) == []


def test_melding_leraar_maximum_en_onbeschikbaarheid_samen(klein_probleem):
    # Jan: 4 lesuren, maximum 2 per dag, op maandag alleen uur 3 vrij.
    # Apart passen beide grenzen (4 <= 2 x 2 dagen, 4 <= 4 vrije tijdslots),
    # maar samen kan Jan maar 1 + 2 = 3 uur geven.
    jan = replace(klein_probleem.leraren[0], max_uren_per_dag=2, onbeschikbaar=frozenset({1, 2}))
    data = replace(klein_probleem, leraren=(jan, klein_probleem.leraren[1]))
    teksten = _teksten(valideer(data))
    assert any("Leraar Jan" in t and "samen maar 3 uur" in t for t in teksten)
    assert len([t for t in teksten if "Leraar Jan" in t]) == 1
