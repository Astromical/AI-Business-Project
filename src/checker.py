"""Onafhankelijke controle van een rooster met gewone Python.

Gebruikt geen OR-Tools en geen code uit solver.py of constraints.py.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from src.models import Lesuur, ProbleemData, Schending, Strafpost, Toewijzing, Wijziging


def _sleutel(lesuur: Lesuur) -> tuple[str, int]:
    """Identificeer een lesuur."""
    return lesuur.les_id, lesuur.volgnummer


def controleer(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """Geef alle schendingen van de harde regels H1 tot en met H9."""
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
    schendingen += _h8(data, toewijzingen)
    schendingen += _h9(data, toewijzingen)
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


def _h8(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """H8: het aantal leerlingen van een les past in het lokaal."""
    schendingen = []
    for t in toewijzingen:
        les = data.les_per_id.get(t.lesuur.les_id)
        lokaal = data.lokaal_per_id.get(t.lokaal_id)
        if les is None or lokaal is None or les.aantal_leerlingen is None or lokaal.capaciteit is None:
            continue
        if les.aantal_leerlingen > lokaal.capaciteit:
            tekst = (
                f"{_naam(t.lesuur)} heeft {les.aantal_leerlingen} leerlingen, maar {lokaal.naam} "
                f"heeft maar {lokaal.capaciteit} plaatsen."
            )
            schendingen.append(Schending("H8", (t.lesuur,), tekst))
    return schendingen


def _h9(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> list[Schending]:
    """H9: de lesuren van een blokles vormen paren van twee opeenvolgende uren op één dag,
    zonder de pauze ertussen."""
    per_les_dag: dict[tuple[str, str], list[Toewijzing]] = defaultdict(list)
    for t in toewijzingen:
        les = data.les_per_id.get(t.lesuur.les_id)
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if les is not None and les.blokuur and slot is not None:
            per_les_dag[les.id, slot.dag].append(t)
    schendingen = []
    for (les_id, dag), lessen in per_les_dag.items():
        uren = sorted(data.tijdslot_per_id[t.tijdslot_id].uur for t in lessen)
        if not _in_paren(uren, data.pauze_na_uur):
            les = data.les_per_id[les_id]
            tekst = (
                f"{les.vak} voor klas {les.klas} is een blokuur, maar staat op {dag} op uur "
                f"{', '.join(map(str, uren))}: geen paren van twee uren na elkaar."
            )
            schendingen.append(Schending("H9", tuple(t.lesuur for t in lessen), tekst))
    return schendingen


def _in_paren(uren: list[int], pauze_na_uur: int) -> bool:
    """Zijn de gesorteerde uren te verdelen in paren (u, u + 1), niet over de pauze?"""
    if len(uren) % 2:
        return False
    for eerste, tweede in zip(uren[0::2], uren[1::2]):
        if tweede != eerste + 1 or (pauze_na_uur and eerste == pauze_na_uur):
            return False
    return True


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


# --- Uitleg bij de strafscore: welke overtredingen, en wie erbij betrokken is ---

_Plek = dict[tuple[str, str], dict[int, Toewijzing]]  # (groep, dag) -> uur -> toewijzing


def _plekken(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], groep_van: Callable[[Lesuur], str]
) -> _Plek:
    """Per groep (klas of leraar) en dag de toewijzing op elk bezet uur."""
    plek: _Plek = defaultdict(dict)
    for t in toewijzingen:
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if slot is not None:
            plek[groep_van(t.lesuur), slot.dag][slot.uur] = t
    return plek


def _betrokken(data: ProbleemData, lessen: list[Toewijzing]) -> tuple[tuple, tuple, tuple]:
    """Klassen, namen van leraren en namen van lokalen van deze toewijzingen, zonder dubbels."""
    klassen = dict.fromkeys(t.lesuur.klas for t in lessen)
    leraren = dict.fromkeys(_leraarnaam(data, t.lesuur.leraar_id) for t in lessen)
    lokalen = dict.fromkeys(
        data.lokaal_per_id[t.lokaal_id].naam if t.lokaal_id in data.lokaal_per_id else t.lokaal_id
        for t in lessen
    )
    return tuple(klassen), tuple(leraren), tuple(lokalen)


def _leraarnaam(data: ProbleemData, leraar_id: str) -> str:
    """De naam van een leraar, of zijn id als hij onbekend is."""
    leraar = data.leraar_per_id.get(leraar_id)
    return leraar.naam if leraar is not None else leraar_id


def _gat_posten(
    data: ProbleemData,
    toewijzingen: tuple[Toewijzing, ...],
    regel: str,
    gewicht: int,
    groep_van: Callable[[Lesuur], str],
    wie: Callable[[str], str],
) -> list[Strafpost]:
    """Een post per tussenuur (Z1 of Z2), met de les ervoor en erna als betrokkenen."""
    uren_per_dag: dict[str, list[int]] = defaultdict(list)
    for slot in data.tijdslots:
        uren_per_dag[slot.dag].append(slot.uur)
    posten = []
    for (groep, dag), bezet in _plekken(data, toewijzingen, groep_van).items():
        for uur in sorted(uren_per_dag[dag]):
            if not min(bezet) < uur < max(bezet) or uur in bezet:
                continue
            voor = bezet[max(u for u in bezet if u < uur)]
            na = bezet[min(u for u in bezet if u > uur)]
            klassen, leraren, lokalen = _betrokken(data, [voor, na])
            tekst = (
                f"{wie(groep)} heeft een tussenuur op {dag} uur {uur} "
                f"(tussen {voor.lesuur.vak} en {na.lesuur.vak})."
            )
            posten.append(Strafpost(regel, 1, gewicht, dag, (uur,), klassen, leraren, lokalen, tekst))
    return posten


def _z3_posten(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], gewicht: int) -> list[Strafpost]:
    """Een post per klas, vak en dag met meer dan één lesuur van dat vak."""
    groepen: dict[tuple[str, str, str], list[Toewijzing]] = defaultdict(list)
    for t in toewijzingen:
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if slot is not None:
            groepen[t.lesuur.klas, t.lesuur.vak, slot.dag].append(t)
    posten = []
    for (klas, vak, dag), lessen in groepen.items():
        if len(lessen) < 2:
            continue
        uren = tuple(sorted(data.tijdslot_per_id[t.tijdslot_id].uur for t in lessen))
        klassen, leraren, lokalen = _betrokken(data, lessen)
        tekst = f"Klas {klas} heeft {vak} {len(lessen)} keer op {dag} (uren {', '.join(map(str, uren))})."
        aantal = len(lessen) - 1
        posten.append(Strafpost("Z3", aantal, gewicht * aantal, dag, uren, klassen, leraren, lokalen, tekst))
    return posten


def _z4_posten(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], gewicht: int, zware_vakken: tuple[str, ...]
) -> list[Strafpost]:
    """Een post per lesuur van een zwaar vak in het laatste uur van zijn dag."""
    zwaar = {vak.lower() for vak in zware_vakken}
    laatste: dict[str, int] = {}
    for slot in data.tijdslots:
        laatste[slot.dag] = max(laatste.get(slot.dag, 0), slot.uur)
    posten = []
    for t in toewijzingen:
        slot = data.tijdslot_per_id.get(t.tijdslot_id)
        if slot is None or slot.uur != laatste[slot.dag] or t.lesuur.vak.lower() not in zwaar:
            continue
        klassen, leraren, lokalen = _betrokken(data, [t])
        tekst = f"Klas {t.lesuur.klas} heeft {t.lesuur.vak} in het laatste uur van {slot.dag}."
        posten.append(Strafpost("Z4", 1, gewicht, slot.dag, (slot.uur,), klassen, leraren, lokalen, tekst))
    return posten


def strafposten(
    data: ProbleemData,
    toewijzingen: tuple[Toewijzing, ...],
    gewichten: dict[str, int],
    zware_vakken: tuple[str, ...] = (),
) -> list[Strafpost]:
    """Alle overtredingen van de zachte regels met gewicht > 0; de punten tellen op tot tel_straf."""
    posten: list[Strafpost] = []
    if gewichten.get("Z1", 0) > 0:
        posten += _gat_posten(
            data, toewijzingen, "Z1", gewichten["Z1"], lambda u: u.klas, lambda k: f"Klas {k}"
        )
    if gewichten.get("Z2", 0) > 0:
        posten += _gat_posten(
            data, toewijzingen, "Z2", gewichten["Z2"], lambda u: u.leraar_id,
            lambda l: f"Leraar {_leraarnaam(data, l)}",
        )
    if gewichten.get("Z3", 0) > 0:
        posten += _z3_posten(data, toewijzingen, gewichten["Z3"])
    if gewichten.get("Z4", 0) > 0:
        posten += _z4_posten(data, toewijzingen, gewichten["Z4"], zware_vakken)
    return posten


# --- Herplannen: wat er verandert tegenover het oude rooster ---

def wijzigingen(oud: tuple[Toewijzing, ...], nieuw: tuple[Toewijzing, ...]) -> list[Wijziging]:
    """De lesuren die van tijdslot of lokaal veranderen, per les vergeleken.

    De lesuren van één les zijn uitwisselbaar: een les die op dezelfde tijdslots blijft,
    telt niet als gewijzigd, ook als de lesuren van nummer ruilen.
    """
    oud_per_les, nieuw_per_les = _per_les(oud), _per_les(nieuw)
    lijst = []
    for les_id in sorted(set(oud_per_les) | set(nieuw_per_les)):
        van, naar = oud_per_les.get(les_id, {}), nieuw_per_les.get(les_id, {})
        weg = sorted(set(van) - set(naar))
        erbij = sorted(set(naar) - set(van))
        for i in range(max(len(weg), len(erbij))):
            s_van = weg[i] if i < len(weg) else None
            s_naar = erbij[i] if i < len(erbij) else None
            lijst.append(Wijziging(les_id, s_van, s_naar, van.get(s_van), naar.get(s_naar)))
        for s in sorted(set(van) & set(naar)):
            if van[s] != naar[s]:
                lijst.append(Wijziging(les_id, s, s, van[s], naar[s]))
    return lijst


def _per_les(toewijzingen: tuple[Toewijzing, ...]) -> dict[str, dict[int, str]]:
    """Per les: tijdslot -> lokaal."""
    per_les: dict[str, dict[int, str]] = defaultdict(dict)
    for t in toewijzingen:
        per_les[t.lesuur.les_id][t.tijdslot_id] = t.lokaal_id
    return per_les


def tel_verplaatst(lijst: list[Wijziging]) -> int:
    """Het aantal lesuren dat naar een ander tijdslot gaat (alleen een ander lokaal telt niet)."""
    return sum(1 for w in lijst if w.van_slot != w.naar_slot)
