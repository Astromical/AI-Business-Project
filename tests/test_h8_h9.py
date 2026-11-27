"""Tests voor H8 (lokaalcapaciteit) en H9 (blokuren): solver, checker, loader en database."""

from dataclasses import replace

from src.checker import controleer
from src.db import maak_schema, sla_tabel_op, verbind
from src.loader import laad_probleem, maak_lesuren, valideer
from src.models import Instellingen, Leraar, Les, Lokaal, ProbleemData, Tijdslot, Toewijzing
from src.seed import seed
from src.solver import solve, verbeter_verder

GEEN = {"Z1": 0, "Z2": 0, "Z3": 0, "Z4": 0}


def _slots(dagen=("maandag", "dinsdag"), uren=6) -> tuple[Tijdslot, ...]:
    return tuple(Tijdslot(i * uren + u, dag, u) for i, dag in enumerate(dagen) for u in range(1, uren + 1))


def _data(lessen, lokalen, pauze=0, uren=6) -> ProbleemData:
    leraren = tuple({les.leraar_id: Leraar(les.leraar_id, les.leraar_id, 8) for les in lessen}.values())
    return ProbleemData(_slots(uren=uren), tuple(lokalen), leraren, tuple(lessen), maak_lesuren(tuple(lessen)), pauze)


def _uren(data, resultaat, les_id):
    return sorted(
        (data.tijdslot_per_id[t.tijdslot_id].dag, data.tijdslot_per_id[t.tijdslot_id].uur)
        for t in resultaat.toewijzingen if t.lesuur.les_id == les_id
    )


# --- H9 blokuren ---

def test_blokuur_staat_in_paren_na_elkaar():
    lessen = (
        Les("LAB", "chemie", "1A", "JAN", 4, "regulier", blokuur=True),
        Les("WIS", "wiskunde", "1A", "AN", 4, "regulier"),
    )
    data = _data(lessen, (Lokaal("R1", "Lokaal 1", "regulier"),))
    r = solve(data, Instellingen(2, {"Z1": 10, "Z3": 5}))
    assert r.status in ("optimaal", "geldig")
    assert controleer(data, r.toewijzingen) == []
    uren = _uren(data, r, "LAB")
    per_dag = {}
    for dag, uur in uren:
        per_dag.setdefault(dag, []).append(uur)
    for lijst in per_dag.values():
        assert len(lijst) % 2 == 0
        assert all(b == a + 1 for a, b in zip(lijst[0::2], lijst[1::2]))


def test_blokuur_loopt_niet_over_de_pauze():
    """Met pauze na uur 4 begint een blok nooit op uur 4 (dan zou het over de pauze lopen)."""
    lessen = (Les("B", "chemie", "1A", "JAN", 2, "regulier", blokuur=True),)
    data = _data(lessen, (Lokaal("R1", "Lokaal 1", "regulier"),), pauze=4)
    for _ in range(3):
        r = solve(data, Instellingen(1, GEEN))
        (dag1, u1), (dag2, u2) = _uren(data, r, "B")
        assert dag1 == dag2 and u2 == u1 + 1 and u1 != 4


def test_onmogelijk_blokuur_geeft_onoplosbaar_zonder_crash():
    """Elke dag één uur: twee uren na elkaar bestaan niet."""
    lessen = (Les("B", "chemie", "1A", "JAN", 2, "regulier", blokuur=True),)
    data = _data(lessen, (Lokaal("R1", "Lokaal 1", "regulier"),), uren=1)
    assert any("blokuur" in m.tekst for m in valideer(data))
    assert solve(data, Instellingen(1, GEEN)).status == "onoplosbaar"


def test_oneven_blokuur_geeft_een_fout_bij_validatie():
    lessen = (Les("B", "chemie", "1A", "JAN", 3, "regulier", blokuur=True),)
    data = _data(lessen, (Lokaal("R1", "Lokaal 1", "regulier"),))
    assert any(m.ernst == "fout" and "even aantal" in m.tekst for m in valideer(data))


def test_checker_vindt_een_gebroken_blokuur():
    lessen = (Les("B", "chemie", "1A", "JAN", 2, "regulier", blokuur=True),)
    data = _data(lessen, (Lokaal("R1", "Lokaal 1", "regulier"),), pauze=4)
    gebroken = (Toewijzing(data.lesuren[0], 1, "R1"), Toewijzing(data.lesuren[1], 3, "R1"))
    over_pauze = (Toewijzing(data.lesuren[0], 4, "R1"), Toewijzing(data.lesuren[1], 5, "R1"))
    goed = (Toewijzing(data.lesuren[0], 2, "R1"), Toewijzing(data.lesuren[1], 3, "R1"))
    assert [s.regel for s in controleer(data, gebroken)] == ["H9"]
    assert [s.regel for s in controleer(data, over_pauze)] == ["H9"]
    assert controleer(data, goed) == []


def test_verder_verbeteren_houdt_blokuren():
    lessen = (
        Les("B", "chemie", "1A", "JAN", 2, "regulier", blokuur=True),
        Les("W", "wiskunde", "1A", "AN", 3, "regulier"),
    )
    data = _data(lessen, (Lokaal("R1", "Lokaal 1", "regulier"),))
    start = solve(data, Instellingen(1, GEEN)).toewijzingen
    r = verbeter_verder(data, start, Instellingen(2, {"Z1": 10, "Z3": 5}))
    assert controleer(data, r.toewijzingen) == []


# --- H8 lokaalcapaciteit ---

