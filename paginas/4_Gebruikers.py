"""Accounts beheren: aanmaken, rol en leraar wijzigen, wachtwoord zetten en verwijderen."""

import pandas as pd
import streamlit as st

from src import service
from src.auth import LERAAR_WACHTWOORD
from src.db import OpslaanFout
from src.models import ROLLEN, Gebruiker
from src.ui import ROL_NAMEN, vereis_recht, zijbalk

st.set_page_config(page_title="Gebruikers", layout="wide")
vereis_recht("accounts")
pad = zijbalk()

st.title("Gebruikers")
if "gebruikers_melding" in st.session_state:
    st.success(st.session_state.pop("gebruikers_melding"))

leraren = {leraar.id: leraar.naam for leraar in service.laad(pad)[0].leraren}
leraar_keuzes = [None, *leraren]


def toon_leraar(leraar_id: str | None) -> str:
    """De naam voor de keuzelijst; None betekent geen koppeling."""
    return "Geen leraar" if leraar_id is None else leraren.get(leraar_id, leraar_id)


def voer_uit(actie, melding: str, *argumenten) -> None:
    """Voer een wijziging uit en toon de uitkomst."""
    try:
        actie(pad, *argumenten)
    except OpslaanFout as fout:
        st.error(f"Niet gelukt: {fout}")
    else:
        st.session_state["gebruikers_melding"] = melding
        st.rerun()


accounts = service.gebruikers(pad)
st.dataframe(
    pd.DataFrame(
        [{"Gebruikersnaam": g.naam, "Rol": ROL_NAMEN.get(g.rol, g.rol), "Leraar": toon_leraar(g.leraar_id)} for g in accounts]
    ),
    hide_index=True,
)

st.subheader("Accounts voor leraren")
zonder = service.leraren_zonder_account(pad)
if zonder == 0:
    st.caption(f"Elke leraar heeft een account. Leraren loggen in met hun code en het wachtwoord {LERAAR_WACHTWOORD}.")
else:
    st.write(
        f"{zonder} leraren hebben nog geen account. Met één klik krijgt elk van hen een account: "
        f"de leraarcode als gebruikersnaam (bijvoorbeeld casw) en het wachtwoord **{LERAAR_WACHTWOORD}**."
    )
    if st.button("Accounts maken voor alle leraren", type="primary"):
        voer_uit(
            service.maak_leraaraccounts,
            f"Accounts aangemaakt. Leraren loggen in met hun code en het wachtwoord {LERAAR_WACHTWOORD}.",
        )

st.subheader("Nieuw account")
with st.form("nieuw_account", clear_on_submit=True):
    naam = st.text_input("Gebruikersnaam")
    wachtwoord = st.text_input("Wachtwoord", type="password")
    rol = st.selectbox("Rol", ROLLEN, index=ROLLEN.index("leraar"), format_func=ROL_NAMEN.get)
    leraar_id = st.selectbox("Leraar", leraar_keuzes, format_func=toon_leraar)
    if st.form_submit_button("Account aanmaken"):
        voer_uit(service.maak_gebruiker, "Account aangemaakt.", naam, wachtwoord, rol, leraar_id)

st.subheader("Account aanpassen")
keuze = st.selectbox("Kies een account", accounts, format_func=lambda g: f"{g.naam} ({ROL_NAMEN.get(g.rol, g.rol).lower()})", key="account_keuze")

with st.container(border=True):
    st.markdown("**Wachtwoord**")
    if keuze.rol == "leraar" and st.button(f"Terugzetten naar {LERAAR_WACHTWOORD}", type="primary"):
        voer_uit(service.zet_wachtwoord, f"Het wachtwoord van {keuze.naam} is weer {LERAAR_WACHTWOORD}.", keuze.naam, LERAAR_WACHTWOORD)
    nieuw = st.text_input("Of kies zelf een wachtwoord", type="password", key=f"wachtwoord_{keuze.naam}")
    if st.button("Wachtwoord instellen", key=f"instellen_{keuze.naam}"):
        voer_uit(service.zet_wachtwoord, "Wachtwoord ingesteld.", keuze.naam, nieuw)

with st.container(border=True):
    st.markdown("**Rol en leraar**")
    rol = st.selectbox("Rol", ROLLEN, index=ROLLEN.index(keuze.rol), format_func=ROL_NAMEN.get, key=f"rol_{keuze.naam}")
    koppeling = keuze.leraar_id if keuze.leraar_id in leraar_keuzes else None
    leraar_id = st.selectbox(
        "Leraar",
        leraar_keuzes,
        index=leraar_keuzes.index(koppeling),
        format_func=toon_leraar,
        key=f"leraar_{keuze.naam}",
    )
    if st.button("Wijzigingen opslaan"):
        voer_uit(service.wijzig_gebruiker, "Account gewijzigd.", Gebruiker(keuze.naam, rol, leraar_id))

with st.container(border=True):
    st.markdown("**Account verwijderen**")
    zeker = st.checkbox("Ik weet zeker dat ik dit account wil verwijderen", key=f"zeker_{keuze.naam}")
    if st.button("Account verwijderen", disabled=not zeker):
        voer_uit(service.verwijder_gebruiker, "Account verwijderd.", keuze.naam)
