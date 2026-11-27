"""Tests voor herplannen bij afwezigheid: geldig, zo weinig mogelijk wijzigingen, geen crash."""

from dataclasses import replace

import pytest

from src import service
from src.benchmark import laad_variant
from src.checker import controleer, tel_verplaatst, wijzigingen
from src.config import laad_instellingen
from src.models import Lesuur, Toewijzing, met_afwezigheid
from src.solver import herplan, solve


@pytest.fixture(scope="module")
def voorbeeld():
    data = laad_variant("voorbeeld")
    instellingen = replace(laad_instellingen(), tijdslimiet_s=4, num_workers=4)
    return data, instellingen, solve(data, instellingen).toewijzingen


def _afwezig_op(data, leraar_id, dag):
    return frozenset((leraar_id, s.id) for s in data.tijdslots if s.dag == dag)


def test_zonder_afwezigheid_verandert_er_niets(voorbeeld):
    data, instellingen, rooster = voorbeeld
    r = herplan(data, rooster, frozenset(), instellingen)
    assert tel_verplaatst(wijzigingen(rooster, r.toewijzingen)) == 0


def test_afwezige_leraar_staat_niet_meer_ingepland_en_weinig_verandert(voorbeeld):
    data, instellingen, rooster = voorbeeld
    afwezig = _afwezig_op(data, "PEE", "maandag")
    r = herplan(data, rooster, afwezig, instellingen)
    assert r.status in ("optimaal", "geldig")
    assert controleer(met_afwezigheid(data, afwezig), r.toewijzingen) == []
    getroffen = sum(1 for t in rooster if (t.lesuur.leraar_id, t.tijdslot_id) in afwezig)
    verplaatst = tel_verplaatst(wijzigingen(rooster, r.toewijzingen))
    assert getroffen > 0
    assert getroffen <= verplaatst <= 4 * getroffen  # alleen wat nodig is, niet het hele rooster
    assert verplaatst < len(rooster) // 4


def test_te_veel_afwezigheid_geeft_onoplosbaar_zonder_crash(voorbeeld):
    data, instellingen, rooster = voorbeeld
    hele_week = frozenset(("PEE", s.id) for s in data.tijdslots)
    r = herplan(data, rooster, hele_week, replace(instellingen, tijdslimiet_s=2))
    assert r.status in ("onoplosbaar", "geen_oplossing_binnen_tijd")
    assert r.toewijzingen == ()


def test_checker_telt_wijzigingen_per_les():
    uur1 = Lesuur("A", 1, "wis", "1A", "JAN", "regulier")
    uur2 = Lesuur("A", 2, "wis", "1A", "JAN", "regulier")
    oud = (Toewijzing(uur1, 1, "R1"), Toewijzing(uur2, 2, "R1"))
    geruild = (Toewijzing(uur1, 2, "R1"), Toewijzing(uur2, 1, "R1"))
    verplaatst = (Toewijzing(uur1, 1, "R1"), Toewijzing(uur2, 5, "R2"))
    assert wijzigingen(oud, geruild) == []  # nummers ruilen is geen wijziging
    (w,) = wijzigingen(oud, verplaatst)
    assert (w.van_slot, w.naar_slot, w.van_lokaal, w.naar_lokaal) == (2, 5, "R1", "R2")


def test_service_bewaart_afwezigheid_en_raakt_het_bewaarde_rooster_niet(tmp_path):
    pad = str(tmp_path / "rooster.db")
    service.vul_voorbeeld(pad, "voorbeeld")
    data, _ = service.laad(pad)
    instellingen = replace(laad_instellingen(), tijdslimiet_s=3, num_workers=4)
    berekening = service.bereken(data, instellingen)
    service.bewaar(pad, berekening.resultaat.toewijzingen)
    afwezig = _afwezig_op(data, "MAE", "dinsdag")
    nieuw = service.herplan_rooster(pad, data, berekening, afwezig, instellingen)
    assert nieuw.schendingen == ()
    assert nieuw.afwezig == afwezig and nieuw.wijzigingen
    assert not service.kan_verder(nieuw)
    assert service.afwezigheid(pad) == afwezig
    bewaard = service.bewaard_rooster(pad, data, instellingen)
    assert set(bewaard.resultaat.toewijzingen) == set(berekening.resultaat.toewijzingen)


def test_pagina_herplannen(tmp_path):
    from pathlib import Path

    from conftest import log_in_op_pagina
    from streamlit.testing.v1 import AppTest

    pad = str(tmp_path / "rooster.db")
    service.vul_voorbeeld(pad, "voorbeeld")
    data, _ = service.laad(pad)
    instellingen = replace(laad_instellingen(), tijdslimiet_s=3, num_workers=4)
    service.bewaar(pad, solve(data, instellingen).toewijzingen)
    pagina = Path(__file__).resolve().parent.parent / "paginas" / "2_Rooster.py"
    at = log_in_op_pagina(AppTest.from_file(str(pagina), default_timeout=120), pad).run()
    assert "Herplannen bij afwezigheid (bijvoorbeeld ziekte)" in [e.label for e in at.expander]
    at.multiselect(key="afwezig_docent").select("PEE")
    at.multiselect(key="afwezig_dagen").select("maandag")
    at = at.run()
    at = next(b for b in at.button if b.label == "Herplannen").click().run()
    assert not at.exception
    assert any("Herplanning voor de afwezigheid van Peeters" in m.value for m in at.success)
    assert {m.label: m.value for m in at.metric}["Schendingen"] == "0"
    at = next(b for b in at.button if b.label == "Terug naar het rooster zonder afwezigheid").click().run()
    assert not at.exception
    assert not any("Herplanning" in m.value for m in at.success)
