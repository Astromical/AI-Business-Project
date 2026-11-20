"""Tests voor de snellere solver: lokalen na het oplossen, symmetriebreking, vaste seed,
aantal werkers, stoppen tijdens het rekenen en de tijdsgrens van de uitleg."""

import os
import threading
import time
from dataclasses import replace

import pytest

from src.checker import controleer
from src.config import laad_instellingen
from src.constraints import slotvolgorde
from src.db import maak_schema, verbind
from src.loader import laad_probleem, maak_lesuren
from src.lokalen import wijs_lokalen_toe
from src.models import Instellingen, Leraar, Les, Lokaal, ProbleemData, Tijdslot, Toewijzing
from src.seed import seed
from src.solver import Voortgang, nieuwe_solver, solve, verbeter_verder
from src.uitleg import verklaar


@pytest.fixture(scope="module")
def groot(tmp_path_factory):
    con = verbind(tmp_path_factory.mktemp("groot") / "g.db")
    maak_schema(con)
    seed(con, "groot")
    data = laad_probleem(con)
    con.close()
    return data


def _drie_uur(lokalen: tuple[Lokaal, ...], lessen: tuple[Les, ...]) -> ProbleemData:
    slots = tuple(Tijdslot(u, "maandag", u) for u in (1, 2, 3))
    leraren = (Leraar("JAN", "Jan", 3), Leraar("AN", "An", 3))
    return ProbleemData(slots, lokalen, leraren, lessen, maak_lesuren(lessen))


def test_lokalen_volgen_het_type():
    lokalen = (Lokaal("L1", "Lab", "lab"), Lokaal("R1", "Lokaal 1", "regulier"))
    lessen = (Les("A", "wis", "1A", "JAN", 1, "regulier"), Les("B", "bio", "1B", "AN", 1, "lab"))
    data = _drie_uur(lokalen, lessen)
    toewijzingen = wijs_lokalen_toe(data, {0: 1, 1: 1})
    assert {t.lesuur.les_id: t.lokaal_id for t in toewijzingen} == {"A": "R1", "B": "L1"}
    assert controleer(data, toewijzingen) == []


def test_zonder_h5_mag_een_les_in_een_ander_lokaal():
    lokalen = (Lokaal("L1", "Lab", "lab"), Lokaal("R1", "Lokaal 1", "regulier"))
    lessen = (Les("A", "wis", "1A", "JAN", 1, "regulier"), Les("B", "ned", "1B", "AN", 1, "regulier"))
    data = _drie_uur(lokalen, lessen)
    toewijzingen = wijs_lokalen_toe(data, {0: 1, 1: 1}, frozenset({"H5"}))
    assert sorted(t.lokaal_id for t in toewijzingen) == ["L1", "R1"]


def test_klas_houdt_haar_lokaal_als_het_kan():
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"), Lokaal("R2", "Lokaal 2", "regulier"))
    lessen = (Les("A", "wis", "1A", "JAN", 1, "regulier"), Les("B", "ned", "1B", "AN", 2, "regulier"))
    data = _drie_uur(lokalen, lessen)
    toewijzingen = wijs_lokalen_toe(data, {0: 1, 1: 1, 2: 2})  # 1B op uur 1 en 2
    lokaal_1b = {t.lokaal_id for t in toewijzingen if t.lesuur.klas == "1B"}
    assert len(lokaal_1b) == 1


def test_volgnummers_staan_in_weekvolgorde(klein_probleem):
    resultaat = solve(klein_probleem, Instellingen(5, symmetrie_breken=True))
    plaats = slotvolgorde(klein_probleem)
    per_les: dict[str, list[tuple[int, int]]] = {}
    for t in resultaat.toewijzingen:
        per_les.setdefault(t.lesuur.les_id, []).append((t.lesuur.volgnummer, plaats[t.tijdslot_id]))
    for uren in per_les.values():
        posities = [p for _, p in sorted(uren)]
        assert posities == sorted(posities)


def test_verder_rekenen_met_omgekeerde_volgnummers(klein_probleem):
    """Een bewaard rooster mag de lesuren van een les in een andere volgorde hebben."""
    rooster = solve(klein_probleem, Instellingen(5, {"Z1": 0})).toewijzingen
    wis = sorted((t for t in rooster if t.lesuur.les_id == "1A-WIS"), key=lambda t: t.lesuur.volgnummer)
    omgedraaid = {wis[0]: replace(wis[0], tijdslot_id=wis[1].tijdslot_id),
                  wis[1]: replace(wis[1], tijdslot_id=wis[0].tijdslot_id)}
    start = tuple(omgedraaid.get(t, t) for t in rooster)
    assert controleer(klein_probleem, start) == []
    instellingen = Instellingen(5, {"Z1": 10}, symmetrie_breken=True)
    resultaat = verbeter_verder(klein_probleem, start, instellingen)
    assert controleer(klein_probleem, resultaat.toewijzingen) == []


