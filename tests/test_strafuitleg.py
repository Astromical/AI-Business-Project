"""Tests voor de uitleg bij de strafscore: per zachte regel de punten en de betrokkenen."""

from dataclasses import replace

from src import service
from src.benchmark import laad_variant
from src.checker import strafposten, tel_per_regel, tel_straf
from src.config import laad_instellingen
from src.loader import maak_lesuren
from src.models import Instellingen, Leraar, Les, Lokaal, ProbleemData, Tijdslot, Toewijzing
from src.solver import GEEN_ZACHTE_REGELS, _als_oplossing, solve, waardeer
from src.views import straf_details, straf_samenvatting
from src.ui import ZACHTE_REGEL_NAMEN

ALLE_REGELS = {"Z1": 10, "Z2": 5, "Z3": 5, "Z4": 2}


def _ruw_rooster(data: ProbleemData) -> tuple[Toewijzing, ...]:
    """Een geldig rooster zonder rekening te houden met zachte regels: heeft strafpunten."""
    return solve(data, Instellingen(1, dict(GEEN_ZACHTE_REGELS), num_workers=1)).toewijzingen


def test_som_van_de_posten_is_de_strafscore_op_de_voorbeelddata():
    data = laad_variant("voorbeeld")
    rooster = _ruw_rooster(data)
    zwaar = laad_instellingen().zware_vakken
    posten = strafposten(data, rooster, ALLE_REGELS, zwaar)
    totaal = sum(p.punten for p in posten)
    assert totaal > 0  # anders test dit niets
    assert totaal == sum(tel_straf(data, rooster, ALLE_REGELS, zwaar).values())
    # en gelijk aan wat het solvermodel voor hetzelfde rooster rekent
    straf_solver = waardeer(data, frozenset(), ALLE_REGELS, _als_oplossing(data, rooster, frozenset()), zwaar)
    assert totaal == sum(straf_solver.values())
    # per regel: aantal overtredingen gelijk aan de bestaande telling
    aantallen = tel_per_regel(data, rooster, zwaar)
    for regel in ALLE_REGELS:
        assert sum(p.aantal for p in posten if p.regel == regel) == aantallen[regel]


def test_regel_met_gewicht_nul_geeft_geen_posten():
    data = laad_variant("voorbeeld")
    posten = strafposten(data, _ruw_rooster(data), {"Z1": 10, "Z2": 0, "Z3": 0, "Z4": 0})
    assert {p.regel for p in posten} <= {"Z1"}


def _een_dag() -> ProbleemData:
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    lessen = (
        Les("A", "wiskunde", "1A", "JAN", 1, "regulier"),
        Les("B", "engels", "1A", "AN", 1, "regulier"),
    )
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    leraren = (Leraar("JAN", "Jan", 3), Leraar("AN", "An", 3))
    return ProbleemData(slots, lokalen, leraren, lessen, maak_lesuren(lessen))


def test_tussenuur_noemt_klas_leraren_lokaal_en_uur():
    data = _een_dag()
    rooster = (Toewijzing(data.lesuren[0], 1, "R1"), Toewijzing(data.lesuren[1], 3, "R1"))
    (post,) = strafposten(data, rooster, {"Z1": 10})
    assert (post.regel, post.punten, post.dag, post.uren) == ("Z1", 10, "maandag", (2,))
    assert post.klassen == ("1A",)
    assert set(post.leraren) == {"Jan", "An"}
    assert post.lokalen == ("Lokaal 1",)
    assert "tussenuur" in post.tekst


def test_zwaar_vak_in_laatste_uur():
    data = _een_dag()
    rooster = (Toewijzing(data.lesuren[1], 2, "R1"), Toewijzing(data.lesuren[0], 3, "R1"))
    (post,) = strafposten(data, rooster, {"Z4": 2}, ("wiskunde",))
    assert (post.regel, post.punten, post.uren, post.leraren) == ("Z4", 2, (3,), ("Jan",))


def test_samenvatting_telt_op_tot_de_totale_strafscore():
    data = laad_variant("voorbeeld")
    rooster = _ruw_rooster(data)
    posten = strafposten(data, rooster, ALLE_REGELS, ("wiskunde",))
    tabel = straf_samenvatting(posten, ALLE_REGELS, ZACHTE_REGEL_NAMEN)
    totaal = tabel.iloc[-1]["strafpunten"]
    assert totaal == tabel.iloc[:-1]["strafpunten"].sum() == sum(p.punten for p in posten)
    assert len(straf_details(posten)) == len(posten)


def test_berekening_bewaart_posten_die_optellen_tot_de_strafscore():
    data = laad_variant("voorbeeld")
    instellingen = replace(laad_instellingen(), tijdslimiet_s=2, num_workers=1)
    berekening = service.bereken(data, instellingen)
    som = sum(p.punten for p in berekening.strafposten)
    assert som == berekening.resultaat.strafscore
    assert berekening.gewichten == instellingen.gewichten
