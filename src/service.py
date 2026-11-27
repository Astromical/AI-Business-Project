"""Logica voor de app, zonder Streamlit: database openen, laden en berekenen."""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from src import auth, beheer, db
from src.checker import (
    controleer,
    strafposten,
    tel_per_regel,
    tel_straf,
    tel_tussenuren,
    wijzigingen,
)
from src.db import (
    OpslaanFout,
    bewaar_rooster,
    laad_rooster,
    leeg_database,
    maak_schema,
    verbind,
)
from src.config import laad_instellingen
from src.conversie import converteer
from src.loader import laad_probleem, valideer
from src.models import (
    DAGEN,
    Afwezigheid,
    Gebruiker,
    Instellingen,
    Melding,
    ProbleemData,
    Resultaat,
    Rol,
    Schending,
    Strafpost,
    Toewijzing,
    Wijziging,
    met_afwezigheid,
)
from src.seed import seed
from src.solver import Voortgang, herplan, solve, verbeter_verder
from src.uitleg import verklaar


@dataclass(frozen=True)
class Poging:
    """Eén run: rooster berekenen of verder verbeteren, met de strafscore ervoor en erna."""

    soort: str  # "berekenen" of "verder verbeteren"
    voor: int | None  # strafscore van het rooster waarvan de run vertrok (None: geen)
    na: int | None  # strafscore van het rooster dat na de run overblijft
    tijd_s: float
    verbeterd: bool  # True als de run een beter rooster opleverde


@dataclass(frozen=True)
class Berekening:
    """Een berekend rooster met de uitkomst van de onafhankelijke controle."""

    resultaat: Resultaat
    schendingen: tuple[Schending, ...]
    tussenuren: int = 0
    bewaard: bool = False  # True als het rooster uit de database komt
    uitleg: tuple[str, ...] = ()  # waarom er geen rooster is (alleen bij 'onoplosbaar')
    data: ProbleemData | None = None  # de gegevens waarop het rooster berekend is
    tellingen: dict[str, int] = field(default_factory=dict)  # aantal per zachte regel
    vorige_strafscore: int | None = None  # strafscore van het rooster vóór 'verder rekenen'
    # elke overtreding van een zachte regel, met de gewichten van deze berekening
    strafposten: tuple[Strafpost, ...] = ()
    gewichten: dict[str, int] = field(default_factory=dict)  # gewichten van deze berekening
    geschiedenis: tuple[Poging, ...] = ()  # de runs die tot dit rooster geleid hebben
    afwezig: Afwezigheid = frozenset()  # bij herplannen: de afwezige (leraar, tijdslot)-paren
    wijzigingen: tuple[Wijziging, ...] = ()  # bij herplannen: wat er veranderde


def vergelijkbaar(a: Berekening, b: Berekening) -> bool:
    """Gaan twee berekeningen over dezelfde gegevens, gewichten en afwezigheid?"""
    return a.data == b.data and a.gewichten == b.gewichten and a.afwezig == b.afwezig


def is_beter(nieuw: Berekening, oud: Berekening) -> bool:
    """Is nieuw een geldig rooster met minder strafpunten dan oud, in dezelfde situatie?

    Een rooster zonder schendingen wint altijd van een rooster met schendingen of zonder
    rooster. Roosters voor andere gegevens, gewichten of afwezigheid zijn niet te vergelijken.
    """
    if not _is_geldig(nieuw):
        return False
    if not _is_geldig(oud):
        return True
    if not vergelijkbaar(nieuw, oud):
        return False
    a, b = nieuw.resultaat.strafscore, oud.resultaat.strafscore
    return a is not None and (b is None or a < b)


def _is_geldig(berekening: Berekening) -> bool:
    """Heeft deze berekening een rooster zonder schendingen?"""
    return bool(berekening.resultaat.toewijzingen) and not berekening.schendingen


def _posten(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], instellingen: Instellingen
) -> tuple[Strafpost, ...]:
    """De strafposten van een rooster volgens de onafhankelijke checker."""
    return tuple(strafposten(data, toewijzingen, instellingen.gewichten, instellingen.zware_vakken))


def is_actueel(berekening: Berekening, data: ProbleemData) -> bool:
    """Hoort deze berekening nog bij de gegevens zoals ze nu in de database staan?"""
    return berekening.data == data


