"""Domeinklassen van de roostersolver, los van SQLite en Streamlit."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import cached_property
from typing import Literal

DAGEN: tuple[str, ...] = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag")

LokaalType = Literal["regulier", "lab", "gym"]
Ernst = Literal["fout", "waarschuwing"]
# 'ongeldig' komt alleen voor bij een bewaard rooster dat niet meer bij de gegevens past.
Status = Literal["optimaal", "geldig", "ongeldig", "onoplosbaar", "geen_oplossing_binnen_tijd"]
Rol = Literal["roostermaker", "leraar"]

ROLLEN: tuple[Rol, ...] = ("roostermaker", "leraar")

STANDAARD_GEWICHTEN: dict[str, int] = {"Z1": 10, "Z2": 5, "Z3": 5, "Z4": 2}


@dataclass(frozen=True)
class Tijdslot:
    """Eén lesuur op één dag."""

    id: int
    dag: str
    uur: int


@dataclass(frozen=True)
class Lokaal:
    """Een lokaal van een bepaald type; capaciteit None betekent: geen grens bekend."""

    id: str
    naam: str
    type: LokaalType
    capaciteit: int | None = None


@dataclass(frozen=True)
class Leraar:
    """Een leraar met een maximum per dag en onbeschikbare tijdslots."""

    id: str
    naam: str
    max_uren_per_dag: int
    onbeschikbaar: frozenset[int] = frozenset()


@dataclass(frozen=True)
class Les:
    """Een vak voor een klas, zoals het in de database staat.

    Met blokuur komen de lesuren per twee na elkaar op dezelfde dag (H9).
    aantal_leerlingen (None: onbekend) moet in het lokaal passen (H8).
    """

    id: str
    vak: str
    klas: str
    leraar_id: str
    aantal_per_week: int
    lokaaltype: LokaalType
    blokuur: bool = False
    aantal_leerlingen: int | None = None


@dataclass(frozen=True)
class Lesuur:
    """Eén in te plannen uur van een les."""

    les_id: str
    volgnummer: int
    vak: str
    klas: str
    leraar_id: str
    lokaaltype: LokaalType


@dataclass(frozen=True)
class ProbleemData:
    """Alle invoer voor de solver, met handige opzoekingen."""

    tijdslots: tuple[Tijdslot, ...]
    lokalen: tuple[Lokaal, ...]
    leraren: tuple[Leraar, ...]
    lessen: tuple[Les, ...]
    lesuren: tuple[Lesuur, ...]
    pauze_na_uur: int = 0  # een blokuur loopt niet over deze pauze (0: geen pauze)

    @cached_property
    def klassen(self) -> tuple[str, ...]:
        """Alle klassen uit de lessen, gesorteerd en zonder dubbels."""
        return tuple(sorted({les.klas for les in self.lessen}))

    @cached_property
    def dagen(self) -> tuple[str, ...]:
        """De dagen met minstens één tijdslot, in weekvolgorde."""
        aanwezig = {slot.dag for slot in self.tijdslots}
        return tuple(dag for dag in DAGEN if dag in aanwezig)

    @cached_property
    def uren_per_dag(self) -> dict[str, int]:
        """Het aantal tijdslots per dag, in weekvolgorde."""
        return {
            dag: sum(1 for slot in self.tijdslots if slot.dag == dag)
            for dag in self.dagen
        }

    @cached_property
    def tijdslot_per_id(self) -> dict[int, Tijdslot]:
        """Tijdslots opzoeken op id."""
        return {slot.id: slot for slot in self.tijdslots}

    @cached_property
    def lokaal_per_id(self) -> dict[str, Lokaal]:
        """Lokalen opzoeken op id."""
        return {lokaal.id: lokaal for lokaal in self.lokalen}

    @cached_property
    def leraar_per_id(self) -> dict[str, Leraar]:
        """Leraren opzoeken op id."""
        return {leraar.id: leraar for leraar in self.leraren}

    @cached_property
    def les_per_id(self) -> dict[str, Les]:
        """Lessen opzoeken op id."""
        return {les.id: les for les in self.lessen}


@dataclass(frozen=True)
class Toewijzing:
    """Een lesuur ingepland in een tijdslot en een lokaal."""

    lesuur: Lesuur
    tijdslot_id: int
    lokaal_id: str


@dataclass(frozen=True)
class Resultaat:
    """De uitkomst van de solver."""

    status: Status
    toewijzingen: tuple[Toewijzing, ...]
    oplostijd_s: float  # totale tijd: zoeken plus verbeteren
    strafscore: int | None = 0  # None: niet uit te rekenen (het rooster zelf is wel geldig)
    straf_per_regel: dict[str, int] = field(default_factory=dict)
    tijd_zoeken_s: float = 0.0  # tijd tot het eerste geldige rooster (fase 1)
    gestopt: bool = False  # True als de gebruiker het rekenen heeft gestopt


@dataclass(frozen=True)
class Gebruiker:
    """Een account zonder wachtwoord; leraar_id verwijst naar de eigen leraar, als die er is."""

    naam: str
    rol: Rol
    leraar_id: str | None = None


@dataclass(frozen=True)
class Melding:
    """Een probleem dat de validatie vooraf vindt."""

    ernst: Ernst
    tekst: str


@dataclass(frozen=True)
class Schending:
    """Een harde regel die een rooster schendt, gevonden door de checker."""

    regel: str
    lesuren: tuple[Lesuur, ...]
    tekst: str


@dataclass(frozen=True)
class Strafpost:
    """Eén overtreding van een zachte regel, met wie en wat erbij betrokken is.

    aantal is het aantal overtredingen in deze post (bij Z3 kan dat meer dan 1 zijn);
    punten is gewicht × aantal. De punten van alle posten samen zijn de strafscore.
    """

    regel: str
    aantal: int
    punten: int
    dag: str
    uren: tuple[int, ...]
    klassen: tuple[str, ...]
    leraren: tuple[str, ...]  # namen
    lokalen: tuple[str, ...]  # namen
    tekst: str


@dataclass(frozen=True)
class Instellingen:
    """Tijd om te verbeteren, gewichten van de zachte regels, de zoekgrens en de zware vakken.

    tijdslimiet_s geldt voor fase 2 (verbeteren) en begint pas te lopen zodra er een
    geldig rooster is. max_tijd_zoeken_s is de bovengrens voor fase 1 (zoeken).
    zware_vakken zijn de vakken die Z4 liever niet in het laatste uur ziet.
    random_seed maakt de zoektocht herhaalbaar; num_workers is het aantal zoekdraden
    van CP-SAT (0: zoveel als de computer processorkernen heeft). symmetrie_breken legt
    de lesuren van één les in weekvolgorde (standaard uit: dat bleek trager).
    pauze_na_uur: een blokuur mag niet over de pauze na dit uur lopen (0: geen pauze).
    """

    tijdslimiet_s: float = 30
    gewichten: dict[str, int] = field(
        default_factory=lambda: dict(STANDAARD_GEWICHTEN)
    )
    max_tijd_zoeken_s: float = 300
    zware_vakken: tuple[str, ...] = ()
    random_seed: int = 0
    num_workers: int = 0
    symmetrie_breken: bool = False
    pauze_na_uur: int = 0


Afwezigheid = frozenset[tuple[str, int]]  # (leraar_id, tijdslot_id)


def met_afwezigheid(data: ProbleemData, afwezig: Afwezigheid) -> ProbleemData:
    """De gegevens met de afwezige tijdslots erbij als onbeschikbaar (H6)."""
    extra: dict[str, set[int]] = {}
    for leraar_id, slot in afwezig:
        extra.setdefault(leraar_id, set()).add(slot)
    leraren = tuple(
        replace(l, onbeschikbaar=l.onbeschikbaar | frozenset(extra[l.id])) if l.id in extra else l
        for l in data.leraren
    )
    return replace(data, leraren=leraren)


@dataclass(frozen=True)
class Wijziging:
    """Een lesuur dat bij het herplannen van tijdslot of lokaal verandert (None: geen)."""

    les_id: str
    van_slot: int | None
    naar_slot: int | None
    van_lokaal: str | None
    naar_lokaal: str | None
