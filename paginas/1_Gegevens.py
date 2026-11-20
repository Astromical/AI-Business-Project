"""Gegevens invullen en aanpassen: tijdslots, leraren, lokalen, onbeschikbaarheid en lessen."""

import streamlit as st

from src import beheer, service
from src.db import OpslaanFout
from src.models import DAGEN
from src.ui import vereis_recht, zijbalk

st.set_page_config(page_title="Gegevens", layout="wide")
vereis_recht("gegevens")
pad = zijbalk()

st.title("Gegevens")
if "gegevens_melding" in st.session_state:
    st.success(st.session_state.pop("gegevens_melding"))

con = service.open_database(pad)
try:
    # --- Tijdslots ---
    st.subheader("Dagen en uren per dag")
    huidig = beheer.uren_per_dag(con)
    kolommen = st.columns(len(DAGEN))
    uren = {
        dag: kolom.number_input(dag.capitalize(), 0, 8, huidig.get(dag, 6 if not huidig else 0), key=f"uren_{dag}")
        for dag, kolom in zip(DAGEN, kolommen)
    }
    bestaand = bool(huidig)
    bevestigd = True
    if bestaand:
        st.warning(
            "Er zijn al tijdslots. Opnieuw aanmaken wist de onbeschikbaarheid en het bewaarde rooster."
        )
        bevestigd = st.checkbox("Ik begrijp dat de onbeschikbaarheid en het bewaarde rooster gewist worden")
    if st.button("Tijdslots aanmaken", disabled=not bevestigd):
        beheer.maak_tijdslots(con, uren)
        st.session_state.pop("berekening", None)
        st.session_state["gegevens_melding"] = "Tijdslots aangemaakt."
        st.rerun()

    # --- Tabellen ---
    leraren = [r["id"] for r in beheer.lees(con, "leraar").to_dict("records")]
    kolom_instellingen = {
        "lokaal": {"type": st.column_config.SelectboxColumn("type", options=["regulier", "lab", "gym"], required=True)},
        "onbeschikbaar": {
            "leraar_id": st.column_config.SelectboxColumn("leraar_id", options=leraren, required=True),
            "dag": st.column_config.SelectboxColumn("dag", options=list(DAGEN), required=True),
            "uur": st.column_config.NumberColumn("uur", min_value=1, max_value=8, step=1, required=True),
        },
        "les": {
            "leraar_id": st.column_config.SelectboxColumn("leraar_id", options=leraren, required=True),
            "lokaaltype": st.column_config.SelectboxColumn("lokaaltype", options=["regulier", "lab", "gym"], required=True),
            "aantal_per_week": st.column_config.NumberColumn("aantal_per_week", min_value=1, step=1, required=True),
        },
        "leraar": {
            "max_uren_per_dag": st.column_config.NumberColumn("max_uren_per_dag", min_value=1, max_value=8, step=1, required=True)
        },
    }
    namen = {"leraar": "Leraren", "lokaal": "Lokalen", "onbeschikbaar": "Onbeschikbaar", "les": "Lessen"}
    tabs = st.tabs([namen[t] for t in beheer.TABBLADEN])
    for tab, tabel in zip(tabs, beheer.TABBLADEN):
        with tab:
            bewerkt = st.data_editor(
                beheer.lees(con, tabel),
                num_rows="dynamic",
                key=f"editor_{tabel}",
                column_config=kolom_instellingen.get(tabel, {}),
                hide_index=True,
                width="stretch",
            )
            if st.button("Opslaan", key=f"opslaan_{tabel}"):
                try:
                    aantal = beheer.sla_op(con, tabel, bewerkt)
                except OpslaanFout as fout:
                    st.error(f"Niet opgeslagen: {fout}")
                else:
                    st.session_state.pop(f"editor_{tabel}", None)
                    st.session_state.pop("berekening", None)
                    st.session_state["gegevens_melding"] = f"{namen[tabel]} opgeslagen ({aantal} wijzigingen)."
                    st.rerun()
finally:
    con.close()