def open_database(pad: str | Path) -> sqlite3.Connection:
    """Open de database en zorg dat het schema bestaat."""
    Path(pad).parent.mkdir(parents=True, exist_ok=True)
    con = verbind(pad)
    maak_schema(con)
    return con


def vul_voorbeeld(pad: str | Path, variant: str) -> None:
    """Wis de database en vul hem met voorbeelddata (variant 'voorbeeld', 'onmogelijk' of 'groot')."""
    con = open_database(pad)
    try:
        seed(con, variant)
    finally:
        con.close()


DATASETS_MAP = Path(__file__).resolve().parent.parent / "data" / "datasets"
UREN_PER_DAG_DATASET = 8  # zoals bij AP: 09:00-13:00 en 14:00-18:00


def datasets() -> dict[str, Path]:
    """De lessenbestanden (CSV) in data/datasets op naam; leeg als de map ontbreekt."""
    return {bestand.stem: bestand for bestand in sorted(DATASETS_MAP.glob("*.csv"))}


def laad_dataset(pad: str | Path, bestand: Path) -> None:
    """Wis de gegevens en lees een lessenbestand in, zoals de pagina Importeren; accounts blijven."""
    uitkomst = converteer(bestand.name, bestand.read_bytes())
    if uitkomst.heeft_fouten or not uitkomst.rijen:
        raise OpslaanFout(f"{bestand.name} kon niet volledig omgezet worden.")
    con = open_database(pad)
    try:
        leeg_database(con)
        db.maak_tijdslots(con, {dag: UREN_PER_DAG_DATASET for dag in DAGEN})
        beheer.vul_basis_aan(con, uitkomst.rijen)
        beheer.importeer(con, uitkomst.rijen)
    finally:
        con.close()


def maak_leeg(pad: str | Path) -> None:
    """Verwijder alle gegevens uit de database."""
    con = open_database(pad)
    try:
        leeg_database(con)
    finally:
        con.close()


def laad(pad: str | Path) -> tuple[ProbleemData, list[Melding]]:
    """Laad de gegevens en geef ze samen met de meldingen van de validatie."""
    con = open_database(pad)
    try:
        data = laad_probleem(con, laad_instellingen().pauze_na_uur)
    finally:
        con.close()
    return data, valideer(data)


def heeft_fouten(meldingen: list[Melding]) -> bool:
    """Is er minstens één melding met ernst 'fout'?"""
    return any(m.ernst == "fout" for m in meldingen)


def aantallen(data: ProbleemData) -> dict[str, int]:
    """De aantallen die de app bovenaan toont."""
    return {
        "Klassen": len(data.klassen),
        "Leraren": len(data.leraren),
        "Lokalen": len(data.lokalen),
        "Tijdslots": len(data.tijdslots),
        "Lesuren": len(data.lesuren),
    }


UITLEG_MAX_S = 15.0  # de uitleg bij een onoplosbaar rooster duurt in totaal hoogstens zo lang


def bereken(
    data: ProbleemData, instellingen: Instellingen | None = None, voortgang: Voortgang | None = None
) -> Berekening:
    """Los het rooster op en controleer het onafhankelijk.

    Met een voortgang is de stand live te volgen en kan het rekenen gestopt worden.
    """
    instellingen = instellingen or Instellingen()
    resultaat = solve(data, instellingen, voortgang=voortgang)
    schendingen = tuple(controleer(data, resultaat.toewijzingen)) if resultaat.toewijzingen else ()
    tussenuren = sum(tel_tussenuren(data, resultaat.toewijzingen).values())
    uitleg: tuple[str, ...] = ()
    if resultaat.status == "onoplosbaar":
        if voortgang is not None:
            voortgang.fase = "uitleg"
        tijdslimiet = min(UITLEG_MAX_S, max(instellingen.tijdslimiet_s, 5.0))
        uitleg = verklaar(data, tijdslimiet).teksten
    tellingen = tel_per_regel(data, resultaat.toewijzingen, instellingen.zware_vakken)
    return Berekening(
        resultaat, schendingen, tussenuren, uitleg=uitleg, data=data, tellingen=tellingen,
        strafposten=_posten(data, resultaat.toewijzingen, instellingen),
        gewichten=dict(instellingen.gewichten),
        geschiedenis=(
            Poging("berekenen", None, resultaat.strafscore, resultaat.oplostijd_s,
                   bool(resultaat.toewijzingen)),
        ),
    )


