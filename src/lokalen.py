"""Lokalen toewijzen nadat de solver de tijdslots gekozen heeft. Kent geen SQLite en geen Streamlit.

Het model eist per tijdslot genoeg lokalen per type (H2 en H5), dus dit lukt altijd:
eerst krijgen de lesuren die hun eigen type moeten hebben een lokaal van dat type,
daarna krijgen de andere lesuren een vrij lokaal (bij voorkeur van hun eigen type).
"""

from __future__ import annotations

from collections import defaultdict

from src.constraints import slotvolgorde
from src.models import Lokaal, ProbleemData, Toewijzing


def h5_geldt(soort: str, uitgeschakeld: frozenset[str]) -> bool:
    """Moet een lesuur van dit type in een lokaal van dat type staan?"""
    return "H5" not in uitgeschakeld and f"H5:{soort}" not in uitgeschakeld


def wijs_lokalen_toe(
    data: ProbleemData, plaatsing: dict[int, int], uitgeschakeld: frozenset[str] = frozenset()
) -> tuple[Toewijzing, ...]:
    """Maak toewijzingen uit plaatsing (lesuur-index -> tijdslot-id) door lokalen te kiezen.

    Een klas houdt waar het kan hetzelfde lokaal als in haar vorige les, zodat het
    rooster per lokaal rustig blijft.
    """
    per_slot: dict[int, list[int]] = defaultdict(list)
    for l, s in plaatsing.items():
        per_slot[s].append(l)
    plaats = slotvolgorde(data)
    vorig: dict[str, str] = {}  # klas -> lokaal van haar vorige les
    toewijzingen: dict[int, Toewijzing] = {}
    for s in sorted(per_slot, key=lambda s: plaats.get(s, s)):
        for l, lokaal_id in _lokalen_voor_slot(data, per_slot[s], uitgeschakeld, vorig).items():
            toewijzingen[l] = Toewijzing(data.lesuren[l], s, lokaal_id)
            vorig[data.lesuren[l].klas] = lokaal_id
    return tuple(toewijzingen[l] for l in sorted(toewijzingen))  # in de volgorde van de lesuren


def _lokalen_voor_slot(
    data: ProbleemData, lesuren: list[int], uitgeschakeld: frozenset[str], vorig: dict[str, str]
) -> dict[int, str]:
    """Kies voor elk lesuur in één tijdslot een ander lokaal."""
    vrij = list(data.lokalen)
    keuze: dict[int, str] = {}
    strikt = [l for l in sorted(lesuren) if h5_geldt(data.lesuren[l].lokaaltype, uitgeschakeld)]
    vrij_te_kiezen = [l for l in sorted(lesuren) if l not in strikt]
    for l in strikt + vrij_te_kiezen:
        uur = data.lesuren[l]
        passend = [r for r in vrij if r.type == uur.lokaaltype]
        kandidaten = passend if l in strikt or passend else vrij
        lokaal = _kies(kandidaten, vorig.get(uur.klas))
        if lokaal is None:
            raise RuntimeError("Te weinig lokalen in een tijdslot; het model had dit moeten uitsluiten.")
        vrij.remove(lokaal)
        keuze[l] = lokaal.id
    return keuze


def _kies(kandidaten: list[Lokaal], voorkeur: str | None) -> Lokaal | None:
    """Het lokaal met de voorkeur als dat vrij is, anders het eerste vrije; None als er geen is."""
    for lokaal in kandidaten:
        if lokaal.id == voorkeur:
            return lokaal
    return kandidaten[0] if kandidaten else None
