"""Tests voor config.toml en de instellingen van de solver."""

from src.config import STANDAARD_CONFIG, laad_instellingen
from src.db import maak_schema, verbind
from src.loader import laad_probleem
from src.models import Instellingen
from src.seed import seed
from src.solver import solve


def test_config_toml_wordt_gelezen():
    instellingen = laad_instellingen(STANDAARD_CONFIG)
    assert instellingen.tijdslimiet_s == 30
    assert instellingen.gewichten["Z1"] == 10


def test_ontbrekende_waarden_krijgen_standaard(tmp_path):
    pad = tmp_path / "c.toml"
    pad.write_text("tijdslimiet_s = 5\n[gewichten]\nZ1 = 3\n", encoding="utf-8")
    instellingen = laad_instellingen(pad)
    assert instellingen.tijdslimiet_s == 5
    assert instellingen.gewichten == {"Z1": 3, "Z2": 5, "Z3": 5, "Z4": 2}


def test_zonder_bestand_standaardwaarden(tmp_path):
    assert laad_instellingen(tmp_path / "bestaat_niet.toml") == Instellingen()


def test_gewicht_nul_schakelt_z1_uit(klein_probleem):
    resultaat = solve(klein_probleem, Instellingen(10, {"Z1": 0}))
    assert resultaat.straf_per_regel == {}
    assert resultaat.strafscore == 0


def test_tijdslimiet_van_een_seconde_wordt_gerespecteerd(tmp_path):
    con = verbind(tmp_path / "t.db")
    maak_schema(con)
    seed(con)
    data = laad_probleem(con)
    con.close()
    resultaat = solve(data, Instellingen(1))
    # de tijdslimiet geldt voor het verbeteren; het zoeken naar een geldig rooster telt niet mee
    assert resultaat.status in ("optimaal", "geldig")
    assert resultaat.oplostijd_s - resultaat.tijd_zoeken_s < 3


def test_zoekgrens_wordt_gelezen(tmp_path):
    pad = tmp_path / "c.toml"
    pad.write_text("tijdslimiet_s = 20\nmax_tijd_zoeken_s = 120\n", encoding="utf-8")
    instellingen = laad_instellingen(pad)
    assert (instellingen.tijdslimiet_s, instellingen.max_tijd_zoeken_s) == (20, 120)
    assert laad_instellingen(STANDAARD_CONFIG).max_tijd_zoeken_s == 300