def kan_verder(berekening: Berekening) -> bool:
    """Is er een geldig rooster dat nog niet bewezen optimaal is?"""
    resultaat = berekening.resultaat
    geldig = bool(resultaat.toewijzingen) and not berekening.schendingen
    return geldig and resultaat.status != "optimaal" and not berekening.afwezig


def reken_verder(
    data: ProbleemData,
    berekening: Berekening,
    instellingen: Instellingen | None = None,
    voortgang: Voortgang | None = None,
) -> Berekening:
    """Reken verder vanaf het rooster van een berekening; dat rooster blijft de veilige versie."""
    instellingen = instellingen or Instellingen()
    oud = berekening.resultaat.toewijzingen
    vorige = sum(tel_straf(data, oud, instellingen.gewichten, instellingen.zware_vakken).values())
    resultaat = verbeter_verder(data, oud, instellingen, voortgang=voortgang)
    resultaat, verbeterd = _houd_beste(data, instellingen, oud, vorige, resultaat)
    nieuw = resultaat.toewijzingen
    poging = Poging("verder verbeteren", vorige, resultaat.strafscore, resultaat.oplostijd_s, verbeterd)
    return Berekening(
        resultaat,
        tuple(controleer(data, nieuw)),
        sum(tel_tussenuren(data, nieuw).values()),
        data=data,
        tellingen=tel_per_regel(data, nieuw, instellingen.zware_vakken),
        vorige_strafscore=vorige,
        strafposten=_posten(data, nieuw, instellingen),
        gewichten=dict(instellingen.gewichten),
        geschiedenis=berekening.geschiedenis + (poging,),
    )


def _houd_beste(
    data: ProbleemData,
    instellingen: Instellingen,
    oud: tuple[Toewijzing, ...],
    vorige: int,
    resultaat: Resultaat,
) -> tuple[Resultaat, bool]:
    """Tweede vangnet, met de onafhankelijke checker: neem het nieuwe rooster alleen als
    het geldig is en strikt minder strafpunten heeft; anders blijft het oude staan.

    Geeft het resultaat dat blijft en of dat een verbetering is.
    """
    nieuw = resultaat.toewijzingen
    if nieuw == oud:
        return resultaat, False
    straf = tel_straf(data, nieuw, instellingen.gewichten, instellingen.zware_vakken)
    if nieuw and not controleer(data, nieuw) and sum(straf.values()) < vorige:
        return resultaat, True
    oud_straf = tel_straf(data, oud, instellingen.gewichten, instellingen.zware_vakken)
    veilig = Resultaat("geldig", oud, resultaat.oplostijd_s, vorige, oud_straf, gestopt=resultaat.gestopt)
    return veilig, False


def afwezigheid(pad: str | Path) -> Afwezigheid:
    """De afwezigheid die bij het laatste herplannen is ingevuld."""
    con = open_database(pad)
    try:
        return db.lees_afwezig(con)
    finally:
        con.close()


def herplan_rooster(
    pad: str | Path,
    data: ProbleemData,
    berekening: Berekening,
    afwezig: Afwezigheid,
    instellingen: Instellingen | None = None,
    voortgang: Voortgang | None = None,
) -> Berekening:
    """Pas het rooster van een berekening aan voor afwezige leraren, met zo weinig mogelijk wijzigingen.

    De afwezigheid wordt bewaard; het rooster in de database blijft staan tot je opslaat.
    Gecontroleerd met de checker, met de afwezige uren als onbeschikbaar.
    """
    instellingen = instellingen or Instellingen()
    con = open_database(pad)
    try:
        db.zet_afwezig(con, afwezig)
    finally:
        con.close()
    oud = berekening.resultaat.toewijzingen
    resultaat = herplan(data, oud, afwezig, instellingen, voortgang)
    nieuw = resultaat.toewijzingen
    return Berekening(
        resultaat,
        tuple(controleer(met_afwezigheid(data, afwezig), nieuw)) if nieuw else (),
        sum(tel_tussenuren(data, nieuw).values()),
        data=data,
        tellingen=tel_per_regel(data, nieuw, instellingen.zware_vakken),
        strafposten=_posten(data, nieuw, instellingen),
        gewichten=dict(instellingen.gewichten),
        afwezig=afwezig,
        wijzigingen=tuple(wijzigingen(oud, nieuw)) if nieuw else (),
    )


