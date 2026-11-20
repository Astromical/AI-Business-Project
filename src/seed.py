"""Voorbeelddata. Dit is verzonnen testdata, geen echte schooldata."""

from __future__ import annotations

import sqlite3

from src.db import leeg_database, maak_tijdslots
from src.models import DAGEN

LABEL = "Voorbeelddata: verzonnen gegevens, geen echte schooldata."
VARIANTEN = ("voorbeeld", "onmogelijk", "groot")

KLASSEN = ("1A", "1B", "2A", "2B", "3A", "3B")
UREN_PER_DAG = {dag: 6 for dag in DAGEN}

LOKALEN = [
    ("R1", "Lokaal 1", "regulier"),
    ("R2", "Lokaal 2", "regulier"),
    ("R3", "Lokaal 3", "regulier"),
    ("R4", "Lokaal 4", "regulier"),
    ("R5", "Lokaal 5", "regulier"),
    ("LAB", "Laboratorium", "lab"),
    ("GYM", "Sporthal", "gym"),
]

# (id, naam, max_uren_per_dag)
LERAREN = [
    ("PEE", "Peeters", 5),
    ("MAE", "Maes", 5),
    ("CLA", "Claes", 5),
    ("WIL", "Willems", 5),
    ("JAN", "Janssens", 5),
    ("DUB", "Dubois", 6),
    ("GOO", "Goossens", 5),
    ("HER", "Hermans", 5),
    ("MER", "Mertens", 5),
    ("VER", "Vermeulen", 5),
]

# (dag, uur) waarop een leraar niet kan.
ONBESCHIKBAAR = {
    "DUB": [("donderdag", 5), ("donderdag", 6)],
    "VER": [("woensdag", 5), ("woensdag", 6), ("vrijdag", 6)],
}

_WIS = {"1A": "PEE", "1B": "PEE", "2A": "PEE", "2B": "MAE", "3A": "MAE", "3B": "MAE"}
_NED = {"1A": "CLA", "1B": "CLA", "2A": "CLA", "2B": "WIL", "3A": "WIL", "3B": "WIL"}

# (code, vak, lokaaltype, uren per week, leraar per klas)
VAKKEN = [
    ("WIS", "wiskunde", "regulier", 4, _WIS),
    ("NED", "nederlands", "regulier", 4, _NED),
    ("ENG", "engels", "regulier", 3, dict.fromkeys(KLASSEN, "JAN")),
    ("FRA", "frans", "regulier", 2, dict.fromkeys(KLASSEN, "DUB")),
    ("GES", "geschiedenis", "regulier", 2, dict.fromkeys(KLASSEN, "DUB")),
    ("AAR", "aardrijkskunde", "regulier", 2, dict.fromkeys(KLASSEN, "GOO")),
    ("BIO", "biologie", "lab", 2, dict.fromkeys(KLASSEN, "HER")),
    ("NAT", "natuurkunde", "lab", 2, dict.fromkeys(KLASSEN, "MER")),
    ("LO", "lichamelijke opvoeding", "gym", 3, dict.fromkeys(KLASSEN, "VER")),
]

# Variant "onmogelijk": klas 1A krijgt 12 uur wiskunde, dus 32 lesuren op 30 tijdslots.
ONMOGELIJK_EXTRA = {("1A", "WIS"): 12}


# --- Variant "groot": een veel grotere, krappe school om de solver echt te belasten ---
# 16 klassen, 28 leraren, 16 lokalen, 40 tijdslots en 512 lesuren (elke klas 32 van de 40 uur).
KLASSEN_GROOT = tuple(f"{jaar}{letter}" for jaar in "1234" for letter in "ABCD")
UREN_PER_DAG_GROOT = {dag: 8 for dag in DAGEN}

