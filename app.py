"""Startpunt van de schoolrooster-solver: inloggen en navigatie per rol."""

import streamlit as st

from src import service
from src.auth import mag
from src.ui import PAGINAS, huidige_gebruiker, inlogscherm, lege_start, link_naar, zijbalk


def _stap_gegevens(pad: str, demodata: bool) -> None:
    """Stap 1: toon wat er al ingevoerd is en waar je gegevens toevoegt."""
    st.subheader("1. Gegevens invoeren")
    data, meldingen = service.laad(pad)
    if not data.lesuren:
        lege_start(demodata)
        return
    tellers = service.aantallen(data)
    st.success(
        f"Ingevoerd: {tellers['Klassen']} klassen, {tellers['Leraren']} leraren "
        f"en {tellers['Lesuren']} lesuren per week."
    )
    fouten = [m.tekst for m in meldingen if m.ernst == "fout"]
    if fouten:
        st.error("Los dit eerst op, daarna kun je het rooster berekenen:\n\n" + "\n".join(f"- {t}" for t in fouten))
    link_naar("importeren", "Bestand importeren")
    link_naar("gegevens", "Gegevens zelf invullen of aanpassen")


def startpagina() -> None:
    """Uitleg na het inloggen: welke stappen er zijn en waar je ze vindt."""
    pad = zijbalk()
    gebruiker = huidige_gebruiker()
    st.title("Schoolrooster-solver")
    if gebruiker is None or not mag(gebruiker.rol, "rooster"):
        st.write("Hier vind je je eigen weekrooster.")
        link_naar("eigen_rooster", "Mijn rooster bekijken")
        return
    st.write("Een weekrooster maken gaat in drie stappen.")
    _stap_gegevens(pad, mag(gebruiker.rol, "demodata"))
    st.subheader("2. Rooster berekenen")
    st.write("Bereken het rooster, controleer het en sla het op.")
    link_naar("rooster", "Rooster berekenen")
    st.subheader("3. Rooster delen")
    st.write("Leraren met een account zien het opgeslagen rooster op de pagina Mijn rooster.")
    link_naar("accounts", "Accounts voor leraren beheren")


st.set_page_config(page_title="Schoolrooster-solver", layout="wide")
gebruiker = huidige_gebruiker()
if gebruiker is None:
    # ook nu st.navigation; de map heet paginas/ en niet pages/, anders toont Streamlit
    # bij het laden eerst even een eigen menu met alle pagina's
    st.navigation([st.Page(inlogscherm, title="Inloggen")]).run()
else:
    paginas = [st.Page(startpagina, title="Start", default=True)]
    paginas += [
        st.Page(bestand, title=titel)
        for recht, (bestand, titel) in PAGINAS.items()
        if mag(gebruiker.rol, recht)
    ]
    st.navigation(paginas).run()
