"""Tests voor het bewaarde rooster: strafscore, status en een verwijderd lokaal."""

import pandas as pd
import pytest

from src import beheer, service
from src.db import bewaar_rooster
from src.loader import laad_probleem
from src.models import Instellingen, Toewijzing

GEWICHTEN = {"Z1": 10, "Z2": 0, "Z3": 5, "Z4": 0}


@pytest.fixture
def pad(tmp_path):
    """Kleine database met een bewaard rooster: wiskunde op uur 1 (R1) en uur 3 (R2).

    Dat geeft klas 1A één tussenuur (Z1) en één dubbel vakuur (Z3).
    """
    pad = str(tmp_path / "rooster.db")
    con = service.open_database(pad)
    beheer.maak_tijdslots(con, {"maandag": 3})
    beheer.sla_op(con, "leraar", pd.DataFrame([["A", "Anna", 3]], columns=["id", "naam", "max_uren_per_dag"]))
    beheer.sla_op(con, "lokaal", pd.DataFrame([["R1", "Lokaal 1", "regulier"], ["R2", "Lokaal 2", "regulier"], ["R3", "Lokaal 3", "regulier"]], columns=["id", "naam", "type"]))
    lessen = pd.DataFrame(
        [["1A-WIS", "wiskunde", "1A", "A", 2, "regulier"]],
        columns=["id", "vak", "klas", "leraar_id", "aantal_per_week", "lokaaltype"],
    )
    beheer.sla_op(con, "les", lessen)
    data = laad_probleem(con)
    slot = {s.uur: s.id for s in data.tijdslots}
    bewaar_rooster(con, tuple(Toewijzing(u, slot[2 * u.volgnummer - 1], f"R{u.volgnummer}") for u in data.lesuren))
    con.close()
    return pad


def test_bewaard_rooster_heeft_strafscore_volgens_de_gewichten(pad):
    data, _ = service.laad(pad)
    berekening = service.bewaard_rooster(pad, data, Instellingen(gewichten=GEWICHTEN))
    assert berekening.resultaat.status == "geldig"
    assert berekening.resultaat.straf_per_regel == {"Z1": 10, "Z3": 5}
    assert berekening.resultaat.strafscore == 15
    assert berekening.tellingen["Z1"] == berekening.tellingen["Z3"] == 1


def test_bewaard_rooster_met_schendingen_is_ongeldig(pad):
    con = service.open_database(pad)
    with con:  # buiten de app om: Anna kan op uur 1 niet meer
        con.execute("INSERT INTO onbeschikbaar SELECT 'A', id FROM tijdslot WHERE uur = 1")
    con.close()
    data, _ = service.laad(pad)
    berekening = service.bewaard_rooster(pad, data)
    assert berekening.resultaat.status == "ongeldig"
    assert [s.regel for s in berekening.schendingen] == ["H6"]


def test_lokaal_uit_bewaard_rooster_verwijderen_lukt(pad):
    con = service.open_database(pad)
    zonder_r1 = beheer.lees(con, "lokaal").query("id != 'R1'")
    assert beheer.sla_op(con, "lokaal", zonder_r1) == 1
    con.close()
    data, _ = service.laad(pad)
    berekening = service.bewaard_rooster(pad, data)
    assert berekening.resultaat.status == "ongeldig"  # de lesuren uit R1 staan niet meer ingepland
    assert {s.regel for s in berekening.schendingen} == {"H1"}


def test_ander_lokaal_verwijderen_houdt_het_bewaarde_rooster(pad):
    con = service.open_database(pad)
    beheer.sla_op(con, "lokaal", beheer.lees(con, "lokaal").query("id != 'R3'"))
    con.close()
    data, _ = service.laad(pad)
    assert service.bewaard_rooster(pad, data).resultaat.status == "geldig"