def bewaar(pad: str | Path, toewijzingen: tuple[Toewijzing, ...]) -> None:
    """Sla het rooster op in de database."""
    con = open_database(pad)
    try:
        bewaar_rooster(con, toewijzingen)
    finally:
        con.close()


def bewaard_rooster(
    pad: str | Path, data: ProbleemData, instellingen: Instellingen | None = None
) -> Berekening | None:
    """Het bewaarde rooster met controle en strafscore, of None als er geen is.

    De status is 'geldig' zonder schendingen en 'ongeldig' als het rooster niet meer
    bij de gegevens past. De strafscore volgt de gewichten uit de instellingen.
    """
    instellingen = instellingen or Instellingen()
    con = open_database(pad)
    try:
        toewijzingen = laad_rooster(con)
    finally:
        con.close()
    if not toewijzingen:
        return None
    schendingen = tuple(controleer(data, toewijzingen))
    zware_vakken = instellingen.zware_vakken
    straf = tel_straf(data, toewijzingen, instellingen.gewichten, zware_vakken)
    status = "ongeldig" if schendingen else "geldig"
    return Berekening(
        Resultaat(status, toewijzingen, 0.0, sum(straf.values()), straf),
        schendingen,
        sum(tel_tussenuren(data, toewijzingen).values()),
        True,
        data=data,
        tellingen=tel_per_regel(data, toewijzingen, zware_vakken),
        strafposten=_posten(data, toewijzingen, instellingen),
        gewichten=dict(instellingen.gewichten),
    )


def heeft_gebruikers(pad: str | Path) -> bool:
    """Bestaat er al een account in deze database?"""
    con = open_database(pad)
    try:
        return db.heeft_gebruikers(con)
    finally:
        con.close()


def zoek_gebruiker(pad: str | Path, naam: str) -> Gebruiker | None:
    """Het account met deze naam, zoals het nu in de database staat."""
    con = open_database(pad)
    try:
        return db.lees_gebruiker(con, naam)
    finally:
        con.close()


def gebruikers(pad: str | Path) -> list[Gebruiker]:
    """Alle accounts."""
    con = open_database(pad)
    try:
        return db.lees_gebruikers(con)
    finally:
        con.close()


def log_in(pad: str | Path, naam: str, wachtwoord: str) -> Gebruiker | None:
    """Het account als naam en wachtwoord kloppen, anders None."""
    naam = _schone_naam(naam)
    con = open_database(pad)
    try:
        opgeslagen = db.lees_wachtwoord_hash(con, naam)
        if opgeslagen is None:
            auth.hash_wachtwoord(wachtwoord)  # even lang rekenen, zodat de naam niet uitlekt
            return None
        return db.lees_gebruiker(con, naam) if auth.controleer_wachtwoord(wachtwoord, opgeslagen) else None
    finally:
        con.close()


def _schone_naam(naam: str) -> str:
    """Gebruikersnamen zijn hoofdletterongevoelig en zonder spaties eromheen."""
    return naam.strip().lower()


def _controleer_invoer(naam: str, wachtwoord: str) -> None:
    """Weiger een lege naam of een te kort wachtwoord."""
    if not naam:
        raise OpslaanFout("Vul een gebruikersnaam in.")
    _controleer_wachtwoord(wachtwoord)


def _controleer_wachtwoord(wachtwoord: str) -> None:
    """Weiger een te kort wachtwoord."""
    if len(wachtwoord) < auth.MINIMALE_LENGTE:
        raise OpslaanFout(f"Een wachtwoord heeft minstens {auth.MINIMALE_LENGTE} tekens.")


def _sessiesleutel(pad: str | Path) -> bytes:
    """De geheime sleutel voor sessiecodes, naast de database; wordt aangemaakt als hij ontbreekt."""
    bestand = Path(pad).parent / ".sessiesleutel"
    bestand.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(bestand, "xb") as uit:  # nooit een bestaande sleutel overschrijven
            uit.write(os.urandom(32))
        bestand.chmod(0o600)
    except FileExistsError:
        pass
    return bestand.read_bytes()


