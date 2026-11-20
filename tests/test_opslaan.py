"""Tests voor opslaan, laden en exporteren van een rooster."""

import csv
import io
from pathlib import Path

import pytest
from conftest import log_in_op_pagina
from streamlit.testing.v1 import AppTest

from src import service
from src.db import bewaar_rooster, laad_rooster, maak_schema, verbind
from src.loader import laad_probleem
from src.models import Instellingen
from src.seed import seed
from src.solver import solve
from src.views import rooster_csv

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def voorbeeld(tmp_path):
    """Database met voorbeelddata, het ingelezen probleem en een rooster."""
    con = verbind(tmp_path / "t.db")
    maak_schema(con)
    seed(con)
    data = laad_probleem(con)
    resultaat = solve(data, Instellingen(30, {"Z1": 0}))
    yield con, data, resultaat.toewijzingen
    con.close()


def _sleutels(toewijzingen):
    return {(t.lesuur, t.tijdslot_id, t.lokaal_id) for t in toewijzingen}


def test_opslaan_en_laden_geeft_dezelfde_toewijzingen(voorbeeld):
    con, _, toewijzingen = voorbeeld
    bewaar_rooster(con, toewijzingen)
    teruggelezen = laad_rooster(con)
    assert len(teruggelezen) == len(toewijzingen) == 144
    assert _sleutels(teruggelezen) == _sleutels(toewijzingen)


def test_opnieuw_opslaan_vervangt_het_oude_rooster(voorbeeld):
    con, _, toewijzingen = voorbeeld
    bewaar_rooster(con, toewijzingen)
    bewaar_rooster(con, toewijzingen[:10])
    assert len(laad_rooster(con)) == 10


def test_leeg_rooster_laden(tmp_path):
    con = verbind(tmp_path / "leeg.db")
    maak_schema(con)
    assert laad_rooster(con) == ()
    con.close()


def test_csv_heeft_juiste_kolommen_en_rijen(voorbeeld):
    _, data, toewijzingen = voorbeeld
    rijen = list(csv.reader(io.StringIO(rooster_csv(data, toewijzingen))))
    assert rijen[0] == ["klas", "dag", "uur", "vak", "leraar", "lokaal"]
    assert len(rijen) == 1 + 144
    assert rijen[1][0] == "1A" and rijen[1][1] == "maandag"


def test_rooster_overleeft_herstarten_van_de_app(tmp_path):
    pad = str(tmp_path / "rooster.db")
    service.vul_voorbeeld(pad, "voorbeeld")
    pagina = str(ROOT / "paginas" / "2_Rooster.py")
    at = log_in_op_pagina(AppTest.from_file(pagina, default_timeout=90), pad)
    at.run()
    at = next(b for b in at.button if b.label == "Rooster berekenen").click().run()
    at = next(b for b in at.button if b.label == "Opslaan in database").click().run()
    assert not at.exception
    # een nieuwe sessie (zoals na herstarten) toont het bewaarde rooster zonder te rekenen
    nieuw = log_in_op_pagina(AppTest.from_file(pagina, default_timeout=90), pad)
    nieuw.run()
    assert not nieuw.exception
    assert len(nieuw.get("html")) == 3
    assert {m.label: m.value for m in nieuw.metric}["Schendingen"] == "0"
    assert not nieuw.warning


def test_bewaard_rooster_na_wijziging_geeft_waarschuwing(tmp_path, voorbeeld):
    con, data, toewijzingen = voorbeeld
    bewaar_rooster(con, toewijzingen)
    with con:  # na het opslaan krijgt 1A een uur wiskunde minder
        con.execute("UPDATE les SET aantal_per_week = 3 WHERE id = '1A-WIS'")
    pad = str(tmp_path / "t.db")
    pagina = str(ROOT / "paginas" / "2_Rooster.py")
    at = log_in_op_pagina(AppTest.from_file(pagina, default_timeout=90), pad)
    at.run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric}["Schendingen"] != "0"
    assert {m.label: m.value for m in at.metric}["Status"] == "ongeldig"
    assert any("past niet meer" in w.value for w in at.warning)
