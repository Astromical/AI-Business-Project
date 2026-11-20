"""Gegevens beheren via tabellen (DataFrames); de SQL zelf staat in db.py."""

from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter

import pandas as pd

from src import db
from src.conversie import LesRij
from src.db import OpslaanFout
from src.models import DAGEN

TABBLADEN: tuple[str, ...] = ("leraar", "lokaal", "onbeschikbaar", "les")

# Kolommen zoals de gebruiker ze ziet; bij onbeschikbaar staan dag en uur in plaats van een tijdslot-id.
WEERGAVE_KOLOMMEN: dict[str, tuple[str, ...]] = {
    "leraar": ("id", "naam", "max_uren_per_dag"),
    "lokaal": ("id", "naam", "type"),
    "onbeschikbaar": ("leraar_id", "dag", "uur"),
    "les": ("id", "vak", "klas", "leraar_id", "aantal_per_week", "lokaaltype"),
}
WEERGAVE_SLEUTELS: dict[str, tuple[str, ...]] = {
    "leraar": ("id",),
    "lokaal": ("id",),
    "onbeschikbaar": ("leraar_id", "dag", "uur"),
    "les": ("id",),
}
GEHELE_GETALLEN = {"max_uren_per_dag", "aantal_per_week", "uur"}


def lees(con: sqlite3.Connection, tabel: str) -> pd.DataFrame:
    """De tabel zoals de gebruiker hem ziet."""
    rijen = db.lees_tabel(con, tabel)
    if tabel == "onbeschikbaar":
        slots = {r["id"]: r for r in db.lees_tabel(con, "tijdslot")}
        rijen = [
            {"leraar_id": r["leraar_id"], "dag": slots[r["tijdslot_id"]]["dag"], "uur": slots[r["tijdslot_id"]]["uur"]}
            for r in rijen
        ]
    return pd.DataFrame(rijen, columns=list(WEERGAVE_KOLOMMEN[tabel]))


def _schoon(waarde: object, kolom: str) -> object:
    """Zet een celwaarde om naar een gewone Python-waarde (of None als leeg)."""
    if waarde is None or pd.isna(waarde):
        return None
    if hasattr(waarde, "item"):
        waarde = waarde.item()
    if isinstance(waarde, str):
        waarde = waarde.strip()
        if not waarde:
            return None
    if kolom in GEHELE_GETALLEN:
        try:
            return int(waarde)
        except (TypeError, ValueError):
            raise OpslaanFout(f"'{waarde}' bij '{kolom}' is geen geheel getal.") from None
    return waarde


def _rijen(tabel: pd.DataFrame, kolommen: tuple[str, ...]) -> list[dict]:
    """De rijen van een DataFrame als schone dicts, zonder volledig lege rijen."""
    rijen = [
        {k: _schoon(rij.get(k), k) for k in kolommen}
        for rij in tabel.to_dict("records")
    ]
    return [r for r in rijen if any(v is not None for v in r.values())]


def bepaal_wijzigingen(
    oud: pd.DataFrame, nieuw: pd.DataFrame, kolommen: tuple[str, ...], sleutel: tuple[str, ...]
) -> tuple[list[dict], list[tuple]]:
    """Vergelijk oud en nieuw: geef de nieuwe of gewijzigde rijen en de verwijderde sleutels."""
    nieuwe = _rijen(nieuw, kolommen)
    for rij in nieuwe:
        if any(rij[k] is None for k in sleutel):
            raise OpslaanFout(f"Vul bij elke rij de velden in: {', '.join(sleutel)}.")
    sleutels = [tuple(rij[k] for k in sleutel) for rij in nieuwe]
    dubbel = [s for s, n in Counter(sleutels).items() if n > 1]
    if dubbel:
        raise OpslaanFout(f"Deze rij komt meer dan eens voor: {' / '.join(map(str, dubbel[0]))}.")
    oud_per_sleutel = {tuple(r[k] for k in sleutel): r for r in _rijen(oud, kolommen)}
    nieuw_per_sleutel = dict(zip(sleutels, nieuwe))
    verwijder = [s for s in oud_per_sleutel if s not in nieuw_per_sleutel]
    te_schrijven = [r for s, r in nieuw_per_sleutel.items() if oud_per_sleutel.get(s) != r]
    return te_schrijven, verwijder


