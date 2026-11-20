"""Instellingen inlezen uit config.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path

from src.models import STANDAARD_GEWICHTEN, Instellingen

STANDAARD_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"


def laad_instellingen(pad: str | Path = STANDAARD_CONFIG) -> Instellingen:
    """Lees de instellingen; ontbrekende waarden krijgen de standaardwaarde."""
    pad = Path(pad)
    if not pad.exists():
        return Instellingen()
    with pad.open("rb") as bestand:
        inhoud = tomllib.load(bestand)
    gewichten = {**STANDAARD_GEWICHTEN, **{k: int(v) for k, v in inhoud.get("gewichten", {}).items()}}
    return Instellingen(
        float(inhoud.get("tijdslimiet_s", 30)),
        gewichten,
        float(inhoud.get("max_tijd_zoeken_s", 300)),
        tuple(str(vak) for vak in inhoud.get("zware_vakken", ())),
        int(inhoud.get("random_seed", 0)),
        max(int(inhoud.get("num_workers", 0)), 0),
        bool(inhoud.get("symmetrie_breken", False)),
    )
