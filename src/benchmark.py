"""Reproduceerbare meting van de solver op de voorbeelddata.

Bouwt de data in een tijdelijke database in het geheugen (via seed en loader), lost
het rooster een aantal keer op en meldt per run de tijden, status en strafscore,
samen met de hardware en de instellingen. Zo is een meting te herhalen en te vergelijken.
"""

from __future__ import annotations

import os
import platform
import statistics
from dataclasses import dataclass, replace

from ortools import __version__ as ortools_versie

from src.checker import controleer
from src.db import maak_schema, verbind
from src.loader import laad_probleem
from src.models import Instellingen, ProbleemData
from src.seed import seed
from src.solver import aantal_werkers, solve


@dataclass(frozen=True)
class Run:
    """De uitkomst van één run."""

    status: str
    totaal_s: float
    zoeken_s: float
    strafscore: int | None
    straf_per_regel: dict[str, int]
    schendingen: int


def laad_variant(variant: str, pauze_na_uur: int = 0) -> ProbleemData:
    """De voorbeelddata van een variant, zonder bestand op schijf."""
    con = verbind(":memory:")
    try:
        maak_schema(con)
        seed(con, variant)
        return laad_probleem(con, pauze_na_uur)
    finally:
        con.close()


def meet(data: ProbleemData, instellingen: Instellingen, runs: int) -> list[Run]:
    """Los het rooster runs keer op en controleer het telkens onafhankelijk."""
    uitkomsten = []
    for _ in range(runs):
        r = solve(data, instellingen)
        uitkomsten.append(
            Run(
                r.status,
                r.oplostijd_s,
                r.tijd_zoeken_s,
                r.strafscore,
                dict(r.straf_per_regel),
                len(controleer(data, r.toewijzingen)),
            )
        )
    return uitkomsten


def omgeving(instellingen: Instellingen) -> list[str]:
    """Hardware, software en instellingen van de meting, als leesbare regels."""
    return [
        f"Processor: {platform.processor() or platform.machine()} ({os.cpu_count()} logische kernen)",
        f"Systeem: {platform.system()} {platform.release()}, Python {platform.python_version()}, "
        f"OR-Tools {ortools_versie}",
        f"Verbetertijd (fase 2): {instellingen.tijdslimiet_s:.0f} s, seed {instellingen.random_seed}, "
        f"zoekdraden {aantal_werkers(instellingen)}"
        + (" (alle kernen)" if instellingen.num_workers == 0 else ""),
        f"Gewichten: {instellingen.gewichten}, zware vakken: {', '.join(instellingen.zware_vakken) or 'geen'}",
    ]


def rapport(variant: str, instellingen: Instellingen, uitkomsten: list[Run]) -> str:
    """Een tekstrapport van de meting."""
    regels = [f"Meting op variant '{variant}'", *omgeving(instellingen), ""]
    for i, r in enumerate(uitkomsten, 1):
        regels.append(
            f"Run {i}: {r.status}, totaal {r.totaal_s:.1f} s (zoeken {r.zoeken_s:.1f} s), "
            f"strafscore {r.strafscore} {r.straf_per_regel}, schendingen {r.schendingen}"
        )
    tijden = [r.totaal_s for r in uitkomsten]
    scores = [r.strafscore for r in uitkomsten if r.strafscore is not None]
    regels.append(
        f"Mediaan: {statistics.median(tijden):.1f} s"
        + (f", strafscore {min(scores)} tot {max(scores)}" if scores else "")
    )
    return "\n".join(regels)


def benchmark(
    variant: str, instellingen: Instellingen, runs: int = 3, num_workers: int | None = None
) -> str:
    """Meet een variant en geef het rapport; num_workers overschrijft de instelling."""
    if num_workers is not None:
        instellingen = replace(instellingen, num_workers=num_workers)
    data = laad_variant(variant, instellingen.pauze_na_uur)
    return rapport(variant, instellingen, meet(data, instellingen, runs))
