"""Opdrachtregel: python -m src.cli seed|solve|check."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from src.checker import controleer
from src.db import maak_schema, verbind
from src.loader import laad_probleem, valideer
from src.config import laad_instellingen
from src.models import Instellingen, ProbleemData, Resultaat, Toewijzing
from src.seed import LABEL, VARIANTEN, seed
from src.solver import solve

STANDAARD_PAD = "data/rooster.db"


def _seed(pad: str, variant: str) -> None:
    """Maak de database met schema en voorbeelddata."""
    Path(pad).parent.mkdir(parents=True, exist_ok=True)
    con = verbind(pad)
    try:
        maak_schema(con)
        seed(con, variant)
        (lesuren,) = con.execute("SELECT SUM(aantal_per_week) FROM les").fetchone()
    finally:
        con.close()
    print(f"Database '{pad}' gemaakt (variant '{variant}', {lesuren} lesuren).")
    print(LABEL)


def rooster_per_klas_tekst(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> str:
    """Het rooster als tekst, één blok per klas (rijen zijn uren, kolommen dagen)."""
    plek = {(t.lesuur.klas, t.tijdslot_id): t for t in toewijzingen}
    uren = sorted({slot.uur for slot in data.tijdslots})
    regels: list[str] = []
    for klas in data.klassen:
        regels.append(f"\nKlas {klas}")
        regels.append("uur " + "".join(f"{dag[:5]:<14}" for dag in data.dagen))
        for uur in uren:
            cellen = []
            for dag in data.dagen:
                slot = next((s for s in data.tijdslots if s.dag == dag and s.uur == uur), None)
                t = plek.get((klas, slot.id)) if slot else None
                cellen.append(f"{t.lesuur.vak[:8]} {t.lokaal_id}" if t else "-")
            regels.append(f"{uur:<4}" + "".join(f"{c:<14}" for c in cellen))
    return "\n".join(regels)


def _laad(pad: str) -> ProbleemData | None:
    """Laad de database en toon de meldingen; None bij een fout."""
    if not Path(pad).exists():
        print(f"Database '{pad}' bestaat niet. Maak hem eerst met: python -m src.cli seed")
        return None
    con = verbind(pad)
    try:
        data = laad_probleem(con)
    finally:
        con.close()
    meldingen = valideer(data)
    for melding in meldingen:
        print(f"{melding.ernst.upper()}: {melding.tekst}")
    if any(m.ernst == "fout" for m in meldingen):
        return None
    return data


def _instellingen(tijdslimiet_s: float | None) -> Instellingen:
    """Instellingen uit config.toml, met eventueel een andere tijdslimiet."""
    basis = laad_instellingen()
    if tijdslimiet_s is None:
        return basis
    return replace(basis, tijdslimiet_s=tijdslimiet_s)


def _tijden(resultaat: Resultaat) -> str:
    """Status met de tijd voor zoeken en verbeteren."""
    verbeteren = resultaat.oplostijd_s - resultaat.tijd_zoeken_s
    return (
        f"Status: {resultaat.status} ({resultaat.oplostijd_s:.1f} s: "
        f"zoeken {resultaat.tijd_zoeken_s:.1f} s, verbeteren {verbeteren:.1f} s)"
    )


def _solve(pad: str, tijdslimiet_s: float | None) -> None:
    """Laad, valideer, los op en druk het rooster af."""
    data = _laad(pad)
    if data is None:
        return
    resultaat = solve(data, _instellingen(tijdslimiet_s))
    print(_tijden(resultaat))
    if resultaat.toewijzingen:
        print(rooster_per_klas_tekst(data, resultaat.toewijzingen))


def _check(pad: str, tijdslimiet_s: float | None) -> None:
    """Los op en controleer het rooster onafhankelijk van de solver."""
    data = _laad(pad)
    if data is None:
        return
    resultaat = solve(data, _instellingen(tijdslimiet_s))
    print(_tijden(resultaat))
    if not resultaat.toewijzingen:
        print("Geen rooster om te controleren.")
        return
    schendingen = controleer(data, resultaat.toewijzingen)
    print(f"Schendingen van H1-H7: {len(schendingen)}")
    for schending in schendingen:
        print(f"  {schending.regel}: {schending.tekst}")


def main(argv: list[str] | None = None) -> None:
    """Verwerk de opdrachtregel."""
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    sub = parser.add_subparsers(dest="opdracht", required=True)
    p_seed = sub.add_parser("seed", help="maak de database met voorbeelddata")
    p_seed.add_argument("--pad", default=STANDAARD_PAD)
    p_seed.add_argument("--variant", choices=VARIANTEN, default="voorbeeld")
    p_solve = sub.add_parser("solve", help="los het rooster op")
    p_solve.add_argument("--pad", default=STANDAARD_PAD)
    p_solve.add_argument("--tijdslimiet", type=float, default=None)
    p_check = sub.add_parser("check", help="los op en controleer het rooster")
    p_check.add_argument("--pad", default=STANDAARD_PAD)
    p_check.add_argument("--tijdslimiet", type=float, default=None)
    args = parser.parse_args(argv)
    if args.opdracht == "seed":
        _seed(args.pad, args.variant)
    elif args.opdracht == "solve":
        _solve(args.pad, args.tijdslimiet)
    elif args.opdracht == "check":
        _check(args.pad, args.tijdslimiet)


if __name__ == "__main__":
    main()
