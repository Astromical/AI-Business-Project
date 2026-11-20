"""Tests voor schema, tijdslots en voorbeelddata."""

import sqlite3

import pytest

from src.cli import main
from src.db import leeg_database, maak_schema, maak_tijdslots, verbind
from src.seed import seed


@pytest.fixture
def con(tmp_path):
    """Lege database met schema in een tijdelijke map."""
    verbinding = verbind(tmp_path / "test.db")
    maak_schema(verbinding)
    yield verbinding
    verbinding.close()


def _tel(con, sql: str) -> int:
    return con.execute(sql).fetchone()[0]


def test_tijdslots_met_kortere_woensdag(con):
    maak_tijdslots(con, {"maandag": 6, "dinsdag": 6, "woensdag": 4})
    assert _tel(con, "SELECT COUNT(*) FROM tijdslot") == 16
    assert _tel(con, "SELECT MAX(uur) FROM tijdslot WHERE dag = 'woensdag'") == 4


def test_onbekende_dag_geweigerd(con):
    with pytest.raises(ValueError):
        maak_tijdslots(con, {"zaterdag": 3})


def test_seed_voorbeeld_aantallen(con):
    seed(con)
    assert _tel(con, "SELECT COUNT(*) FROM tijdslot") == 30
    assert _tel(con, "SELECT COUNT(*) FROM leraar") == 10
    assert _tel(con, "SELECT COUNT(*) FROM lokaal") == 7
    assert _tel(con, "SELECT COUNT(*) FROM lokaal WHERE type = 'regulier'") == 5
    assert _tel(con, "SELECT COUNT(DISTINCT klas) FROM les") == 6
    assert _tel(con, "SELECT SUM(aantal_per_week) FROM les") == 144
    for (uren,) in con.execute("SELECT SUM(aantal_per_week) FROM les GROUP BY klas"):
        assert uren == 24
    assert _tel(con, "SELECT COUNT(DISTINCT leraar_id) FROM onbeschikbaar") == 2


def test_seed_voorbeeld_kan_oplosbaar_zijn(con):
    seed(con)
    slots = _tel(con, "SELECT COUNT(*) FROM tijdslot")
    per_leraar = con.execute(
        """SELECT l.leraar_id, SUM(l.aantal_per_week),
                  (SELECT COUNT(*) FROM onbeschikbaar o WHERE o.leraar_id = l.leraar_id)
           FROM les l GROUP BY l.leraar_id"""
    ).fetchall()
    for _, uren, onbeschikbaar in per_leraar:
        assert uren <= slots - onbeschikbaar
    per_type = con.execute(
        """SELECT l.lokaaltype, SUM(l.aantal_per_week),
                  (SELECT COUNT(*) FROM lokaal r WHERE r.type = l.lokaaltype)
           FROM les l GROUP BY l.lokaaltype"""
    ).fetchall()
    for _, uren, lokalen in per_type:
        assert uren <= 0.85 * lokalen * slots


def test_seed_onmogelijk_heeft_klas_met_te_veel_uren(con):
    seed(con, "onmogelijk")
    slots = _tel(con, "SELECT COUNT(*) FROM tijdslot")
    maximum = _tel(
        con, "SELECT MAX(u) FROM (SELECT SUM(aantal_per_week) u FROM les GROUP BY klas)"
    )
    assert maximum == 32 > slots


def test_onbekende_variant(con):
    with pytest.raises(ValueError):
        seed(con, "bestaat_niet")


def test_seed_twee_keer_geeft_zelfde_aantallen(con):
    seed(con)
    seed(con)
    assert _tel(con, "SELECT SUM(aantal_per_week) FROM les") == 144


def test_leeg_database(con):
    seed(con)
    leeg_database(con)
    assert _tel(con, "SELECT COUNT(*) FROM les") == 0
    assert _tel(con, "SELECT COUNT(*) FROM tijdslot") == 0


def test_les_met_onbekende_leraar_geweigerd(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO les VALUES ('X', 'vak', '1A', 'NIEMAND', 1, 'regulier')")


def test_ongeldig_lokaaltype_geweigerd(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO lokaal VALUES ('Z', 'Zaal', 'zwembad')")


def test_cli_seed(tmp_path, capsys):
    pad = tmp_path / "sub" / "rooster.db"
    main(["seed", "--pad", str(pad)])
    assert "144 lesuren" in capsys.readouterr().out
    con = verbind(pad)
    assert _tel(con, "SELECT SUM(aantal_per_week) FROM les") == 144
    con.close()


def test_seed_groot_aantallen_en_bezetting(con):
    seed(con, "groot")
    assert _tel(con, "SELECT COUNT(DISTINCT klas) FROM les") == 16
    assert _tel(con, "SELECT COUNT(*) FROM leraar") == 28
    assert _tel(con, "SELECT COUNT(*) FROM lokaal") == 16
    assert _tel(con, "SELECT COUNT(*) FROM tijdslot") == 40
    assert _tel(con, "SELECT SUM(aantal_per_week) FROM les") == 512
    for (uren,) in con.execute("SELECT SUM(aantal_per_week) FROM les GROUP BY klas"):
        assert uren == 32
    per_type = con.execute(
        """SELECT l.lokaaltype, SUM(l.aantal_per_week),
                  (SELECT COUNT(*) FROM lokaal r WHERE r.type = l.lokaaltype)
           FROM les l GROUP BY l.lokaaltype"""
    ).fetchall()
    for _, uren, lokalen in per_type:
        assert uren <= 0.85 * lokalen * 40  # krap, maar niet onmogelijk


def test_seed_groot_komt_door_de_validatie(con):
    from src.loader import laad_probleem, valideer

    seed(con, "groot")
    assert [m for m in valideer(laad_probleem(con)) if m.ernst == "fout"] == []
