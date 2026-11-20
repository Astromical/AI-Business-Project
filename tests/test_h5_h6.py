"""Tests voor H5 (lokaaltype) en H6 (onbeschikbaarheid)."""

from dataclasses import replace

from src.constraints import toegelaten_lokalen
from src.loader import maak_lesuren
from src.models import Leraar, Les, Lokaal, ProbleemData
from src.models import Instellingen
from src.solver import solve


def _klein(lessen, lokalen, leraren, tijdslots):
    return ProbleemData(tijdslots, lokalen, leraren, lessen, maak_lesuren(lessen))


def test_toegelaten_lokalen_per_type(klein_probleem):
    lab_uur = next(u for u in klein_probleem.lesuren if u.lokaaltype == "lab")
    gewoon_uur = next(u for u in klein_probleem.lesuren if u.lokaaltype == "regulier")
    assert toegelaten_lokalen(lab_uur, klein_probleem) == ("L1",)
    assert toegelaten_lokalen(gewoon_uur, klein_probleem) == ("R1",)


def test_h5_lab_les_staat_in_het_lab(klein_probleem):
    resultaat = solve(klein_probleem, Instellingen(10))
    for t in resultaat.toewijzingen:
        soort = klein_probleem.lokaal_per_id[t.lokaal_id].type
        assert soort == t.lesuur.lokaaltype


def test_h5_precies_dat_ene_lokaal(klein_probleem):
    lessen = (Les("A", "bio", "1A", "JAN", 1, "lab"),)
    data = _klein(lessen, klein_probleem.lokalen, klein_probleem.leraren, klein_probleem.tijdslots)
    resultaat = solve(data, Instellingen(10))
    assert [t.lokaal_id for t in resultaat.toewijzingen] == ["L1"]


def test_h5_faalt_zonder_regel(klein_probleem):
    # twee labuuren tegelijk kunnen niet in 1 lab; met H5 uit staan ze in een ander lokaal
    lessen = tuple(Les(f"K{i}", "bio", f"K{i}", f"L{i}", 6, "lab") for i in range(2))
    leraren = (Leraar("L0", "A", 6), Leraar("L1", "B", 6))
    data = _klein(lessen, klein_probleem.lokalen, leraren, klein_probleem.tijdslots)
    assert solve(data, Instellingen(10)).status == "onoplosbaar"
    zonder = solve(data, Instellingen(10), uitgeschakeld=frozenset({"H5"}))
    assert zonder.status in ("optimaal", "geldig")


def test_h6_leraar_beschikbaar_op_een_tijdslot(klein_probleem):
    slots = klein_probleem.tijdslots
    jan = Leraar("JAN", "Jan", 3, frozenset(s.id for s in slots if s.id != 4))
    lessen = (Les("A", "wis", "1A", "JAN", 1, "regulier"),)
    data = _klein(lessen, klein_probleem.lokalen, (jan,), slots)
    resultaat = solve(data, Instellingen(10))
    assert [t.tijdslot_id for t in resultaat.toewijzingen] == [4]


def test_h6_faalt_zonder_regel(klein_probleem):
    slots = klein_probleem.tijdslots
    jan = Leraar("JAN", "Jan", 3, frozenset(s.id for s in slots if s.id != 4))
    lessen = (Les("A", "wis", "1A", "JAN", 2, "regulier"),)
    data = _klein(lessen, klein_probleem.lokalen, (jan,), slots)
    assert solve(data, Instellingen(10)).status == "onoplosbaar"
    zonder = solve(data, Instellingen(10), uitgeschakeld=frozenset({"H6"}))
    assert zonder.status in ("optimaal", "geldig")


def test_voorbeelddata_met_h5_h6_blijft_oplosbaar(tmp_path):
    from src.db import maak_schema, verbind
    from src.loader import laad_probleem
    from src.seed import seed

    con = verbind(tmp_path / "t.db")
    maak_schema(con)
    seed(con)
    data = laad_probleem(con)
    con.close()
    resultaat = solve(data, Instellingen(30))
    assert resultaat.status in ("optimaal", "geldig")
    assert resultaat.tijd_zoeken_s < 30  # eerste geldige rooster; fase 2 krijgt zelf de tijdslimiet
    for t in resultaat.toewijzingen:
        assert data.lokaal_per_id[t.lokaal_id].type == t.lesuur.lokaaltype
        assert t.tijdslot_id not in data.leraar_per_id[t.lesuur.leraar_id].onbeschikbaar
    print(f"oplostijd {resultaat.oplostijd_s:.1f}s")