def test_seed_en_werkers_uit_config(tmp_path):
    pad = tmp_path / "c.toml"
    pad.write_text("random_seed = 7\nnum_workers = 3\nsymmetrie_breken = true\n", encoding="utf-8")
    instellingen = laad_instellingen(pad)
    assert (instellingen.random_seed, instellingen.num_workers) == (7, 3)
    assert instellingen.symmetrie_breken
    solver = nieuwe_solver(5, instellingen)
    assert solver.parameters.random_seed == 7
    assert solver.parameters.num_workers == 3


def test_nul_werkers_betekent_alle_kernen():
    assert nieuwe_solver(5, Instellingen()).parameters.num_workers == (os.cpu_count() or 8)


def test_een_werker_geeft_telkens_hetzelfde_rooster(klein_probleem):
    instellingen = Instellingen(2, {"Z1": 10}, num_workers=1)
    eerste = solve(klein_probleem, instellingen)
    tweede = solve(klein_probleem, instellingen)
    assert eerste.toewijzingen == tweede.toewijzingen


def test_stoppen_voor_de_start_rekent_niet(klein_probleem):
    voortgang = Voortgang()
    voortgang.stop()
    resultaat = solve(klein_probleem, Instellingen(30), voortgang=voortgang)
    assert resultaat.gestopt
    assert resultaat.oplostijd_s < 5


def test_stoppen_tijdens_verbeteren_houdt_het_beste_rooster(groot):
    voortgang = Voortgang()
    uitkomst = {}
    draad = threading.Thread(target=lambda: uitkomst.update(r=solve(groot, Instellingen(120), voortgang=voortgang)))
    begin = time.monotonic()
    draad.start()
    while voortgang.fase != "verbeteren" and draad.is_alive():
        time.sleep(0.1)
    time.sleep(1)
    voortgang.stop()
    draad.join(60)
    resultaat = uitkomst["r"]
    assert resultaat.gestopt
    assert time.monotonic() - begin < 60  # niet de volle 120 s
    assert len(resultaat.toewijzingen) == len(groot.lesuren)
    assert controleer(groot, resultaat.toewijzingen) == []
    assert resultaat.strafscore is not None


def _groot_onoplosbaar(groot: ProbleemData) -> ProbleemData:
    """De drukste leraar heeft één beschikbaar uur te weinig."""
    uren: dict[str, int] = {}
    for uur in groot.lesuren:
        uren[uur.leraar_id] = uren.get(uur.leraar_id, 0) + 1
    drukste = max(uren, key=uren.get)
    slots = sorted(s.id for s in groot.tijdslots)
    weg = frozenset(slots[uren[drukste] - 1:])
    leraren = tuple(replace(l, onbeschikbaar=weg) if l.id == drukste else l for l in groot.leraren)
    return replace(groot, leraren=leraren)


def test_uitleg_wijst_de_leraar_aan_binnen_het_budget(groot):
    data = _groot_onoplosbaar(groot)
    begin = time.monotonic()
    uitleg = verklaar(data, 20)
    assert time.monotonic() - begin < 20 + 5  # budget plus het bouwen van de modellen
    assert [regel for regel, _ in uitleg.oorzaken] == ["H6"]


def test_uitleg_zonder_tijd_zegt_dat_eerlijk(groot):
    uitleg = verklaar(_groot_onoplosbaar(groot), 0)
    assert uitleg.oorzaken == ()
    assert "niet gevonden" in uitleg.teksten[0]


def test_toewijzing_is_gewoon_een_toewijzing():
    """Het type van de uitvoer verandert niet: Toewijzing met lesuur, tijdslot en lokaal."""
    lokalen = (Lokaal("R1", "Lokaal 1", "regulier"),)
    data = _drie_uur(lokalen, (Les("A", "wis", "1A", "JAN", 1, "regulier"),))
    (t,) = wijs_lokalen_toe(data, {0: 2})
    assert t == Toewijzing(data.lesuren[0], 2, "R1")
