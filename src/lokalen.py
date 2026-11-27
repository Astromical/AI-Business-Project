"""Lokalen toewijzen nadat de solver de tijdslots gekozen heeft. Kent geen SQLite en geen Streamlit.

Het model eist per tijdslot genoeg lokalen per type (H2 en H5), dus dit lukt altijd:
eerst krijgen de lesuren die hun eigen type moeten hebben een lokaal van dat type,
daarna krijgen de andere lesuren een vrij lokaal (bij voorkeur van hun eigen type).
"""

from __future__ import annotations

from collections import defaultdict

from src.constraints import blokparen, slotvolgorde
from src.models import Lokaal, ProbleemData, Toewijzing


def h5_geldt(soort: str, uitgeschakeld: frozenset[str]) -> bool:
    """Moet een lesuur van dit type in een lokaal van dat type staan?"""
    return "H5" not in uitgeschakeld and f"H5:{soort}" not in uitgeschakeld


Voorkeur = dict[tuple[str, int], str]  # (les_id, tijdslot_id) -> lokaal_id


def wijs_lokalen_toe(
    data: ProbleemData,
    plaatsing: dict[int, int],
    uitgeschakeld: frozenset[str] = frozenset(),
    voorkeur: Voorkeur | None = None,
) -> tuple[Toewijzing, ...]:
    """Maak toewijzingen uit plaatsing (lesuur-index -> tijdslot-id) door lokalen te kiezen.

    Voorkeur (als het lokaal past en vrij is): eerst het lokaal uit 'voorkeur' (bij
    herplannen: het oude lokaal), dan bij een blokuur het lokaal van het eerste uur, dan
    het lokaal van de vorige les van de klas. Zo blijft het rooster per lokaal rustig.
    """
    per_slot: dict[int, list[int]] = defaultdict(list)
    for l, s in plaatsing.items():
        per_slot[s].append(l)
    plaats = slotvolgorde(data)
    tweede_uur = {b: a for a, b in blokparen(data)}
    vorig: dict[str, str] = {}  # klas -> lokaal van haar vorige les
    toewijzingen: dict[int, Toewijzing] = {}
    for s in sorted(per_slot, key=lambda s: plaats.get(s, s)):
        wens = {}
        for l in per_slot[s]:
            eerste = toewijzingen.get(tweede_uur.get(l, -1))
            klas = vorig.get(data.lesuren[l].klas)
            wens[l] = [w for w in ((voorkeur or {}).get((data.lesuren[l].les_id, s)),
                                   eerste.lokaal_id if eerste else None, klas) if w]
        for l, lokaal_id in _lokalen_voor_slot(data, per_slot[s], uitgeschakeld, wens).items():
            toewijzingen[l] = Toewijzing(data.lesuren[l], s, lokaal_id)
            vorig[data.lesuren[l].klas] = lokaal_id
    return tuple(toewijzingen[l] for l in sorted(toewijzingen))  # in de volgorde van de lesuren


def _leerlingen(data: ProbleemData, l: int) -> int:
    """Het aantal leerlingen van een lesuur (0 als het onbekend is)."""
    return data.les_per_id[data.lesuren[l].les_id].aantal_leerlingen or 0


def _past(lokaal: Lokaal, leerlingen: int) -> bool:
    """Past een groep in dit lokaal (capaciteit None: geen grens)?"""
    return lokaal.capaciteit is None or lokaal.capaciteit >= leerlingen


def _lokalen_voor_slot(
    data: ProbleemData, lesuren: list[int], uitgeschakeld: frozenset[str], wens: dict[int, list[str]]
) -> dict[int, str]:
    """Kies voor elk lesuur in één tijdslot een ander lokaal.

    Eerst de lesuren die hun eigen type moeten krijgen, de grootste groep eerst: omdat
    een kleinere groep in elk lokaal past waar een grotere in past, lukt dat altijd als
    het model genoeg lokalen per type en grootte heeft geëist (H2, H5, H8).
    """
    vrij = list(data.lokalen)
    keuze: dict[int, str] = {}
    volgorde = sorted(lesuren, key=lambda l: (-_leerlingen(data, l), l))
    strikt = [l for l in volgorde if h5_geldt(data.lesuren[l].lokaaltype, uitgeschakeld)]
    for l in strikt + [l for l in volgorde if l not in strikt]:
        uur, n = data.lesuren[l], _leerlingen(data, l)
        passend = [r for r in vrij if r.type == uur.lokaaltype and _past(r, n)]
        if l not in strikt and not passend:  # H5 uit: elk lokaal, liefst een dat groot genoeg is
            passend = [r for r in vrij if _past(r, n)] or vrij
        lokaal = _kies(passend, wens.get(l, []))
        if lokaal is None:
            raise RuntimeError("Te weinig lokalen in een tijdslot; het model had dit moeten uitsluiten.")
        vrij.remove(lokaal)
        keuze[l] = lokaal.id
    return keuze


def _kies(kandidaten: list[Lokaal], wensen: list[str]) -> Lokaal | None:
    """Het eerste gewenste lokaal dat vrij is, anders het kleinste dat past; None als er geen is."""
    for wens in wensen:
        for lokaal in kandidaten:
            if lokaal.id == wens:
                return lokaal
    if not kandidaten:
        return None
    return min(kandidaten, key=lambda r: (r.capaciteit is None, r.capaciteit or 0))