def sla_op(con: sqlite3.Connection, tabel: str, nieuw: pd.DataFrame) -> int:
    """Sla de bewerkte tabel op; geef het aantal gewijzigde rijen terug.

    Bij een fout (OpslaanFout) blijft de database ongewijzigd.
    """
    if tabel not in WEERGAVE_KOLOMMEN:
        raise ValueError(f"Onbekende tabel: {tabel}")
    rijen, verwijder = bepaal_wijzigingen(
        lees(con, tabel), nieuw, WEERGAVE_KOLOMMEN[tabel], WEERGAVE_SLEUTELS[tabel]
    )
    if tabel == "onbeschikbaar":
        rijen, verwijder = _naar_tijdslot_ids(con, rijen, verwijder)
    db.sla_tabel_op(con, tabel, rijen, verwijder)
    return len(rijen) + len(verwijder)


def _naar_tijdslot_ids(
    con: sqlite3.Connection, rijen: list[dict], verwijder: list[tuple]
) -> tuple[list[dict], list[tuple]]:
    """Zet (dag, uur) om naar tijdslot-id voor de tabel onbeschikbaar."""
    ids = {(r["dag"], r["uur"]): r["id"] for r in db.lees_tabel(con, "tijdslot")}

    def id_van(dag: object, uur: object) -> int:
        if (dag, uur) not in ids:
            raise OpslaanFout(f"Het tijdslot {dag} uur {uur} bestaat niet.")
        return ids[dag, uur]

    return (
        [{"leraar_id": r["leraar_id"], "tijdslot_id": id_van(r["dag"], r["uur"])} for r in rijen],
        [(leraar_id, id_van(dag, uur)) for leraar_id, dag, uur in verwijder],
    )


def uren_per_dag(con: sqlite3.Connection) -> dict[str, int]:
    """Het aantal tijdslots per dag zoals het nu in de database staat."""
    return dict(Counter(r["dag"] for r in db.lees_tabel(con, "tijdslot")))


def maak_tijdslots(con: sqlite3.Connection, uren: dict[str, int]) -> None:
    """Maak tijdslots aan; bestaan ze al, dan worden ze vervangen (met gevolgen, zie db)."""
    if db.lees_tabel(con, "tijdslot"):
        db.maak_tijdslots_opnieuw(con, uren)
    else:
        db.maak_tijdslots(con, uren)


STANDAARD_MAX_UREN_PER_DAG = 8  # ruim: de roostermaker kan het daarna verlagen


def _vrij_id(bronnen: tuple[str, ...], bezet: set[str]) -> str:
    """Een leesbaar, nog vrij id, bijvoorbeeld 1A-WISKUNDE of 1A-WISKUNDE-2."""
    basis = re.sub(r"[^A-Z0-9]+", "-", "-".join(bronnen).upper()).strip("-") or "ID"
    kandidaat, volgnummer = basis, 2
    while kandidaat in bezet:
        kandidaat, volgnummer = f"{basis}-{volgnummer}", volgnummer + 1
    bezet.add(kandidaat)
    return kandidaat


