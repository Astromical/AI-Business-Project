"""Het eigen rooster van een leraar: alleen bekijken, zonder rekenen of wijzigen."""

import streamlit as st

from src import service
from src.ui import vereis_recht, zijbalk
from src.views import rooster_html

st.set_page_config(page_title="Mijn rooster", layout="wide")
gebruiker = vereis_recht("eigen_rooster")
pad = zijbalk()

st.title("Mijn rooster")
data, _ = service.laad(pad)
leraar_id = gebruiker.leraar_id
if leraar_id is None or leraar_id not in data.leraar_per_id:
    st.info("Aan je account is geen docent gekoppeld. Vraag dit aan de roostermaker.")
    st.stop()

berekening = service.bewaard_rooster(pad, data)
if berekening is None:
    st.info("Er is nog geen rooster bewaard.")
    st.stop()

if berekening.schendingen:
    st.warning("Dit rooster klopt niet meer met de gegevens en wordt nog aangepast.")
st.html(rooster_html(data, berekening.resultaat.toewijzingen, "leraar", leraar_id))
