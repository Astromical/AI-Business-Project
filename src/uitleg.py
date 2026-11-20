"""Uitleg bij een onoplosbaar rooster: welke versoepeling lost het probleem op?

Aanpak: één model met per versoepelbare regel (H5 per lokaaltype, H6 en H7 per
leraar) een schakelaar die zegt of de regel geldt. CP-SAT zet zo weinig mogelijk
regels uit zodat er toch een rooster bestaat. Die kleinste set is ook minimaal: geen
enkele versoepeling eruit kan weg. Alles samen blijft binnen één tijdsbudget.
Kent geen SQLite en geen Streamlit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Literal

from ortools.sat.python import cp_model

from src.models import Instellingen, Leraar, ProbleemData
from src.solver import GEEN_ZACHTE_REGELS, harde_regels, maak_variabelen, nieuwe_solver, solve

Versoepeling = tuple[str, str]  # (regel, sleutel): ("H6", leraar_id), ("H7", leraar_id), ("H5", type)
Uitkomst = Literal["gevonden", "geen", "onbekend"]


@dataclass(frozen=True)
class Uitleg:
    """De gevonden oorzaken en een tekst voor de gebruiker."""

    oorzaken: tuple[Versoepeling, ...]
    teksten: tuple[str, ...]


def _kandidaten(data: ProbleemData) -> list[Versoepeling]:
    """Alle regels die je per leraar of lokaaltype kunt versoepelen, in vaste volgorde."""
    met_lessen = {uur.leraar_id for uur in data.lesuren}
    kandidaten: list[Versoepeling] = [("H5", soort) for soort in sorted({u.lokaaltype for u in data.lesuren})]
    kandidaten += [("H6", l.id) for l in data.leraren if l.id in met_lessen and l.onbeschikbaar]
    kandidaten += [("H7", l.id) for l in data.leraren if l.id in met_lessen]
    return sorted(kandidaten)


def _pas_toe(
    data: ProbleemData, versoepelingen: set[Versoepeling]
) -> tuple[ProbleemData, frozenset[str]]:
    """Maak data en uitgeschakelde regels waarin de versoepelingen zijn doorgevoerd."""
    maximum = len(data.tijdslots)
    leraren: list[Leraar] = []
    for leraar in data.leraren:
        if ("H6", leraar.id) in versoepelingen:
            leraar = replace(leraar, onbeschikbaar=frozenset())
        if ("H7", leraar.id) in versoepelingen:
            leraar = replace(leraar, max_uren_per_dag=maximum)
        leraren.append(leraar)
    uitgeschakeld = frozenset(f"H5:{sleutel}" for regel, sleutel in versoepelingen if regel == "H5")
    return replace(data, leraren=tuple(leraren)), uitgeschakeld


def _oplosbaar(data: ProbleemData, versoepelingen: set[Versoepeling], tijdslimiet_s: float) -> bool:
    """Is er een rooster als deze regels versoepeld zijn? (Geen tijd = niet bewezen.)"""
    versoepeld, uitgeschakeld = _pas_toe(data, versoepelingen)
    instellingen = Instellingen(tijdslimiet_s, GEEN_ZACHTE_REGELS, tijdslimiet_s)
    return solve(versoepeld, instellingen, uitgeschakeld).status in ("optimaal", "geldig")


def _resterend(einde: float) -> float:
    """De seconden tot het einde van het budget (nooit negatief)."""
    return max(einde - time.monotonic(), 0.0)


def _kleinste_versoepeling(data: ProbleemData, einde: float) -> tuple[Uitkomst, tuple[Versoepeling, ...], bool]:
    """Eén solve: zet zo weinig mogelijk regels uit zodat er een rooster bestaat.

    Geeft de uitkomst, de versoepelingen en of bewezen is dat het de kleinste set is.
    Bij gelijke grootte gaan de laatste kandidaten (H7 voor H6 voor H5) eerst uit.
    """
    kandidaten = _kandidaten(data)
    model = cp_model.CpModel()
    x = maak_variabelen(model, data)
    geldt = {k: model.NewBoolVar(f"geldt_{k[0]}_{k[1]}") for k in kandidaten}
    harde_regels(model, x, data, schakelaars=geldt)
    n = len(kandidaten)
    model.Minimize(sum((n * n + n - i) * (1 - geldt[k]) for i, k in enumerate(kandidaten)))
    solver = nieuwe_solver(_resterend(einde))
    code = solver.Solve(model)
    if code == cp_model.INFEASIBLE:
        return "geen", (), True
    if code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return "onbekend", (), False
    versoepeld = tuple(k for k in kandidaten if not solver.Value(geldt[k]))
    return "gevonden", versoepeld, code == cp_model.OPTIMAL


def _zoek_oorzaak(data: ProbleemData, einde: float) -> tuple[Uitkomst, tuple[Versoepeling, ...]]:
    """De kleinste set versoepelingen; niet bewezen kleinst, dan nog een deletiefilter."""
    uitkomst, huidig, bewezen = _kleinste_versoepeling(data, einde)
    if uitkomst != "gevonden" or bewezen:
        return uitkomst, tuple(sorted(huidig))
    over = set(huidig)
    for kandidaat in sorted(huidig):
        if _resterend(einde) > 0 and _oplosbaar(data, over - {kandidaat}, _resterend(einde)):
            over.discard(kandidaat)
    return "gevonden", tuple(sorted(over))


def minimale_oorzaak(data: ProbleemData, tijdslimiet_s: float = 10) -> tuple[Versoepeling, ...] | None:
    """Een minimale set versoepelingen die het probleem oplost; None als geen set helpt
    (of als dat binnen tijdslimiet_s seconden in totaal niet te bepalen is)."""
    uitkomst, oorzaken = _zoek_oorzaak(data, time.monotonic() + tijdslimiet_s)
    return oorzaken if uitkomst == "gevonden" else None


def _slots_die_helpen(
    data: ProbleemData, leraar: Leraar, einde: float, max_aantal: int = 3
) -> list[int]:
    """Onbeschikbare tijdslots van een leraar die elk afzonderlijk het probleem oplossen.

    Eén model waarin precies één van die tijdslots vrijgegeven wordt; na elke vondst
    gaat dat tijdslot uit de keuze, tot er max_aantal zijn of geen meer helpt.
    """
    slots = sorted(leraar.onbeschikbaar)
    model = cp_model.CpModel()
    x = maak_variabelen(model, data)
    vrij = {s: model.NewBoolVar(f"vrij_{s}") for s in slots}
    harde_regels(model, x, data, schakelaars={("H6", leraar.id, s): vrij[s].Not() for s in slots})
    model.AddExactlyOne(vrij.values())
    helpt: list[int] = []
    while len(helpt) < max_aantal and _resterend(einde) > 0:
        solver = nieuwe_solver(_resterend(einde))
        if solver.Solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        gevonden = next(s for s in slots if solver.Value(vrij[s]))
        helpt.append(gevonden)
        model.Add(vrij[gevonden] == 0)
    return sorted(helpt)


def _tekst(data: ProbleemData, v: Versoepeling, enkel: bool, einde: float) -> str:
    """De uitleg voor één versoepeling."""
    regel, sleutel = v
    if regel == "H5":
        return (
            f"Zonder de eis dat lessen van het type '{sleutel}' in een lokaal van dat type staan, "
            f"lukt het wel. Er zijn waarschijnlijk te weinig lokalen van het type '{sleutel}' "
            f"op de momenten dat ze nodig zijn: overweeg een extra lokaal."
        )
    leraar = data.leraar_per_id[sleutel]
    if regel == "H7":
        return (
            f"Zonder het maximum van {leraar.max_uren_per_dag} uur per dag voor {leraar.naam} lukt het wel. "
            f"Kijk of {leraar.naam} op sommige dagen meer uren mag geven."
        )
    tekst = f"Zonder de onbeschikbaarheid van {leraar.naam} lukt het wel."
    if enkel:  # alleen noemen wat uit de analyse blijkt
        slots = _slots_die_helpen(data, leraar, einde)
        if slots:
            namen = ", ".join(
                f"{data.tijdslot_per_id[s].dag} uur {data.tijdslot_per_id[s].uur}" for s in slots
            )
            return tekst + f" Kijk of {leraar.naam} op {namen} toch kan."
    return tekst + f" Kijk of {leraar.naam} op meer momenten beschikbaar kan zijn."


GEEN_OORZAAK = (
    "Ook zonder de onbeschikbaarheid, het maximum per dag en de lokaaltypes blijft er "
    "geen rooster mogelijk. Op sommige momenten zijn er te veel lessen tegelijk nodig "
    "voor dezelfde klas, leraar of hetzelfde lokaal. Controleer de lessen en het aantal lokalen."
)


def verklaar(data: ProbleemData, tijdslimiet_s: float = 10) -> Uitleg:
    """Leg uit waarom er geen rooster bestaat, in het Nederlands, binnen tijdslimiet_s in totaal."""
    einde = time.monotonic() + tijdslimiet_s
    uitkomst, oorzaken = _zoek_oorzaak(data, einde)
    if uitkomst == "onbekend":
        return Uitleg((), (
            f"Binnen {tijdslimiet_s:.0f} seconden is niet gevonden welke regel het probleem "
            "veroorzaakt. Controleer de onbeschikbaarheid, het maximum per dag en het aantal lokalen.",
        ))
    if uitkomst == "geen":
        return Uitleg((), (GEEN_OORZAAK,))
    if len(oorzaken) > 1:
        kop = "Meerdere regels samen veroorzaken het probleem:"
        regels = tuple(_tekst(data, v, False, einde) for v in oorzaken)
        return Uitleg(oorzaken, (kop, *regels))
    return Uitleg(oorzaken, (_tekst(data, oorzaken[0], True, einde),))