def maak_sessiecode(pad: str | Path, naam: str) -> str:
    """Een sessiecode voor deze gebruiker."""
    return auth.maak_sessiecode(naam, _sessiesleutel(pad), time.time())


def naam_uit_sessiecode(pad: str | Path, code: str) -> str | None:
    """De gebruikersnaam uit een geldige sessiecode, of None."""
    return auth.lees_sessiecode(code, _sessiesleutel(pad), time.time())


def maak_eerste_roostermaker(pad: str | Path, naam: str, wachtwoord: str) -> None:
    """Maak de eerste roostermaker; werkt alleen zolang er geen enkel account is."""
    naam = _schone_naam(naam)
    _controleer_invoer(naam, wachtwoord)
    con = open_database(pad)
    try:
        if not db.voeg_eerste_roostermaker_toe(con, naam, auth.hash_wachtwoord(wachtwoord)):
            raise OpslaanFout("Er bestaat al een account. Log in of vraag het aan de roostermaker.")
    finally:
        con.close()


def _leraren_zonder_account(con: sqlite3.Connection) -> list[dict]:
    """De leraren (id, naam) waaraan nog geen account gekoppeld is."""
    gekoppeld = {g.leraar_id for g in db.lees_gebruikers(con)}
    return [r for r in db.lees_tabel(con, "leraar") if r["id"] not in gekoppeld]


def leraren_zonder_account(pad: str | Path) -> int:
    """Hoeveel leraren nog geen account hebben."""
    con = open_database(pad)
    try:
        return len(_leraren_zonder_account(con))
    finally:
        con.close()


def _vrije_gebruikersnaam(basis: str, bezet: set[str]) -> str:
    """basis, of basis-2, basis-3, ... als die naam al bestaat."""
    naam, volgnummer = basis, 2
    while naam in bezet:
        naam, volgnummer = f"{basis}-{volgnummer}", volgnummer + 1
    bezet.add(naam)
    return naam


def maak_leraaraccounts(pad: str | Path) -> list[str]:
    """Maak een account met LERAAR_WACHTWOORD voor elke leraar zonder account; geef de namen.

    Bestaande accounts blijven ongemoeid.
    """
    con = open_database(pad)
    try:
        bezet = {g.naam for g in db.lees_gebruikers(con)}
        nieuw = [
            Gebruiker(_vrije_gebruikersnaam(_schone_naam(leraar["id"]), bezet), "leraar", leraar["id"])
            for leraar in _leraren_zonder_account(con)
        ]
        db.voeg_gebruikers_toe(con, [(g, auth.hash_wachtwoord(auth.LERAAR_WACHTWOORD)) for g in nieuw])
        return [g.naam for g in nieuw]
    finally:
        con.close()


def maak_gebruiker(
    pad: str | Path, naam: str, wachtwoord: str, rol: Rol, leraar_id: str | None = None
) -> None:
    """Maak een nieuw account aan."""
    naam = _schone_naam(naam)
    _controleer_invoer(naam, wachtwoord)
    con = open_database(pad)
    try:
        db.voeg_gebruiker_toe(con, Gebruiker(naam, rol, leraar_id), auth.hash_wachtwoord(wachtwoord))
    finally:
        con.close()


def wijzig_gebruiker(pad: str | Path, gebruiker: Gebruiker) -> None:
    """Wijzig de rol en de gekoppelde leraar van een account."""
    con = open_database(pad)
    try:
        db.wijzig_gebruiker(con, gebruiker)
    finally:
        con.close()


def zet_wachtwoord(pad: str | Path, naam: str, wachtwoord: str) -> None:
    """Geef een account een nieuw wachtwoord."""
    _controleer_wachtwoord(wachtwoord)
    con = open_database(pad)
    try:
        db.wijzig_wachtwoord(con, naam, auth.hash_wachtwoord(wachtwoord))
    finally:
        con.close()


def verwijder_gebruiker(pad: str | Path, naam: str) -> None:
    """Verwijder een account."""
    con = open_database(pad)
    try:
        db.verwijder_gebruiker(con, naam)
    finally:
        con.close()