def importeer(con: sqlite3.Connection, rijen: tuple[LesRij, ...]) -> tuple[int, int]:
    """Voeg lessen toe; geef het aantal nieuwe leraren en lessen.

    Leraren worden op naam herkend en anders aangemaakt. Een les met dezelfde klas, vak en
    leraar krijgt de nieuwe uren, zodat opnieuw importeren niets verdubbelt.
    """
    leraren = {r["naam"].lower(): r["id"] for r in db.lees_tabel(con, "leraar")}
    bestaand = db.lees_tabel(con, "les")
    les_ids = {(r["klas"].lower(), r["vak"].lower(), r["leraar_id"]): r["id"] for r in bestaand}
    bezet_leraren, bezet_lessen = set(leraren.values()), {r["id"] for r in bestaand}
    nieuwe_leraren, lessen = [], []
    nieuwe_lessen = 0
    for rij in rijen:
        if rij.leraar.lower() not in leraren:
            id_ = _vrij_id((rij.leraar,), bezet_leraren)
            leraren[rij.leraar.lower()] = id_
            nieuwe_leraren.append(
                {"id": id_, "naam": rij.leraar, "max_uren_per_dag": STANDAARD_MAX_UREN_PER_DAG}
            )
        leraar_id = leraren[rij.leraar.lower()]
        les_id = les_ids.get((rij.klas.lower(), rij.vak.lower(), leraar_id))
        if les_id is None:
            les_id = _vrij_id((rij.klas, rij.vak, leraar_id), bezet_lessen)
            nieuwe_lessen += 1
        lessen.append(
            {
                "id": les_id,
                "vak": rij.vak,
                "klas": rij.klas,
                "leraar_id": leraar_id,
                "aantal_per_week": rij.uren_per_week,
                "lokaaltype": rij.soort_lokaal,
            }
        )
    db.importeer_lessen(con, nieuwe_leraren, lessen)
    return len(nieuwe_leraren), nieuwe_lessen


BEZETTING_LOKALEN = 0.8  # lokalen niet helemaal volplannen, anders is er snel geen rooster


def _ontbrekende_tijdslots(con: sqlite3.Connection, rijen: tuple[LesRij, ...]) -> list[tuple[str, int]]:
    """De tijdslots die nodig zijn om de drukste klas ruimte te geven (hoogstens 8 uur per dag)."""
    uren_per_klas = Counter()
    for rij in rijen:
        uren_per_klas[rij.klas] += rij.uren_per_week
    bestaand = {(r["dag"], r["uur"]) for r in db.lees_tabel(con, "tijdslot")}
    drukste = max(uren_per_klas.values(), default=0)
    if drukste < len(bestaand):
        return []
    per_dag = min(8, math.ceil(drukste / len(DAGEN)) + 1)
    nodig = [(dag, uur) for dag in DAGEN for uur in range(1, per_dag + 1)]
    return [slot for slot in nodig if slot not in bestaand]


# soort lokaal -> naam voor lokalen die de import zelf aanmaakt
LOKAALNAAM: dict[str, str] = {"regulier": "Lokaal", "lab": "Labo", "gym": "Sporthal"}


def _ontbrekende_lokalen(
    con: sqlite3.Connection, rijen: tuple[LesRij, ...], tijdslots: int
) -> list[dict]:
    """Lokalen voor elke soort waarvan er te weinig zijn, met een gewone naam (Lokaal 1, Labo 1, ...)."""
    lokalen = db.lees_tabel(con, "lokaal")
    bezet = {r["id"] for r in lokalen}
    uren = Counter()
    for les in db.lees_tabel(con, "les"):
        uren[les["lokaaltype"]] += les["aantal_per_week"]
    klassen: dict[str, set[str]] = {}
    for rij in rijen:
        uren[rij.soort_lokaal] += rij.uren_per_week
        klassen.setdefault(rij.soort_lokaal, set()).add(rij.klas)
    nieuw = []
    for soort, samen in klassen.items():
        nodig = max(len(samen), math.ceil(uren[soort] / (tijdslots * BEZETTING_LOKALEN)))
        aanwezig = sum(r["type"] == soort for r in lokalen)
        for nummer in range(aanwezig + 1, nodig + 1):
            naam = f"{LOKAALNAAM.get(soort, 'Lokaal')} {nummer}"
            id_ = _vrij_id((naam,), bezet)
            nieuw.append({"id": id_, "naam": naam, "type": soort})
    return nieuw


def vul_basis_aan(con: sqlite3.Connection, rijen: tuple[LesRij, ...]) -> tuple[int, int]:
    """Vul tijdslots en lokalen aan die deze lessen nodig hebben; geef de aantallen terug."""
    tijdslots = _ontbrekende_tijdslots(con, rijen)
    totaal = len(db.lees_tabel(con, "tijdslot")) + len(tijdslots)
    lokalen = _ontbrekende_lokalen(con, rijen, totaal)
    db.voeg_basis_toe(con, tijdslots, lokalen)
    return len(tijdslots), len(lokalen)
