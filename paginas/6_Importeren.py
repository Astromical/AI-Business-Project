"""Lessen inlezen uit een bestand: eerst bekijken, pas daarna toevoegen."""

import pandas as pd
import streamlit as st

from src import beheer, service
from src.conversie import KOLOMMEN, ConversieFout, converteer, naar_csv
from src.db import OpslaanFout
from src.ui import link_naar, vereis_recht, zijbalk

st.set_page_config(page_title="Importeren", layout="wide")
vereis_recht("importeren")
pad = zijbalk()

st.title("Importeren")
st.write(
    "Lees lessen in uit CSV, Excel (.xlsx), JSON of een WebUntis-export van een klas. "
    f"De app zet alles om naar deze kolommen: {', '.join(KOLOMMEN)}."
)
if "import_melding" in st.session_state:
    st.success(st.session_state.pop("import_melding"))
    link_naar("rooster", "Volgende stap: rooster berekenen")
    st.write("Of importeer nog een bestand, bijvoorbeeld van een andere klas.")

# een nieuwe sleutel na elke import maakt de uploadzone weer leeg
uploads = st.session_state.get("uploads", 0)
bestand = st.file_uploader("Kies een bestand of sleep het hierheen", key=f"upload_{uploads}")
if bestand is None:
    st.stop()

try:
    uitkomst = converteer(bestand.name, bestand.getvalue())
except ConversieFout as fout:
    st.error(str(fout))
    st.stop()

for melding in uitkomst.meldingen:
    (st.error if melding.ernst == "fout" else st.warning)(melding.tekst)
voorbeeld = [(r.klas, r.vak, r.leraar, r.uren_per_week, r.soort_lokaal) for r in uitkomst.rijen]
st.dataframe(pd.DataFrame(voorbeeld, columns=KOLOMMEN), hide_index=True)
st.caption(f"{len(uitkomst.rijen)} lessen, {sum(r.uren_per_week for r in uitkomst.rijen)} lesuren per week.")
st.download_button("Download als CSV", naar_csv(uitkomst.rijen), file_name="lessen.csv", mime="text/csv")

akkoord = True
if uitkomst.heeft_fouten:
    akkoord = st.checkbox("Ik begrijp dat dit niet alles is en wil de lessen toch toevoegen")
if st.button("Lessen toevoegen", type="primary", disabled=not (akkoord and uitkomst.rijen)):
    con = service.open_database(pad)
    try:
        tijdslots, lokalen = beheer.vul_basis_aan(con, uitkomst.rijen)
        leraren, lessen = beheer.importeer(con, uitkomst.rijen)
    except OpslaanFout as fout:
        st.error(f"Niet toegevoegd: {fout}")
    else:
        st.session_state.pop("berekening", None)
        st.session_state["uploads"] = uploads + 1
        st.session_state["import_melding"] = (
            f"Toegevoegd: {lessen} nieuwe lessen, {leraren} nieuwe leraren, "
            f"{tijdslots} tijdslots en {lokalen} lokalen."
        )
        st.rerun()
    finally:
        con.close()
