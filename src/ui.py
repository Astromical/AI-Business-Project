"""Gedeelde Streamlit-onderdelen, zoals de zijbalk."""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from typing import Callable

import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError

from src import service
from src.auth import MINIMALE_LENGTE, Recht, mag
from src.config import laad_instellingen
from src.db import OpslaanFout
from src.models import Gebruiker, Instellingen
from src.seed import LABEL

STANDAARD_PAD = "data/rooster.db"

# recht -> (pagina, titel). De navigatie toont alleen wat de rol mag.
PAGINAS: dict[Recht, tuple[str, str]] = {
    "gegevens": ("paginas/1_Gegevens.py", "Gegevens"),
    "importeren": ("paginas/6_Importeren.py", "Importeren"),
    "rooster": ("paginas/2_Rooster.py", "Rooster"),
    "eigen_rooster": ("paginas/3_Mijn_rooster.py", "Mijn rooster"),
    "accounts": ("paginas/4_Gebruikers.py", "Gebruikers"),
}

# Hoe een rol in de app heet; intern blijft de rol "leraar".
ROL_NAMEN: dict[str, str] = {"roostermaker": "Roostermaker", "leraar": "Docent"}

# Naam van elke gebouwde zachte regel, voor de schuifregelaars en de tellingen.
ZACHTE_REGEL_NAMEN: dict[str, str] = {
    "Z1": "Tussenuren klassen",
    "Z2": "Tussenuren docenten",
    "Z3": "Dubbele vakuren",
    "Z4": "Zware vakken laatste uur",
}


def _wis_berekening() -> None:
    """Vergeet het berekende rooster als de gegevens veranderen."""
    st.session_state.pop("berekening", None)


def database_pad() -> str:
    """Het databasepad van deze sessie."""
    return st.session_state.setdefault("pad", STANDAARD_PAD)


def _vergeet_sessie() -> None:
    """Wis alles van deze gebruiker uit de sessie en de adresbalk; alleen het databasepad blijft."""
    for sleutel in list(st.session_state):
        if sleutel != "pad":
            del st.session_state[sleutel]
    if "sessie" in st.query_params:
        del st.query_params["sessie"]


def _naam_uit_adres() -> str | None:
    """De gebruiker uit de sessiecode in de adresbalk, bijvoorbeeld na het vernieuwen."""
    code = st.query_params.get("sessie")
    if not code:
        return None
    naam = service.naam_uit_sessiecode(database_pad(), code)
    if naam is None:  # verlopen of vervalst
        del st.query_params["sessie"]
    else:
        st.session_state["sessie"] = code
    return naam


def _bewaar_in_adres(naam: str) -> None:
    """Zet de sessiecode in de adresbalk, zodat vernieuwen de login niet wist."""
    if "sessie" not in st.session_state:
        st.session_state["sessie"] = service.maak_sessiecode(database_pad(), naam)
    if st.query_params.get("sessie") != st.session_state["sessie"]:
        st.query_params["sessie"] = st.session_state["sessie"]


def huidige_gebruiker() -> Gebruiker | None:
    """De ingelogde gebruiker, elke keer opnieuw uit de database gelezen.

    Zo geldt een gewijzigde rol meteen en verliest een verwijderd account meteen zijn toegang.
    """
    naam = st.session_state.get("gebruiker") or _naam_uit_adres()
    if naam is None:
        return None
    gebruiker = service.zoek_gebruiker(database_pad(), naam)
    if gebruiker is None:
        _vergeet_sessie()
        return None
    st.session_state["gebruiker"] = gebruiker.naam
    _bewaar_in_adres(gebruiker.naam)
    return gebruiker


def vereis_recht(recht: Recht) -> Gebruiker:
    """Stop de pagina als de gebruiker niet is ingelogd of dit recht niet heeft."""
    gebruiker = huidige_gebruiker()
    if gebruiker is None:
        st.warning("Log eerst in.")
        st.stop()
    if not mag(gebruiker.rol, recht):
        st.error("Je hebt geen toegang tot deze pagina.")
        st.stop()
    return gebruiker


