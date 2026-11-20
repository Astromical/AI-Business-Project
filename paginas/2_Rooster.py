"""Rooster berekenen en bekijken."""

import streamlit as st

from src import service
from src.auth import mag
from src.ui import (
    ZACHTE_REGEL_NAMEN,
    lege_start,
    link_naar,
    start_rekenen,
    vereis_recht,
    volg_rekenen,
    zijbalk_met_regels,
)
from src.views import SOORTEN, keuzes, rooster_csv, rooster_html

st.set_page_config(page_title="Rooster", layout="wide")
gebruiker = vereis_recht("rooster")
pad, instellingen = zijbalk_met_regels()

st.title("Rooster")

data, meldingen = service.laad(pad)

if not data.lessen:
    lege_start(mag(gebruiker.rol, "demodata"))
    st.stop()

kolommen = st.columns(5)
for kolom, (naam, aantal) in zip(kolommen, service.aantallen(data).items()):
    kolom.metric("Docenten" if naam == "Leraren" else naam, aantal)

for melding in meldingen:
    if melding.ernst == "fout":
        st.error(melding.tekst)
    else:
        st.warning(melding.tekst)
if service.heeft_fouten(meldingen):
    st.caption("Los eerst de fouten hierboven op; daarna kun je het rooster berekenen.")
    link_naar("gegevens", "Gegevens aanpassen")

if st.button("Rooster berekenen", disabled=service.heeft_fouten(meldingen)):
    start_rekenen(lambda voortgang, d=data, i=instellingen: service.bereken(d, i, voortgang))
volg_rekenen()  # zolang er gerekend wordt: voortgang en stopknop; daarna het resultaat

berekening = st.session_state.get("berekening")
if berekening is not None and not service.is_actueel(berekening, data):
    # de database is veranderd sinds het rekenen (bijvoorbeeld in een ander tabblad)
    st.session_state.pop("berekening", None)
    berekening = None
    st.info(
        "De gegevens zijn veranderd sinds de laatste berekening. Bereken het rooster opnieuw."
    )
berekening = berekening or service.bewaard_rooster(pad, data, instellingen)
if berekening is not None:
    resultaat = berekening.resultaat
    kolommen = st.columns(4)
    kolommen[0].metric("Status", resultaat.status)
    kolommen[1].metric(
        "Oplostijd (s)", "-" if berekening.bewaard else f"{resultaat.oplostijd_s:.1f}"
    )
    heeft_rooster = bool(
        resultaat.toewijzingen
    )  # zonder rooster valt er niets te tellen
    kolommen[2].metric(
        "Schendingen", len(berekening.schendingen) if heeft_rooster else "-"
    )
    strafscore = resultaat.strafscore if heeft_rooster else None
    kolommen[3].metric("Strafscore", "-" if strafscore is None else strafscore)
    kolommen = st.columns(len(ZACHTE_REGEL_NAMEN))
    for kolom, (regel, naam) in zip(kolommen, ZACHTE_REGEL_NAMEN.items()):
        kolom.metric(naam, berekening.tellingen.get(regel, 0) if heeft_rooster else "-")
    for schending in berekening.schendingen:
        st.error(f"{schending.regel}: {schending.tekst}")
    if resultaat.status == "onoplosbaar":
        st.error("Er bestaat geen rooster dat aan alle harde regels voldoet.")
        for regel in berekening.uitleg:
            st.info(regel)
    elif resultaat.status == "geen_oplossing_binnen_tijd" and resultaat.gestopt:
        st.warning("Je hebt het rekenen gestopt voordat er een geldig rooster was.")
    elif resultaat.status == "geen_oplossing_binnen_tijd":
        st.warning(
            f"Na {instellingen.max_tijd_zoeken_s:.0f} seconden zoeken is nog geen geldig rooster "
            "gevonden. Controleer of de gegevens niet te krap zijn, of verhoog max_tijd_zoeken_s "
            "in config.toml."
        )
    if resultaat.gestopt and resultaat.toewijzingen:
        st.info("Je hebt het rekenen gestopt: dit is het beste rooster tot dat moment.")
    vorige = berekening.vorige_strafscore
    if berekening.bewaard:
        st.caption(
            "Dit is het rooster dat eerder in de database is opgeslagen. "
            "De strafscore volgt de gewichten in de zijbalk."
        )
        if berekening.schendingen:
            st.warning(
                "Het bewaarde rooster past niet meer bij de gegevens (die zijn na het opslaan "
                "aangepast). Bereken het rooster opnieuw."
            )
    elif vorige is not None:
        st.caption(f"Verder verbeterd vanaf het vorige rooster: {resultaat.oplostijd_s:.1f} s.")
        if resultaat.strafscore is not None and resultaat.strafscore < vorige:
            st.success(f"Beter rooster gevonden: strafscore van {vorige} naar {resultaat.strafscore}.")
        else:
            st.info(f"Geen beter rooster gevonden: het vorige rooster (strafscore {vorige}) blijft staan.")
    else:
        verbeteren = resultaat.oplostijd_s - resultaat.tijd_zoeken_s
        st.caption(
            f"Zoeken naar een geldig rooster: {resultaat.tijd_zoeken_s:.1f} s. "
            f"Verbeteren: {verbeteren:.1f} s."
        )
    if service.kan_verder(berekening) and st.button(
        "Verder verbeteren",
        help="Rekent verder vanaf dit rooster, met de verbetertijd uit de zijbalk. Dit rooster "
        "blijft de veilige versie: vindt de solver niets beters, dan blijft het staan.",
    ):
        start_rekenen(
            lambda voortgang, d=data, b=berekening, i=instellingen: service.reken_verder(
                d, b, i, voortgang
            )
        )
        st.rerun()
    if resultaat.toewijzingen:
        opslaan, download = st.columns(2)
        if opslaan.button("Opslaan in database"):
            service.bewaar(pad, resultaat.toewijzingen)
            st.success("Rooster opgeslagen.")
        download.download_button(
            "Download CSV",
            rooster_csv(data, resultaat.toewijzingen),
            file_name="rooster.csv",
            mime="text/csv",
        )
        tabs = st.tabs(["Per klas", "Per docent", "Per lokaal"])
        for tab, soort in zip(tabs, SOORTEN):
            with tab:
                opties = keuzes(data, soort)
                id_ = st.selectbox(
                    f"Kies een {'docent' if soort == 'leraar' else soort}",
                    [i for i, _ in opties],
                    format_func=dict(opties).get,
                    key=f"keuze_{soort}",
                )
                st.html(rooster_html(data, resultaat.toewijzingen, soort, id_))
