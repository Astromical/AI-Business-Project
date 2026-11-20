"""Onafhankelijke controle van een rooster met gewone Python.

Gebruikt geen OR-Tools en geen code uit solver.py of constraints.py.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from src.models import Lesuur, ProbleemData, Schending, Toewijzing


def _sleutel(lesuur: Lesuur) -> tuple[str, int]:
    """Identificeer een lesuur."""
    return lesuur.les_id, lesuur.volgnummer


def controleer(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """Geef alle schendingen van de harde regels H1 tot en met H7."""
    schendingen: list[Schending] = []
    schendingen += _h1(data, toewijzingen)
    schendingen += _dubbel_gebruik(toewijzingen, "H2", lambda t: (t.tijdslot_id, t.lokaal_id), "Lokaal")
    schendingen += _dubbel_gebruik(
        toewijzingen, "H3", lambda t: (t.tijdslot_id, t.lesuur.leraar_id), "Leraar"
    )
    schendingen += _dubbel_gebruik(
        toewijzingen, "H4", lambda t: (t.tijdslot_id, t.lesuur.klas), "Klas"
    )
    schendingen += _h5(data, toewijzingen)
    schendingen += _h6(data, toewijzingen)
    schendingen += _h7(data, toewijzingen)
    return schendingen


def _h1(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """H1: elk lesuur precies één keer, in een bestaand tijdslot en lokaal."""
    schendingen = []
    aantal: dict[tuple[str, int], int] = defaultdict(int)
    for t in toewijzingen:
        aantal[_sleutel(t.lesuur)] += 1
        if t.tijdslot_id not in data.tijdslot_per_id or t.lokaal_id not in data.lokaal_per_id:
            schendingen.append(
                Schending("H1", (t.lesuur,), f"{_naam(t.lesuur)} staat in een onbekend tijdslot of lokaal.")
            )
    bekend = {_sleutel(u) for u in data.lesuren}
    for lesuur in data.lesuren:
        n = aantal[_sleutel(lesuur)]
        if n != 1:
            tekst = "is niet ingepland" if n == 0 else f"is {n} keer ingepland"
            schendingen.append(Schending("H1", (lesuur,), f"{_naam(lesuur)} {tekst}."))
    for t in toewijzingen:
        if _sleutel(t.lesuur) not in bekend:
            schendingen.append(Schending("H1", (t.lesuur,), f"{_naam(t.lesuur)} bestaat niet in de lessen."))
    return schendingen


def _naam(lesuur: Lesuur) -> str:
    """Leesbare naam van een lesuur."""
    return f"Lesuur {lesuur.volgnummer} van {lesuur.vak} voor klas {lesuur.klas}"


def _dubbel_gebruik(toewijzingen, regel: str, sleutel, wie: str) -> list[Schending]:
    """Geef een schending voor elke groep met meer dan één lesuur in hetzelfde tijdslot."""
    groepen: dict[tuple, list[Lesuur]] = defaultdict(list)
    for t in toewijzingen:
        groepen[sleutel(t)].append(t.lesuur)
    schendingen = []
    for (tijdslot_id, naam), lesuren in groepen.items():
        if len(lesuren) > 1:
            tekst = f"{wie} {naam} heeft {len(lesuren)} lessen tegelijk in tijdslot {tijdslot_id}."
            schendingen.append(Schending(regel, tuple(lesuren), tekst))
    return schendingen


def _h5(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """H5: een les staat alleen in een lokaal van het gevraagde type."""
    schendingen = []
    for t in toewijzingen:
        lokaal = data.lokaal_per_id.get(t.lokaal_id)
        if lokaal is not None and lokaal.type != t.lesuur.lokaaltype:
            tekst = (
                f"{_naam(t.lesuur)} vraagt een lokaal van type '{t.lesuur.lokaaltype}', "
                f"maar staat in {lokaal.naam} (type '{lokaal.type}')."
            )
            schendingen.append(Schending("H5", (t.lesuur,), tekst))
    return schendingen


def _h6(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """H6: een leraar staat niet op een onbeschikbaar tijdslot."""
    schendingen = []
    for t in toewijzingen:
        leraar = data.leraar_per_id.get(t.lesuur.leraar_id)
        if leraar is not None and t.tijdslot_id in leraar.onbeschikbaar:
            tekst = f"Leraar {leraar.naam} staat ingepland in tijdslot {t.tijdslot_id}, maar is dan niet beschikbaar."
            schendingen.append(Schending("H6", (t.lesuur,), tekst))
    return schendingen


def _h7(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """H7: een leraar geeft per dag niet meer dan zijn maximum."""
    groepen: dict[tuple[str, str], list[Lesuur]] = defaultdict(list)
    for t in toewijzingen:
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if slot is not None:
            groepen[t.lesuur.leraar_id, slot.dag].append(t.lesuur)
    schendingen = []
    for (leraar_id, dag), lesuren in groepen.items():
        leraar = data.leraar_per_id.get(leraar_id)
        if leraar is not None and len(lesuren) > leraar.max_uren_per_dag:
            tekst = (
                f"Leraar {leraar.naam} geeft op {dag} {len(lesuren)} uur, "
                f"meer dan het maximum van {leraar.max_uren_per_dag}."
            )
            schendingen.append(Schending("H7", tuple(lesuren), tekst))
    return schendingen


def tel_tussenuren(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> dict[str, int]:
    """Tel per klas de tussenuren: vrije uren met eerder en later die dag nog een les."""
    return _tel_gaten(data, toewijzingen, lambda uur: uur.klas, data.klassen)


def tel_tussenuren_leraren(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]
) -> dict[str, int]:
    """Tel per leraar (id) de tussenuren."""
    leraren = tuple(leraar.id for leraar in data.leraren)
    return _tel_gaten(data, toewijzingen, lambda uur: uur.leraar_id, leraren)


def _tel_gaten(
    data: ProbleemData,
    toewijzingen: tuple[Toewijzing, ...],
    groep_van: Callable[[Lesuur], str],
    groepen: tuple[str, ...],
) -> dict[str, int]:
    """Tel per groep de vrije uren met eerder en later die dag nog een les."""
    bezet: dict[tuple[str, str], set[int]] = defaultdict(set)
    for t in toewijzingen:
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if slot is not None:
            bezet[groep_van(t.lesuur), slot.dag].add(slot.uur)
    uren_per_dag: dict[str, list[int]] = defaultdict(list)
    for slot in data.tijdslots:
        uren_per_dag[slot.dag].append(slot.uur)
    aantal = dict.fromkeys(groepen, 0)
    for (groep, dag), uren in bezet.items():
        eerste, laatste = min(uren), max(uren)
        aantal[groep] = aantal.get(groep, 0) + sum(
            1 for uur in uren_per_dag[dag] if eerste < uur < laatste and uur not in uren
        )
    return aantal


def tel_dubbele_vakken(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]
) -> dict[str, int]:
    """Tel per klas de lesuren die een vak voor de tweede (derde, ...) keer op een dag geven."""
    aantal: dict[tuple[str, str, str], int] = defaultdict(int)
    for t in toewijzingen:
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if slot is not None:
            aantal[t.lesuur.klas, t.lesuur.vak, slot.dag] += 1
    dubbel = dict.fromkeys(data.klassen, 0)
    for (klas, _, _), n in aantal.items():
        dubbel[klas] = dubbel.get(klas, 0) + max(0, n - 1)
    return dubbel


def tel_zware_laatste_uren(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], zware_vakken: tuple[str, ...]
) -> int:
    """Tel de lesuren van een zwaar vak in het laatste uur van hun dag."""
    zwaar = {vak.lower() for vak in zware_vakken}
    laatste: dict[str, int] = {}
    for slot in data.tijdslots:
        laatste[slot.dag] = max(laatste.get(slot.dag, 0), slot.uur)
    aantal = 0
    for t in toewijzingen:
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if slot is not None and slot.uur == laatste[slot.dag] and t.lesuur.vak.lower() in zwaar:
            aantal += 1
    return aantal


def tel_per_regel(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], zware_vakken: tuple[str, ...] = ()
) -> dict[str, int]:
    """Het aantal overtredingen per zachte regel, zonder gewicht."""
    return {
        "Z1": sum(tel_tussenuren(data, toewijzingen).values()),
        "Z2": sum(tel_tussenuren_leraren(data, toewijzingen).values()),
        "Z3": sum(tel_dubbele_vakken(data, toewijzingen).values()),
        "Z4": tel_zware_laatste_uren(data, toewijzingen, zware_vakken),
    }


def tel_straf(
    data: ProbleemData,
    toewijzingen: tuple[Toewijzing, ...],
    gewichten: dict[str, int],
    zware_vakken: tuple[str, ...] = (),
) -> dict[str, int]:
    """Strafpunten per zachte regel (gewicht × aantal), voor elke regel met gewicht > 0."""
    aantallen = tel_per_regel(data, toewijzingen, zware_vakken)
    return {
        regel: gewicht * aantallen[regel]
        for regel, gewicht in gewichten.items()
        if gewicht > 0 and regel in aantallen
    }
