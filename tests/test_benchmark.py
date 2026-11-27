"""Tests voor de reproduceerbare meting (python -m src.cli bench)."""

from src.benchmark import benchmark, laad_variant
from src.cli import main
from src.models import Instellingen


def test_laad_variant_zonder_bestand():
    data = laad_variant("voorbeeld")
    assert (len(data.klassen), len(data.lesuren), len(data.tijdslots)) == (6, 144, 30)


def test_rapport_noemt_hardware_instellingen_en_uitkomst():
    rapport = benchmark("voorbeeld", Instellingen(1, {"Z1": 10}), runs=1, num_workers=1)
    assert "logische kernen" in rapport
    assert "seed 0" in rapport and "zoekdraden 1" in rapport
    assert "OR-Tools" in rapport
    assert "Run 1:" in rapport and "schendingen 0" in rapport


def test_cli_bench(capsys, monkeypatch):
    monkeypatch.setattr("src.cli._instellingen", lambda t: Instellingen(1, {"Z1": 10}))
    main(["bench", "--runs", "1", "--werkers", "1"])
    uit = capsys.readouterr().out
    assert "Meting op variant 'voorbeeld'" in uit and "Mediaan" in uit