def link_naar(recht: Recht, tekst: str | None = None) -> None:
    """Toon een link naar de pagina bij dit recht, alleen als de gebruiker dat recht heeft."""
    gebruiker = huidige_gebruiker()
    if gebruiker is None or not mag(gebruiker.rol, recht):
        return
    bestand, titel = PAGINAS[recht]
    try:
        st.page_link(bestand, label=tekst or titel, icon=":material/arrow_forward:")
    except StreamlitPageNotFoundError:
        # pagina los gestart (zoals in de tests), dus zonder navigatie van app.py
        st.caption(f"Ga in de zijbalk naar {titel}.")


def lege_start(demodata: bool) -> None:
    """Uitleg en links zolang er nog geen lessen zijn."""
    st.info("**Welkom!** Voeg eerst lessen toe, dan maakt de app er een weekrooster van.")
    link_naar("importeren", "Lessen importeren uit Excel, CSV of JSON")
    link_naar("gegevens", "Lessen zelf invullen")
    if demodata:
        st.caption("Wil je de app eerst uitproberen? Open **Voorbeelddata** in de zijbalk en laad een voorbeeld.")


def inlogscherm() -> None:
    """Toon het inlogformulier, of het aanmaken van het eerste account; smal en in het midden."""
    pad = database_pad()
    with st.columns([1, 2, 1])[1]:
        if service.heeft_gebruikers(pad):
            _inloggen(pad)
        else:
            _eerste_roostermaker(pad)


def _log_in_als(gebruiker: Gebruiker) -> None:
    """Begin een nieuwe sessie voor deze gebruiker."""
    _vergeet_sessie()
    st.session_state["gebruiker"] = gebruiker.naam
    st.rerun()


def _inloggen(pad: str) -> None:
    """Het gewone inlogscherm."""
    st.caption("SCHOOLROOSTER")
    st.title("Inloggen")
    st.write("Welkom terug. Log in met je gebruikersnaam en wachtwoord.")
    with st.form("inloggen"):
        naam = st.text_input("Gebruikersnaam")
        wachtwoord = st.text_input("Wachtwoord", type="password")
        verstuurd = st.form_submit_button("Inloggen", type="primary", width="stretch")
    st.caption("Wachtwoord vergeten? Vraag een roostermaker om een nieuw wachtwoord in te stellen.")
    if verstuurd:
        gebruiker = service.log_in(pad, naam, wachtwoord)
        if gebruiker is None:
            st.error("Gebruikersnaam of wachtwoord klopt niet.")
        else:
            _log_in_als(gebruiker)


def _eerste_roostermaker(pad: str) -> None:
    """Het allereerste account aanmaken; daarna ben je meteen ingelogd."""
    st.caption("SCHOOLROOSTER · EERSTE START")
    st.title("Account aanmaken")
    st.write(
        "Er is nog geen enkel account. Het account dat je nu maakt, wordt **roostermaker**: "
        "je voert daarna de gegevens in, berekent roosters en maakt accounts voor leraren."
    )
    with st.form("eerste_roostermaker"):
        naam = st.text_input("Kies een gebruikersnaam")
        wachtwoord = st.text_input(
            "Kies een wachtwoord", type="password", help=f"Minstens {MINIMALE_LENGTE} tekens."
        )
        herhaal = st.text_input("Herhaal het wachtwoord", type="password")
        verstuurd = st.form_submit_button("Account aanmaken", type="primary", width="stretch")
    if not verstuurd:
        return
    if wachtwoord != herhaal:
        st.error("De twee wachtwoorden zijn niet gelijk.")
        return
    try:
        service.maak_eerste_roostermaker(pad, naam, wachtwoord)
    except OpslaanFout as fout:
        st.error(f"Niet aangemaakt: {fout}")
        return
    _log_in_als(service.log_in(pad, naam, wachtwoord))


# variant -> (naam, uitleg) voor de keuze in de zijbalk
VOORBEELDEN: dict[str, tuple[str, str]] = {
    "voorbeeld": ("Gewone school", "6 klassen en 144 lesuren; rekent in enkele seconden."),
    "onmogelijk": ("Onmogelijk rooster", "Te veel lesuren: toont hoe de app uitlegt wat niet past."),
    "groot": ("Grote school", "16 klassen en 512 lesuren; rekenen duurt ongeveer 45 seconden."),
}