# (code, vak, lokaaltype, uren per week per klas)
VAKKEN_GROOT = [
    ("WIS", "wiskunde", "regulier", 4),
    ("NED", "nederlands", "regulier", 4),
    ("ENG", "engels", "regulier", 3),
    ("FRA", "frans", "regulier", 3),
    ("GES", "geschiedenis", "regulier", 2),
    ("AAR", "aardrijkskunde", "regulier", 2),
    ("MUZ", "muziek", "regulier", 2),
    ("PLA", "plastische opvoeding", "regulier", 2),
    ("INF", "informatica", "regulier", 1),
    ("BIO", "biologie", "lab", 2),
    ("NAT", "natuurkunde", "lab", 2),
    ("SCH", "scheikunde", "lab", 2),
    ("LO", "lichamelijke opvoeding", "gym", 3),
]
# Elke leraargroep geeft per leerjaar alle klassen van die vakken; zo moeten de vier klassen
# van een leerjaar achter elkaar bij dezelfde leraar langs.
LERAARGROEPEN_GROOT = [
    ("WIS", ["WIS"]),
    ("NED", ["NED"]),
    ("TAL", ["ENG", "FRA"]),
    ("MENS", ["GES", "AAR"]),
    ("KUNST", ["MUZ", "PLA", "INF"]),
    ("NAT", ["BIO", "NAT"]),
    ("SPORT", ["SCH", "LO"]),
]


def _groot() -> tuple[list, list, list, dict[str, list[tuple[str, int]]]]:
    """Lokalen, leraren, lessen en onbeschikbaarheid van de grote variant."""
    lokalen = (
        [(f"R{i:02d}", f"Lokaal {i}", "regulier") for i in range(1, 12)]
        + [(f"LAB{i}", f"Laboratorium {i}", "lab") for i in range(1, 4)]
        + [(f"GYM{i}", f"Sporthal {i}", "gym") for i in range(1, 3)]
    )
    leraren, lessen = [], []
    onbeschikbaar: dict[str, list[tuple[str, int]]] = {}
    teller = 0
    for jaar in "1234":
        klassen = [k for k in KLASSEN_GROOT if k[0] == jaar]
        for groep, codes in LERAARGROEPEN_GROOT:
            leraar_id = f"{groep}{jaar}"
            leraren.append((leraar_id, f"{groep.capitalize()} jaar {jaar}", 6))
            for code, vak, type_, uren in VAKKEN_GROOT:
                if code in codes:
                    lessen += [
                        (f"{k}-{code}", vak, k, leraar_id, uren, type_) for k in klassen
                    ]
            dagen = list(DAGEN)
            if teller % 3 == 0:  # een derde van de leraren is aan het eind van een dag weg
                onbeschikbaar[leraar_id] = [(dagen[teller % 5], 7), (dagen[teller % 5], 8)]
            if teller % 6 == 0:
                onbeschikbaar[leraar_id] += [(dagen[(teller + 2) % 5], 1)]
            teller += 1
    return lokalen, leraren, lessen, onbeschikbaar


def _lessen(variant: str) -> list[tuple[str, str, str, str, int, str]]:
    """Alle lessen als rijen voor de tabel les."""
    rijen = []
    for code, vak, type_, uren, leraar_per_klas in VAKKEN:
        for klas in KLASSEN:
            aantal = uren
            if variant == "onmogelijk":
                aantal = ONMOGELIJK_EXTRA.get((klas, code), uren)
            rijen.append(
                (f"{klas}-{code}", vak, klas, leraar_per_klas[klas], aantal, type_)
            )
    return rijen


def seed(con: sqlite3.Connection, variant: str = "voorbeeld") -> None:
    """Wis de database en vul hem met voorbeelddata (variant 'voorbeeld', 'onmogelijk' of 'groot')."""
    if variant not in VARIANTEN:
        raise ValueError(
            f"Onbekende variant '{variant}'; kies uit: {', '.join(VARIANTEN)}"
        )
    leeg_database(con)
    if variant == "groot":
        uren_per_dag = UREN_PER_DAG_GROOT
        lokalen, leraren, lessen, onbeschikbaar = _groot()
    else:
        uren_per_dag, lokalen, leraren = UREN_PER_DAG, LOKALEN, LERAREN
        lessen, onbeschikbaar = _lessen(variant), ONBESCHIKBAAR
    maak_tijdslots(con, uren_per_dag)
    with con:
        con.executemany("INSERT INTO lokaal VALUES (?, ?, ?)", lokalen)
        con.executemany("INSERT INTO leraar VALUES (?, ?, ?)", leraren)
        con.executemany("INSERT INTO les VALUES (?, ?, ?, ?, ?, ?)", lessen)
        for leraar_id, momenten in onbeschikbaar.items():
            for dag, uur in momenten:
                con.execute(
                    "INSERT INTO onbeschikbaar "
                    "SELECT ?, id FROM tijdslot WHERE dag = ? AND uur = ?",
                    (leraar_id, dag, uur),
                )
