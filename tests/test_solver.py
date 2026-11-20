"""Tests voor de solver en de harde regels H1-H4.

De uitkomst wordt hier met gewone Python gecontroleerd, los van het model.
"""

from collections import Counter

import pytest

from src.cli import main
from src.db import maak_schema, verbind
from src.loader import laad_probleem
from src.seed import seed
from src.models import Instellingen
from src.solver import solve


@pytest.fixture
def resultaat(klein_probleem):
    return solve(klein_probleem, Instellingen(10))


def test_klein_probleem_geeft_geldig_rooster(klein_probleem, resultaat):
    assert resultaat.status in ("optimaal", "geldig")
    assert len(resultaat.toewijzingen) == len(klein_probleem.lesuren)


def test_onmogelijk_probleem_is_onoplosbaar(onmogelijk_probleem):
    resultaat = solve(onmogelijk_probleem, Instellingen(10))
    assert resultaat.status == "onoplosbaar"
    assert resultaat.toewijzingen == ()


def test_h1_elk_lesuur_precies_een_keer(klein_probleem, resultaat):
    gepland = Counter((t.lesuur.les_id, t.lesuur.volgnummer) for t in resultaat.toewijzingen)
    verwacht = {(u.les_id, u.volgnummer) for u in klein_probleem.lesuren}
    assert set(gepland) == verwacht
    assert set(gepland.values()) == {1}


def test_h2_geen_dubbel_lokaal(resultaat):
    tellers = Counter((t.tijdslot_id, t.lokaal_id) for t in resultaat.toewijzingen)
    assert max(tellers.values()) == 1


def test_h3_geen_dubbele_leraar(resultaat):
    tellers = Counter((t.lesuur.leraar_id, t.tijdslot_id) for t in resultaat.toewijzingen)
    assert max(tellers.values()) == 1


def test_h4_geen_dubbele_klas(resultaat):
    tellers = Counter((t.lesuur.klas, t.tijdslot_id) for t in resultaat.toewijzingen)
    assert max(tellers.values()) == 1


def test_voorbeelddata_binnen_30_seconden(tmp_path):
    con = verbind(tmp_path / "t.db")
    maak_schema(con)
    seed(con)
    data = laad_probleem(con)
    con.close()
    resultaat = solve(data, Instellingen(30))
    assert resultaat.status in ("optimaal", "geldig")
    assert resultaat.tijd_zoeken_s < 30  # eerste geldige rooster; fase 2 krijgt zelf de tijdslimiet
    assert len(resultaat.toewijzingen) == 144
    assert max(Counter((t.lesuur.klas, t.tijdslot_id) for t in resultaat.toewijzingen).values()) == 1


def test_cli_solve(tmp_path, capsys):
    pad = str(tmp_path / "r.db")
    main(["seed", "--pad", pad])
    main(["solve", "--pad", pad])
    uitvoer = capsys.readouterr().out
    assert "Status:" in uitvoer
    assert "Klas 1A" in uitvoer


def test_cli_solve_zonder_database(tmp_path, capsys):
    main(["solve", "--pad", str(tmp_path / "bestaat_niet.db")])
    assert "bestaat niet" in capsys.readouterr().out
