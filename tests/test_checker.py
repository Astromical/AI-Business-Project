"""Tests voor de onafhankelijke roostercontrole."""

from dataclasses import replace

import pytest

from src.checker import controleer
from src.cli import main
from src.db import maak_schema, verbind
from src.loader import laad_probleem
from src.models import Toewijzing
from src.seed import seed
from src.models import Instellingen
from src.solver import solve

# (les_id, volgnummer): (tijdslot_id, lokaal_id) voor een geldig rooster van klein_probleem
GOED = {
    ("1A-WIS", 1): (1, "R1"),
    ("1A-WIS", 2): (2, "R1"),
    ("1A-NED", 1): (3, "R1"),
    ("1A-BIO", 1): (6, "L1"),
    ("1B-WIS", 1): (4, "R1"),
    ("1B-WIS", 2): (5, "R1"),
    ("1B-BIO", 1): (1, "L1"),
    ("1B-BIO", 2): (2, "L1"),
}


def _rooster(data, plaatsing=None):
    """Bouw toewijzingen uit een dict {(les_id, volgnummer): (tijdslot, lokaal)}."""
    plaatsing = {**GOED, **(plaatsing or {})}
    return tuple(
        Toewijzing(u, *plaatsing[u.les_id, u.volgnummer]) for u in data.lesuren
    )


def _regels(schendingen):
    return {s.regel for s in schendingen}


def test_goed_rooster_heeft_geen_schendingen(klein_probleem):
    assert controleer(klein_probleem, _rooster(klein_probleem)) == []


def test_h1_ontbrekend_lesuur(klein_probleem):
    rooster = _rooster(klein_probleem)[1:]
    schendingen = controleer(klein_probleem, rooster)
    assert _regels(schendingen) == {"H1"}
    assert "niet ingepland" in schendingen[0].tekst


def test_h1_dubbel_ingepland(klein_probleem):
    rooster = _rooster(klein_probleem)
    schendingen = controleer(klein_probleem, rooster + (rooster[0],))
    assert "H1" in _regels(schendingen)
    assert any("2 keer" in s.tekst for s in schendingen)


def test_h2_dubbel_lokaal(klein_probleem):
    rooster = _rooster(klein_probleem, {("1B-WIS", 1): (3, "R1")})
    assert "H2" in _regels(controleer(klein_probleem, rooster))


def test_h3_dubbele_leraar(klein_probleem):
    rooster = _rooster(klein_probleem, {("1B-WIS", 1): (1, "R1")})
    assert "H3" in _regels(controleer(klein_probleem, rooster))


def test_h4_dubbele_klas(klein_probleem):
    rooster = _rooster(klein_probleem, {("1A-BIO", 1): (3, "L1")})
    assert "H4" in _regels(controleer(klein_probleem, rooster))


def test_h5_verkeerd_lokaaltype(klein_probleem):
    rooster = _rooster(klein_probleem, {("1A-BIO", 1): (6, "R1")})
    schendingen = controleer(klein_probleem, rooster)
    assert _regels(schendingen) == {"H5"}


def test_h6_onbeschikbare_leraar(klein_probleem):
    jan, an = klein_probleem.leraren
    data = replace(klein_probleem, leraren=(replace(jan, onbeschikbaar=frozenset({1})), an))
    schendingen = controleer(data, _rooster(data))
    assert _regels(schendingen) == {"H6"}


def test_h7_te_veel_uren_op_een_dag(klein_probleem):
    jan, an = klein_probleem.leraren
    data = replace(klein_probleem, leraren=(jan, replace(an, max_uren_per_dag=2)))
    schendingen = controleer(data, _rooster(data))
    assert _regels(schendingen) == {"H7"}


def test_solver_rooster_klein_probleem_is_schoon(klein_probleem):
    resultaat = solve(klein_probleem, Instellingen(10))
    assert controleer(klein_probleem, resultaat.toewijzingen) == []


@pytest.fixture
def voorbeeld(tmp_path):
    con = verbind(tmp_path / "t.db")
    maak_schema(con)
    seed(con)
    data = laad_probleem(con)
    con.close()
    return data


def test_solver_rooster_voorbeelddata_is_schoon(voorbeeld):
    resultaat = solve(voorbeeld, Instellingen(30))
    assert len(resultaat.toewijzingen) == 144
    assert controleer(voorbeeld, resultaat.toewijzingen) == []


def test_cli_check(tmp_path, capsys):
    pad = str(tmp_path / "r.db")
    main(["seed", "--pad", pad])
    main(["check", "--pad", pad])
    assert "Schendingen van H1-H7: 0" in capsys.readouterr().out