def _keuzes() -> dict[str, tuple[str, str]]:
    """De verzonnen voorbeelden plus de lokale datasets uit data/datasets."""
    lokaal = {
        f"dataset:{naam}": (naam, "Echte lessen, overgetikt uit WebUntis. Zie data/datasets/LEESMIJ.md.")
        for naam in service.datasets()
    }
    return {**VOORBEELDEN, **lokaal}


def _laad_keuze(pad: str, keuze: str) -> None:
    """Laad een verzonnen voorbeeld of een lokale dataset."""
    if keuze in VOORBEELDEN:
        service.vul_voorbeeld(pad, keuze)
    else:
        service.laad_dataset(pad, service.datasets()[keuze.removeprefix("dataset:")])


def _voorbeeldkeuze(pad: str) -> None:
    """Een voorbeeld of dataset kiezen en laden, met uitleg over wat er vervangen wordt."""
    keuzes = _keuzes()
    with st.expander("Voorbeelddata", icon=":material/science:"):
        keuze = st.selectbox(
            "Kies een voorbeeld", list(keuzes), format_func=lambda k: keuzes[k][0], key="voorbeeld_variant"
        )
        label = LABEL if keuze in VOORBEELDEN else "Echte gegevens: niet in git."
        st.caption(f"{keuzes[keuze][1]} {label}")
        st.caption("Vervangt alle lessen, leraren, lokalen en het bewaarde rooster. Accounts blijven.")
        if st.button("Voorbeeld laden", type="primary", width="stretch"):
            try:
                _laad_keuze(pad, keuze)
            except OpslaanFout as fout:
                st.error(str(fout))
                return
            _wis_berekening()
            st.toast(f"{keuzes[keuze][0]} geladen.", icon=":material/check:")


def _geavanceerd(pad: str, met_regels: bool, database: bool) -> tuple[str, Instellingen | None]:
    """Ingeklapt blok met de regels (op de pagina Rooster) en de database; geef pad en instellingen."""
    instellingen = None
    with st.expander("Geavanceerd", icon=":material/settings:"):
        if met_regels:
            instellingen = _regelinstellingen()
        if met_regels and database:
            st.divider()
        if database:
            pad = _database(pad)
    return pad, instellingen


def _database(pad: str) -> str:
    """Databasepad en database leegmaken; geef het pad terug."""
    st.markdown("**Database**")
    pad = st.text_input(
        "Databasepad", value=pad, key="pad_invoer",
        help="Het bestand waarin alle gegevens staan. Meestal hoef je dit niet te veranderen.",
    )
    st.session_state["pad"] = pad
    zeker = st.checkbox("Ik weet zeker dat ik alles wil wissen")
    if st.button("Database leegmaken", disabled=not zeker, width="stretch"):
        service.maak_leeg(pad)
        _wis_berekening()
        st.toast("Database leeggemaakt.", icon=":material/check:")
    return pad


def _regelinstellingen() -> Instellingen:
    """Schuifregelaars voor de verbetertijd en de gewichten van de zachte regels."""
    standaard = laad_instellingen()
    st.markdown("**Regels en rekentijd**")
    tijdslimiet = st.slider(
        "Tijd om te verbeteren (seconden)", 1, 120, int(standaard.tijdslimiet_s),
        key="tijdslimiet_s", help="Loopt pas zodra er een geldig rooster is gevonden.",
    )
    gewichten = dict(standaard.gewichten)
    for regel, naam in ZACHTE_REGEL_NAMEN.items():
        gewichten[regel] = st.slider(
            f"Gewicht {naam.lower()} ({regel})", 0, 20, standaard.gewichten.get(regel, 0),
            key=f"gewicht_{regel.lower()}", help="0 zet deze regel uit.",
        )
    zwaar = ", ".join(standaard.zware_vakken) or "geen"
    st.caption(
        f"Zware vakken (Z4): {zwaar}. Zoeken naar een eerste geldig rooster duurt hoogstens "
        f"{standaard.max_tijd_zoeken_s:.0f} seconden. Beide instelbaar in config.toml."
    )
    return replace(standaard, tijdslimiet_s=float(tijdslimiet), gewichten=gewichten)


