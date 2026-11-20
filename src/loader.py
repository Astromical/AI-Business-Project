"""Database -> ProbleemData en validatie van de invoer."""

from __future__ import annotations

import sqlite3
from collections import Counter

from src.models import (
    Leraar,
    Les,
    Lesuur,
    Lokaal,
    Melding,
    ProbleemData,
    Tijdslot,
)


def maak_lesuren(lessen: tuple[Les, ...]) -> tuple[Lesuur, ...]:
    """Zet elke les om in aantal_per_week lesuren met volgnummer 1, 2, ..."""
    return tuple(
        Lesuur(les.id, nr, les.vak, les.klas, les.leraar_id, les.lokaaltype)
        for les in lessen
        for nr in range(1, les.aantal_per_week + 1)
    )


def laad_probleem(con: sqlite3.Connection) -> ProbleemData:
    """Lees de database in als ProbleemData."""
    tijdslots = tuple(
        Tijdslot(*rij) for rij in con.execute("SELECT id, dag, uur FROM tijdslot ORDER BY id")
    )
    lokalen = tuple(
        Lokaal(*rij) for rij in con.execute("SELECT id, naam, type FROM lokaal ORDER BY id")
    )
    onbeschikbaar: dict[str, set[int]] = {}
    for leraar_id, tijdslot_id in con.execute("SELECT leraar_id, tijdslot_id FROM onbeschikbaar"):
        onbeschikbaar.setdefault(leraar_id, set()).add(tijdslot_id)
    leraren = tuple(
        Leraar(lid, naam, maximum, frozenset(onbeschikbaar.get(lid, ())))
        for lid, naam, maximum in con.execute(
            "SELECT id, naam, max_uren_per_dag FROM leraar ORDER BY id"
        )
    )
    lessen = tuple(
        Les(*rij)
        for rij in con.execute(
            "SELECT id, vak, klas, leraar_id, aantal_per_week, lokaaltype FROM les ORDER BY id"
        )
    )
    return ProbleemData(tijdslots, lokalen, leraren, lessen, maak_lesuren(lessen))


def valideer(data: ProbleemData) -> list[Melding]:
    """Vind vooraf problemen die een rooster onmogelijk maken, in het Nederlands."""
    meldingen: list[Melding] = []
    if not data.tijdslots:
        meldingen.append(Melding("fout", "Er zijn geen tijdslots. Maak eerst tijdslots aan."))
    if not data.lessen:
        meldingen.append(Melding("fout", "Er zijn geen lessen om in te plannen."))
    if meldingen:
        return meldingen
    meldingen += _controleer_klassen(data)
    meldingen += _controleer_leraren(data)
    meldingen += _controleer_lokalen(data)
    return meldingen


def _controleer_klassen(data: ProbleemData) -> list[Melding]:
    """Een klas mag niet meer lesuren hebben dan er tijdslots zijn."""
    aantal = Counter(uur.klas for uur in data.lesuren)
    return [
        Melding(
            "fout",
            f"Klas {klas} heeft {n} lesuren, maar er zijn maar {len(data.tijdslots)} tijdslots.",
        )
        for klas, n in sorted(aantal.items())
        if n > len(data.tijdslots)
    ]


def _controleer_leraren(data: ProbleemData) -> list[Melding]:
    """Een leraar mag niet meer lesuren hebben dan hij in de week kan geven."""
    aantal = Counter(uur.leraar_id for uur in data.lesuren)
    meldingen = []
    for leraar in data.leraren:
        meldingen += _controleer_leraar(data, leraar, aantal[leraar.id])
    return meldingen


def _capaciteit(data: ProbleemData, leraar: Leraar) -> int:
    """Uren die een leraar kan geven: per dag het minimum van maximum en vrije tijdslots."""
    vrij = Counter(s.dag for s in data.tijdslots if s.id not in leraar.onbeschikbaar)
    return sum(min(leraar.max_uren_per_dag, vrij[dag]) for dag in data.dagen)


def _controleer_leraar(data: ProbleemData, leraar: Leraar, n: int) -> list[Melding]:
    """De meldingen voor één leraar met n lesuren."""
    meldingen = []
    ruimte = leraar.max_uren_per_dag * len(data.dagen)
    beschikbaar = len(set(data.tijdslot_per_id) - leraar.onbeschikbaar)
    if n > ruimte:
        meldingen.append(Melding(
            "fout",
            f"Leraar {leraar.naam} heeft {n} lesuren, maar mag per dag maximaal "
            f"{leraar.max_uren_per_dag} uur geven ({ruimte} uur in {len(data.dagen)} dagen).",
        ))
    if n > beschikbaar:
        meldingen.append(Melding(
            "fout",
            f"Leraar {leraar.naam} heeft {n} lesuren, maar is maar op {beschikbaar} tijdslots beschikbaar.",
        ))
    capaciteit = _capaciteit(data, leraar)
    if not meldingen and n > capaciteit:  # beide grenzen samen, per dag
        meldingen.append(Melding(
            "fout",
            f"Leraar {leraar.naam} heeft {n} lesuren, maar kan met het maximum van "
            f"{leraar.max_uren_per_dag} uur per dag en de onbeschikbaarheid samen maar "
            f"{capaciteit} uur geven.",
        ))
    return meldingen


def _controleer_lokalen(data: ProbleemData) -> list[Melding]:
    """Per lokaaltype moeten er lokalen zijn met genoeg plaatsen."""
    gevraagd = Counter(uur.lokaaltype for uur in data.lesuren)
    aanwezig = Counter(lokaal.type for lokaal in data.lokalen)
    meldingen = []
    for soort, n in sorted(gevraagd.items()):
        if aanwezig[soort] == 0:
            meldingen.append(
                Melding("fout", f"Er is geen lokaal van het type '{soort}', maar {n} lesuren vragen er een.")
            )
        elif n > aanwezig[soort] * len(data.tijdslots):
            meldingen.append(
                Melding(
                    "fout",
                    f"Er zijn {n} lesuren in lokalen van het type '{soort}', maar er zijn maar "
                    f"{aanwezig[soort] * len(data.tijdslots)} plaatsen "
                    f"({aanwezig[soort]} lokalen x {len(data.tijdslots)} tijdslots).",
                )
            )
    return meldingen