def test_grote_groep_krijgt_een_groot_genoeg_lokaal():
    lokalen = (Lokaal("K", "Klein", "regulier", 20), Lokaal("G", "Groot", "regulier", 30))
    lessen = (
        Les("A", "wiskunde", "1A", "JAN", 6, "regulier", aantal_leerlingen=28),
        Les("B", "engels", "1B", "AN", 6, "regulier", aantal_leerlingen=18),
    )
    data = _data(lessen, lokalen)
    r = solve(data, Instellingen(1, GEEN))
    assert controleer(data, r.toewijzingen) == []
    assert {t.lokaal_id for t in r.toewijzingen if t.lesuur.les_id == "A"} == {"G"}


def test_twee_grote_groepen_nooit_tegelijk_met_een_groot_lokaal():
    """Eén lokaal voor 30: de twee grote groepen mogen nooit samen ingepland staan."""
    lokalen = (Lokaal("K", "Klein", "regulier", 20), Lokaal("G", "Groot", "regulier", 30))
    lessen = (
        Les("A", "wiskunde", "1A", "JAN", 4, "regulier", aantal_leerlingen=25),
        Les("B", "engels", "1B", "AN", 4, "regulier", aantal_leerlingen=26),
    )
    data = _data(lessen, lokalen)
    r = solve(data, Instellingen(1, GEEN))
    assert controleer(data, r.toewijzingen) == []
    slots_a = {t.tijdslot_id for t in r.toewijzingen if t.lesuur.les_id == "A"}
    slots_b = {t.tijdslot_id for t in r.toewijzingen if t.lesuur.les_id == "B"}
    assert not slots_a & slots_b


def test_te_grote_groep_geeft_een_fout_bij_validatie():
    lokalen = (Lokaal("K", "Klein", "regulier", 20),)
    lessen = (Les("A", "wiskunde", "1A", "JAN", 2, "regulier", aantal_leerlingen=25),)
    meldingen = valideer(_data(lessen, lokalen))
    assert any(m.ernst == "fout" and "25 leerlingen" in m.tekst for m in meldingen)


def test_checker_vindt_een_te_klein_lokaal():
    lokalen = (Lokaal("K", "Klein", "regulier", 20),)
    lessen = (Les("A", "wiskunde", "1A", "JAN", 1, "regulier", aantal_leerlingen=25),)
    data = _data(lessen, lokalen)
    (schending,) = controleer(data, (Toewijzing(data.lesuren[0], 1, "K"),))
    assert schending.regel == "H8" and "25 leerlingen" in schending.tekst


def test_blokuur_en_capaciteit_samen():
    lokalen = (Lokaal("K", "Klein", "regulier", 20), Lokaal("G", "Groot", "regulier", 30))
    lessen = (
        Les("A", "chemie", "1A", "JAN", 4, "regulier", blokuur=True, aantal_leerlingen=28),
        Les("B", "engels", "1B", "AN", 6, "regulier", aantal_leerlingen=18),
        Les("C", "frans", "1B", "PIET", 2, "regulier", blokuur=True, aantal_leerlingen=18),
    )
    data = _data(lessen, lokalen, pauze=4)
    r = solve(data, Instellingen(2, {"Z1": 10}))
    assert r.status in ("optimaal", "geldig")
    assert controleer(data, r.toewijzingen) == []


# --- database ---

def test_capaciteit_en_blokuur_komen_uit_de_database():
    con = verbind(":memory:")
    maak_schema(con)
    seed(con, "voorbeeld")
    sla_tabel_op(con, "lokaal_capaciteit", [{"lokaal_id": "R1", "capaciteit": 24}], [])
    sla_tabel_op(con, "les_eigenschap", [{"les_id": "1A-WIS", "blokuur": 1, "aantal_leerlingen": 22}], [])
    data = laad_probleem(con, pauze_na_uur=4)
    assert data.lokaal_per_id["R1"].capaciteit == 24
    les = data.les_per_id["1A-WIS"]
    assert (les.blokuur, les.aantal_leerlingen) == (True, 22)
    assert data.pauze_na_uur == 4
    assert data.les_per_id["1A-NED"].blokuur is False
    # zonder extra gegevens blijft de voorbeelddata werken zoals voorheen
    assert replace(data, pauze_na_uur=0).lokaal_per_id["R2"].capaciteit is None
    con.close()


def test_beheer_bewaart_blokuur_en_capaciteit_en_wist_lege_rijen():
    import pandas as pd

    from src import beheer

    con = verbind(":memory:")
    maak_schema(con)
    seed(con, "voorbeeld")
    beheer.sla_op(con, "les_eigenschap", pd.DataFrame(
        [{"les_id": "1A-WIS", "blokuur": True, "aantal_leerlingen": 22}, {"les_id": None, "blokuur": False}]
    ))
    beheer.sla_op(con, "lokaal_capaciteit", pd.DataFrame([{"lokaal_id": "R1", "capaciteit": 24}]))
    tabel = beheer.lees(con, "les_eigenschap")
    assert tabel.to_dict("records") == [{"les_id": "1A-WIS", "blokuur": True, "aantal_leerlingen": 22}]
    data = laad_probleem(con)
    assert data.les_per_id["1A-WIS"].blokuur and data.lokaal_per_id["R1"].capaciteit == 24
    # een les verwijderen neemt haar extra gegevens mee
    lessen = beheer.lees(con, "les")
    con.execute("DELETE FROM ingepland")
    beheer.sla_op(con, "les", lessen[lessen["id"] != "1A-WIS"])
    assert beheer.lees(con, "les_eigenschap").empty
    con.close()
