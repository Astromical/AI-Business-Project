"""Gedeelde test-fixtures, rechtstreeks gebouwd met dataclasses."""

import pytest

from src.models import Les, Lesuur, Leraar, Lokaal, ProbleemData, Tijdslot, Toewijzing


def maak_lesuren(lessen: tuple[Les, ...]) -> tuple[Lesuur, ...]:
    """Zet elke les om in aantal_per_week lesuren met volgnummer 1, 2, ..."""
    return tuple(
        Lesuur(les.id, nr, les.vak, les.klas, les.leraar_id, les.lokaaltype)
        for les in lessen
        for nr in range(1, les.aantal_per_week + 1)
    )


def maak_tijdslots(dagen: tuple[str, ...], uren: int) -> tuple[Tijdslot, ...]:
    """Maak tijdslots met oplopend id voor elke dag en elk uur."""
    return tuple(
        Tijdslot(i * uren + u, dag, u)
        for i, dag in enumerate(dagen)
        for u in range(1, uren + 1)
    )


def _basis() -> tuple[tuple[Tijdslot, ...], tuple[Lokaal, ...], tuple[Leraar, ...]]:
    """Tijdslots, lokalen en leraren die beide fixtures delen."""
    tijdslots = maak_tijdslots(("maandag", "dinsdag"), 3)
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"), Lokaal("L1", "Lab", "lab"))
    leraren = (Leraar("JAN", "Jan", 3), Leraar("AN", "An", 3))
    return tijdslots, lokalen, leraren


@pytest.fixture
def klein_probleem() -> ProbleemData:
    """Voorbeeld: 2 klassen, 2 leraren, 2 lokalen, 2 dagen x 3 uur, 8 lesuren."""
    tijdslots, lokalen, leraren = _basis()
    lessen = (
        Les("1A-WIS", "wiskunde", "1A", "JAN", 2, "regulier"),
        Les("1A-NED", "nederlands", "1A", "AN", 1, "regulier"),
        Les("1A-BIO", "biologie", "1A", "AN", 1, "lab"),
        Les("1B-WIS", "wiskunde", "1B", "JAN", 2, "regulier"),
        Les("1B-BIO", "biologie", "1B", "AN", 2, "lab"),
    )
    return ProbleemData(tijdslots, lokalen, leraren, lessen, maak_lesuren(lessen))


@pytest.fixture
def klein_rooster(klein_probleem: ProbleemData) -> tuple[Toewijzing, ...]:
    """Een met de hand gemaakt, geldig rooster voor klein_probleem."""
    plaatsing = {
        ("1A-WIS", 1): (1, "R1"),
        ("1A-WIS", 2): (2, "R1"),
        ("1A-NED", 1): (3, "R1"),
        ("1A-BIO", 1): (6, "L1"),
        ("1B-WIS", 1): (4, "R1"),
        ("1B-WIS", 2): (5, "R1"),
        ("1B-BIO", 1): (1, "L1"),
        ("1B-BIO", 2): (2, "L1"),
    }
    return tuple(
        Toewijzing(u, *plaatsing[u.les_id, u.volgnummer]) for u in klein_probleem.lesuren
    )


@pytest.fixture
def onmogelijk_probleem() -> ProbleemData:
    """Voorbeeld: klas 1A heeft 7 lesuren, maar er zijn maar 6 tijdslots."""
    tijdslots, lokalen, leraren = _basis()
    lessen = (
        Les("1A-WIS", "wiskunde", "1A", "JAN", 4, "regulier"),
        Les("1A-BIO", "biologie", "1A", "AN", 3, "lab"),
    )
    return ProbleemData(tijdslots, lokalen, leraren, lessen, maak_lesuren(lessen))


def log_in_op_pagina(at, pad: str, rol: str = "roostermaker", leraar_id: str | None = None):
    """Geef een AppTest een ingelogde gebruiker met deze rol in de database op pad."""
    from src import service

    naam = f"test_{rol}"
    if service.zoek_gebruiker(pad, naam) is None:
        service.maak_gebruiker(pad, naam, "wachtwoord123", rol, leraar_id)
    at.session_state["pad"] = pad
    at.session_state["gebruiker"] = naam
    return at