def _kopregel(gebruiker: Gebruiker) -> None:
    """Bovenaan elke pagina: links de rol in het groot, rechts de knop om uit te loggen."""
    links, rechts = st.columns([5, 1], vertical_alignment="center")
    links.subheader(ROL_NAMEN.get(gebruiker.rol, gebruiker.rol), anchor=False)
    if rechts.button("Uitloggen", icon=":material/logout:"):
        _vergeet_sessie()
        st.rerun()


def _zijbalk(met_regels: bool) -> tuple[str, Instellingen | None]:
    """Kopregel, voorbeelddata en het blok Geavanceerd; geef pad en (eventueel) instellingen."""
    pad = database_pad()
    gebruiker = huidige_gebruiker()
    if gebruiker is None:
        return pad, None
    _kopregel(gebruiker)
    database = mag(gebruiker.rol, "demodata")
    if not (database or met_regels):
        return pad, None
    with st.sidebar:
        if database:
            _voorbeeldkeuze(pad)
        return _geavanceerd(pad, met_regels, database)


def zijbalk() -> str:
    """Toon de kopregel en, voor de roostermaker, de databaseknoppen; geef het pad terug."""
    return _zijbalk(met_regels=False)[0]


def zijbalk_met_regels() -> tuple[str, Instellingen]:
    """Zoals zijbalk, met de regels en de rekentijd in het blok Geavanceerd."""
    pad, instellingen = _zijbalk(met_regels=True)
    return pad, instellingen or laad_instellingen()


REKENEN = "rekenen"  # sleutel in session_state voor een lopende berekening


def start_rekenen(taak: Callable[[service.Voortgang], service.Berekening]) -> None:
    """Start een berekening in een aparte draad, zodat de pagina de voortgang kan tonen."""
    voortgang, uitkomst = service.Voortgang(), {}

    def werk() -> None:
        try:
            uitkomst["berekening"] = taak(voortgang)
        except Exception as fout:  # pragma: no cover - wordt in de pagina opnieuw opgegooid
            uitkomst["fout"] = fout

    draad = threading.Thread(target=werk, daemon=True)
    draad.start()
    st.session_state[REKENEN] = (draad, voortgang, uitkomst, time.monotonic())


def _voortgangstekst(voortgang: service.Voortgang, seconden: float) -> str:
    """Wat de solver nu doet, voor de gebruiker."""
    if voortgang.gestopt:
        return f"Stoppen... ({seconden:.0f} s)"
    if voortgang.fase == "verbeteren":
        straf = "-" if voortgang.beste_straf is None else voortgang.beste_straf
        return f"Verbeteren: beste strafscore tot nu toe {straf} ({seconden:.0f} s)"
    if voortgang.fase == "uitleg":
        return f"Geen rooster mogelijk; zoeken naar de oorzaak... ({seconden:.0f} s)"
    return f"Zoeken naar een geldig rooster... ({seconden:.0f} s)"


def volg_rekenen() -> None:
    """Toon de voortgang van een lopende berekening tot ze klaar is, met een stopknop.

    Stoppen houdt het beste rooster tot dan toe. Daarna komt de berekening in
    session_state["berekening"] en wordt de pagina opnieuw getekend.
    """
    lopend = st.session_state.get(REKENEN)
    if lopend is None:
        return
    draad, voortgang, uitkomst, start = lopend
    if st.button("Stoppen en beste rooster houden", disabled=voortgang.gestopt):
        voortgang.stop()
    vak = st.empty()
    while draad.is_alive():
        if voortgang.gestopt:
            voortgang.stop()  # opnieuw: de solver kan net na de vorige vraag begonnen zijn
        vak.info(_voortgangstekst(voortgang, time.monotonic() - start))
        draad.join(0.5)
    st.session_state.pop(REKENEN, None)
    if "fout" in uitkomst:
        raise uitkomst["fout"]
    st.session_state["berekening"] = uitkomst["berekening"]
    st.rerun()
