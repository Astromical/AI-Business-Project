"""Allerlei invoer omzetten naar de vaste lessen-CSV.

De uitkomst is altijd dezelfde tabel: klas, vak, leraar, uren_per_week, soort_lokaal.
Wanneer een les staat, beslist de solver; hoeveel uur een vak krijgt, is invoer. Bij een
bestaand rooster worden de uren daarom uit de duur van de blokken opgeteld.
Kent geen SQLite, geen Streamlit en geen OR-Tools.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Iterable

from openpyxl import load_workbook

from src.models import Melding

KOLOMMEN: tuple[str, ...] = ("klas", "vak", "leraar", "uren_per_week", "soort_lokaal")
SOORTEN_LOKAAL: tuple[str, ...] = ("regulier", "lab", "gym")
MAX_BYTES = 20_000_000

# Veld -> kolomnamen die we herkennen (kleine letters, leestekens als _).
ALIASSEN: dict[str, tuple[str, ...]] = {
    "klas": ("klas", "klassen", "class", "groep", "group", "reeks", "klasgroep"),
    "vak": ("vak", "vaknaam", "subject", "course", "opleidingsonderdeel", "olod", "les", "lesson"),
    "leraar": ("leraar", "leerkracht", "docent", "lector", "teacher", "lesgever", "naam_leraar"),
    "uren_per_week": ("uren_per_week", "uren", "aantal_per_week", "aantal_uren", "lesuren", "hours", "periods"),
    "soort_lokaal": ("soort_lokaal", "lokaaltype", "type_lokaal", "soort", "room_type"),
    "start": ("start", "begin", "starttijd", "beginuur", "van", "from"),
    "einde": ("einde", "eind", "eindtijd", "einduur", "tot", "end", "to"),
}
VERPLICHT: tuple[str, ...] = ("klas", "vak", "leraar")
LOKAAL_WOORDEN: dict[str, tuple[str, ...]] = {
    "lab": ("lab", "labo", "laboratorium", "practicum", "wetenschapslokaal"),
    "gym": ("gym", "sport", "sporthal", "turnzaal", "turnen"),
    "regulier": ("regulier", "gewoon", "klaslokaal", "normaal", "theorie"),
}


class ConversieFout(Exception):
    """Dit bestand kan niet omgezet worden; de tekst is bedoeld voor de gebruiker."""


@dataclass(frozen=True)
class LesRij:
    """Eén rij van de vaste lessen-CSV."""

    klas: str
    vak: str
    leraar: str
    uren_per_week: int
    soort_lokaal: str


@dataclass(frozen=True)
class Conversie:
    """De omgezette lessen, met wat er onderweg opviel."""

    rijen: tuple[LesRij, ...]
    meldingen: tuple[Melding, ...] = ()

    @property
    def heeft_fouten(self) -> bool:
        """Is er iets overgeslagen of niet overgenomen?"""
        return any(m.ernst == "fout" for m in self.meldingen)


def _norm(tekst: object) -> str:
    """Een kolomnaam of woord in kleine letters, met _ tussen de woorden."""
    return re.sub(r"[^a-z0-9]+", "_", str(tekst).lower()).strip("_")


def _tekst(waarde: object) -> str:
    """Een celwaarde als schone tekst; leeg bij niets."""
    return "" if waarde is None else str(waarde).strip()


def herken_kolommen(koppen: Iterable[str], kolommen: dict[str, str] | None = None) -> dict[str, str]:
    """Bepaal per veld de bronkolom; 'kolommen' (veld -> bronkolom) gaat voor op de herkenning."""
    koppen = [k for k in koppen if k is not None]
    gevonden = {_norm(k): k for k in koppen}
    koppeling = {
        veld: gevonden[naam]
        for veld, namen in ALIASSEN.items()
        for naam in reversed(namen)
        if naam in gevonden
    }
    for veld, bron in (kolommen or {}).items():
        if veld not in ALIASSEN:
            raise ConversieFout(f"Onbekend veld '{veld}'. Kies uit: {', '.join(ALIASSEN)}.")
        if bron not in koppen:
            raise ConversieFout(f"De kolom '{bron}' staat niet in het bestand.")
        koppeling[veld] = bron
    return koppeling


def _minuten(waarde: object) -> int | None:
    """Het tijdstip als minuten sinds middernacht, of None als het onleesbaar is."""
    if isinstance(waarde, (datetime, time)):
        return waarde.hour * 60 + waarde.minute
    gevonden = re.search(r"(?:^|[T\s])(\d{1,2})[:.hu](\d{2})", _tekst(waarde))
    return int(gevonden[1]) * 60 + int(gevonden[2]) if gevonden else None


def _uren_uit_rij(rij: dict, koppeling: dict[str, str]) -> float | None:
    """De uren van een rij: uit de urenkolom, anders uit start en einde."""
    if "uren_per_week" in koppeling:
        ruw = rij.get(koppeling["uren_per_week"])
        try:
            return float(_tekst(ruw).replace(",", "."))
        except ValueError:
            return None
    begin, einde = _minuten(rij.get(koppeling["start"])), _minuten(rij.get(koppeling["einde"]))
    return None if begin is None or einde is None else (einde - begin) / 60


def _soort_lokaal(waarde: object, standaard: str) -> tuple[str, bool]:
    """De soort lokaal en of die uit de waarde herkend is."""
    woord = _norm(_tekst(waarde))
    for soort, woorden in LOKAAL_WOORDEN.items():
        if woord in woorden:
            return soort, True
    return standaard, not woord


def _controleer_koppeling(koppeling: dict[str, str]) -> None:
    """Weiger een tabel waarin verplichte kolommen of de uren ontbreken."""
    ontbreekt = [veld for veld in VERPLICHT if veld not in koppeling]
    if ontbreekt:
        raise ConversieFout(f"Deze kolommen ontbreken: {', '.join(ontbreekt)}.")
    if "uren_per_week" not in koppeling and not {"start", "einde"} <= set(koppeling):
        raise ConversieFout(
            "Het aantal uren ontbreekt. De solver kiest wanneer een les staat, maar moet weten "
            "hoeveel uur een vak krijgt: voeg een kolom met uren toe, of start- en eindtijden."
        )


def _voeg_samen(
    verzameld: dict[tuple[str, str, str], list], meldingen: list[Melding]
) -> tuple[LesRij, ...]:
    """Maak van de opgetelde uren hele lesuren per klas, vak en leraar."""
    rijen = []
    for klas, vak, leraar, uren, soort in verzameld.values():
        hele = math.ceil(round(uren, 6))
        if hele != round(uren, 6):
            meldingen.append(
                Melding(
                    "waarschuwing",
                    f"{vak} voor {klas} heeft {uren:g} uur: afgerond naar {hele} lesuren.",
                )
            )
        rijen.append(LesRij(klas, vak, leraar, hele, soort))
    return tuple(sorted(rijen, key=lambda r: (r.klas, r.vak, r.leraar)))


def _lees_rij(
    nummer: int, rij: dict, koppeling: dict[str, str], standaard: str
) -> tuple[tuple[str, str, str, float, str] | None, Melding | None]:
    """Eén bronrij als (klas, vak, leraar, uren, soort), of de reden waarom dat niet lukt."""
    klas, vak, leraar = (_tekst(rij.get(koppeling[veld])) for veld in VERPLICHT)
    uren = _uren_uit_rij(rij, koppeling)
    if not (klas and vak and leraar):
        return None, Melding("fout", f"Rij {nummer} overgeslagen: klas, vak of leraar ontbreekt.")
    if uren is None or not math.isfinite(uren) or uren <= 0:
        return None, Melding("fout", f"Rij {nummer} overgeslagen: het aantal uren klopt niet.")
    ruw_soort = rij.get(koppeling.get("soort_lokaal", ""))
    soort, herkend = _soort_lokaal(ruw_soort, standaard)
    melding = None
    if not herkend:
        melding = Melding("waarschuwing", f"Rij {nummer}: soort lokaal '{ruw_soort}' is onbekend, gebruikt: {soort}.")
    return (klas, vak, leraar, uren, soort), melding


def _controleer_standaard(standaard_lokaal: str) -> None:
    """De standaardsoort moet een soort zijn die de app kent."""
    if standaard_lokaal not in SOORTEN_LOKAAL:
        raise ConversieFout(f"Soort lokaal moet een van deze zijn: {', '.join(SOORTEN_LOKAAL)}.")


def uit_rijen(
    rijen: list[dict[str, Any]],
    kolommen: dict[str, str] | None = None,
    standaard_lokaal: str = "regulier",
) -> Conversie:
    """Zet rijen (kolomnaam -> waarde) om; dubbele lessen worden bij elkaar opgeteld."""
    _controleer_standaard(standaard_lokaal)
    if not rijen:
        raise ConversieFout("Er staan geen rijen in deze gegevens.")
    koppeling = herken_kolommen(dict.fromkeys(k for rij in rijen for k in rij), kolommen)
    _controleer_koppeling(koppeling)
    meldingen: list[Melding] = []
    verzameld: dict[tuple[str, str, str], list] = {}
    for nummer, rij in enumerate(rijen, 1):
        gelezen, melding = _lees_rij(nummer, rij, koppeling, standaard_lokaal)
        if melding is not None:
            meldingen.append(melding)
        if gelezen is None:
            continue
        klas, vak, leraar, uren, soort = gelezen
        sleutel = (klas.lower(), vak.lower(), leraar.lower())
        if sleutel in verzameld:
            verzameld[sleutel][3] += uren
        else:
            verzameld[sleutel] = [klas, vak, leraar, uren, soort]
    if "soort_lokaal" not in koppeling:
        meldingen.append(
            Melding("waarschuwing", f"De soort lokaal staat niet in de gegevens: overal '{standaard_lokaal}' gebruikt.")
        )
    return Conversie(_voeg_samen(verzameld, meldingen), tuple(meldingen))


# --- bestanden lezen ---


def _lees_tekst(inhoud: bytes) -> list[dict[str, Any]]:
    """Lees CSV, TSV of vergelijkbaar; scheidingsteken en codering worden herkend."""
    try:
        tekst = inhoud.decode("utf-8-sig")
    except UnicodeDecodeError:
        tekst = inhoud.decode("cp1252", errors="replace")
    eerste = next((regel for regel in tekst.splitlines() if regel.strip()), "")
    scheiding = max(";,\t|", key=eerste.count)
    return [
        {k: v for k, v in rij.items() if k is not None}
        for rij in csv.DictReader(io.StringIO(tekst), delimiter=scheiding)
    ]


def _lees_excel(inhoud: bytes) -> list[dict[str, Any]]:
    """Lees het eerste werkblad met gegevens; de eerste gevulde rij is de kop."""
    boek = load_workbook(io.BytesIO(inhoud), read_only=True, data_only=True)
    try:
        for blad in boek.worksheets:
            rijen = [r for r in blad.iter_rows(values_only=True) if any(c is not None for c in r)]
            if rijen:
                koppen = [None if c is None else str(c).strip() for c in rijen[0]]
                return [{k: c for k, c in zip(koppen, r) if k} for r in rijen[1:]]
    finally:
        boek.close()
    return []


def is_webuntis(gegevens: object) -> bool:
    """Lijkt dit op een WebUntis-export van een weekrooster?"""
    return isinstance(gegevens, dict) and any(
        isinstance(dag, dict) and "gridEntries" in dag for dag in gegevens.get("days") or []
    )


def _tabel_uit_json(gegevens: object) -> list[dict[str, Any]]:
    """Vind de lijst met rijen: de JSON zelf, of de eerste lijst met objecten erin."""
    kandidaten = gegevens.values() if isinstance(gegevens, dict) else [gegevens]
    for waarde in kandidaten:
        if isinstance(waarde, list) and waarde and all(isinstance(r, dict) for r in waarde):
            return waarde
    raise ConversieFout("In deze JSON staat geen lijst met rijen.")


def _soort_bestand(naam: str, inhoud: bytes) -> str:
    """Bepaal het soort bestand uit de inhoud; de naam zegt niet altijd iets."""
    begin = inhoud[:8].lstrip()
    if begin.startswith(b"%PDF"):
        raise ConversieFout(
            "Een PDF kan niet gelezen worden. Zet de lessen in een CSV- of Excel-bestand en upload dat."
        )
    if inhoud[:4] == b"PK\x03\x04":
        return "excel"
    if inhoud[:4] == b"\xd0\xcf\x11\xe0":
        raise ConversieFout("Oude .xls-bestanden worden niet gelezen. Bewaar het bestand als .xlsx.")
    if begin[:1] in (b"{", b"["):
        return "json"
    if b"\x00" in inhoud[:1024]:
        raise ConversieFout(f"'{naam}' is geen tekst-, Excel- of JSON-bestand.")
    return "tekst"


def lees_bestand(naam: str, inhoud: bytes) -> tuple[str, Any]:
    """Lees een bestand als (soort, gegevens): rijen, of de ruwe JSON bij WebUntis."""
    if len(inhoud) > MAX_BYTES:
        raise ConversieFout(f"Dit bestand is groter dan {MAX_BYTES // 1_000_000} MB.")
    soort = _soort_bestand(naam, inhoud)
    try:
        if soort == "excel":
            return soort, _lees_excel(inhoud)
        if soort == "tekst":
            return soort, _lees_tekst(inhoud)
        gegevens = json.loads(inhoud.decode("utf-8-sig"))
    except ConversieFout:
        raise
    except Exception as fout:  # beschadigde bestanden geven veel soorten fouten
        raise ConversieFout(f"'{naam}' kon niet gelezen worden: {fout}") from fout
    if is_webuntis(gegevens):
        return "webuntis", gegevens
    return "json", _tabel_uit_json(gegevens)


def converteer(
    naam: str,
    inhoud: bytes,
    kolommen: dict[str, str] | None = None,
    standaard_lokaal: str = "regulier",
) -> Conversie:
    """Zet een bestand om naar de vaste lessen."""
    soort, gegevens = lees_bestand(naam, inhoud)
    if soort == "webuntis":
        return _uit_webuntis(gegevens, standaard_lokaal)
    return uit_rijen(gegevens, kolommen, standaard_lokaal)


# --- WebUntis ---


def _huidig(blok: dict, soort: str) -> list[dict]:
    """De huidige waarden van één soort (SUBJECT, TEACHER, ROOM, CLASS) in een blok."""
    waarden = (
        positie.get("current")
        for nummer in range(1, 8)
        for positie in blok.get(f"position{nummer}") or []
    )
    return [w for w in waarden if w and w.get("type") == soort]


def _naam(waarde: dict) -> str:
    """De leesbaarste naam van een WebUntis-waarde."""
    return _tekst(waarde.get("longName")) or _tekst(waarde.get("shortName"))


def _overlappingen(blokken: list[dict]) -> int:
    """Het aantal blokken dat begint voor het vorige is afgelopen."""
    duur = sorted((b["duration"]["start"], b["duration"]["end"]) for b in blokken)
    return sum(1 for (_, eind), (begin, _) in zip(duur, duur[1:]) if begin < eind)


def _webuntis_meldingen(blokken: list[dict], klas: str, dagen: int) -> list[Melding]:
    """Wat de app niet kan overnemen uit een WebUntis-rooster."""
    tellers = {
        f"{{}} van {len(blokken)} blokken hebben meerdere docenten: alleen de eerste is overgenomen.": sum(
            len(_huidig(b, "TEACHER")) > 1 for b in blokken
        ),
        f"{{}} van {len(blokken)} blokken gebruiken meerdere lokalen: de app plant er één.": sum(
            len(_huidig(b, "ROOM")) > 1 for b in blokken
        ),
        f"{{}} van {len(blokken)} blokken zijn gedeeld met andere klassen: ze staan nu alleen bij {klas}, "
        "dus de andere klassen ontbreken.": sum(len(_huidig(b, "CLASS")) > 1 for b in blokken),
        f"{{}} blokken overlappen elkaar: die vakken staan in aparte groepen ({klas}-2, ...). De solver "
        f"kan ze ook tegelijk met andere lessen van {klas} zetten; controleer dat zelf.": _overlappingen(blokken),
    }
    meldingen = [Melding("fout", tekst.format(n)) for tekst, n in tellers.items() if n]
    if dagen > 7:
        meldingen.append(Melding("fout", f"Dit rooster beslaat {dagen} dagen: de uren zijn opgeteld alsof het één week is."))
    meldingen.append(Melding("waarschuwing", "Blokken worden losse lesuren: de solver houdt ze niet bij elkaar."))
    meldingen.append(Melding("waarschuwing", "Onbeschikbaarheid en maximum uren per dag staan niet in dit bestand."))
    return meldingen


def _sleutel(blok: dict) -> tuple[str, str]:
    """Vak en eerste docent van een blok."""
    vakken, docenten = _huidig(blok, "SUBJECT"), _huidig(blok, "TEACHER")
    return (_naam(vakken[0]) if vakken else "", _naam(docenten[0]) if docenten else "")


def _blokuren(blokken: list[dict]) -> dict[tuple[str, str], float]:
    """Het aantal uren per vak en docent."""
    uren: dict[tuple[str, str], float] = {}
    for blok in blokken:
        duur = datetime.fromisoformat(blok["duration"]["end"]) - datetime.fromisoformat(blok["duration"]["start"])
        uren[_sleutel(blok)] = uren.get(_sleutel(blok), 0) + duur.total_seconds() / 3600
    return uren


def _botsingen(blokken: list[dict]) -> dict[tuple[str, str], set[tuple[str, str]]]:
    """Per vak de vakken die er ergens parallel mee lopen."""
    botst: dict[tuple[str, str], set[tuple[str, str]]] = {_sleutel(b): set() for b in blokken}
    for i, een in enumerate(blokken):
        for ander in blokken[i + 1:]:
            samen = een["duration"]["start"] < ander["duration"]["end"] and ander["duration"]["start"] < een["duration"]["end"]
            if samen and _sleutel(een) != _sleutel(ander):
                botst[_sleutel(een)].add(_sleutel(ander))
                botst[_sleutel(ander)].add(_sleutel(een))
    return botst


def _verdeel_in_groepen(blokken: list[dict], klas: str) -> dict[tuple[str, str], str]:
    """Geef elk vak een groep, zodat parallelle vakken nooit in dezelfde groep zitten.

    Een klas kan in het model maar één les tegelijk volgen; parallelle lessen krijgen daarom
    een eigen groep. De groep met de meeste uren houdt de naam van de klas.
    """
    botst, uren = _botsingen(blokken), _blokuren(blokken)
    nummer: dict[tuple[str, str], int] = {}
    for vak in sorted(botst, key=lambda v: (-len(botst[v]), -uren[v], v)):
        bezet = {nummer[ander] for ander in botst[vak] if ander in nummer}
        nummer[vak] = next(n for n in range(len(botst) + 1) if n not in bezet)
    per_groep: dict[int, float] = {}
    for vak, groep in nummer.items():
        per_groep[groep] = per_groep.get(groep, 0) + uren[vak]
    volgorde = sorted(per_groep, key=lambda g: (-per_groep[g], g))
    namen = {g: klas if i == 0 else f"{klas}-{i + 1}" for i, g in enumerate(volgorde)}
    return {vak: namen[groep] for vak, groep in nummer.items()}


def _uit_webuntis(gegevens: dict, standaard_lokaal: str) -> Conversie:
    """Tel per vak de uren uit een WebUntis-klasrooster op."""
    dagen = [d for d in gegevens["days"] if d.get("gridEntries")]
    soorten = {d.get("resourceType") for d in dagen}
    if soorten != {"CLASS"}:
        raise ConversieFout("Alleen het rooster van een klas kan omgezet worden, niet dat van een docent of lokaal.")
    namen = {d["resource"]["shortName"] for d in dagen}
    if len(namen) != 1:
        raise ConversieFout("Dit bestand bevat meerdere klassen; zet ze één voor één om.")
    klas = namen.pop()
    alle = [b for d in dagen for b in d["gridEntries"]]
    blokken = [b for b in alle if b.get("status") != "CANCELLED"]
    if not blokken:
        raise ConversieFout("In dit rooster staan geen lessen.")
    groepen = _verdeel_in_groepen(blokken, klas)
    rijen = [
        {
            "klas": groepen[_sleutel(b)],
            "vak": _sleutel(b)[0],
            "leraar": _sleutel(b)[1],
            "start": b["duration"]["start"],
            "einde": b["duration"]["end"],
        }
        for b in blokken
    ]
    uitkomst = uit_rijen(rijen, standaard_lokaal=standaard_lokaal)
    extra = _webuntis_meldingen(blokken, klas, len({d["date"] for d in gegevens["days"]}))
    return Conversie(uitkomst.rijen, (*extra, *uitkomst.meldingen))


# --- uitvoer ---


def naar_csv(rijen: Iterable[LesRij]) -> str:
    """De lessen als CSV in het vaste formaat."""
    uit = io.StringIO()
    schrijver = csv.writer(uit, lineterminator="\n")
    schrijver.writerow(KOLOMMEN)
    schrijver.writerows((r.klas, r.vak, r.leraar, r.uren_per_week, r.soort_lokaal) for r in rijen)
    return uit.getvalue()
