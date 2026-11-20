"""Tests voor de roosterweergave."""

from src.views import keuzes, rooster_html, rooster_tabel, vak_kleur


def test_tabel_per_klas_heeft_juiste_vorm(klein_probleem, klein_rooster):
    tabel = rooster_tabel(klein_probleem, klein_rooster, "klas", "1A")
    assert list(tabel.index) == [1, 2, 3]
    assert list(tabel.columns) == ["maandag", "dinsdag"]
    assert tabel.shape == (3, 2)


def test_tabel_per_klas_inhoud(klein_probleem, klein_rooster):
    tabel = rooster_tabel(klein_probleem, klein_rooster, "klas", "1A")
    assert tabel.loc[1, "maandag"] == "wiskunde\nJan\nLokaal 1"
    assert tabel.loc[3, "dinsdag"] == "biologie\nAn\nLab"
    assert tabel.loc[1, "dinsdag"] == ""


def test_tabel_per_leraar(klein_probleem, klein_rooster):
    tabel = rooster_tabel(klein_probleem, klein_rooster, "leraar", "JAN")
    assert tabel.loc[1, "dinsdag"] == "wiskunde\n1B\nLokaal 1"
    assert tabel.loc[3, "maandag"] == ""


def test_tabel_per_lokaal(klein_probleem, klein_rooster):
    tabel = rooster_tabel(klein_probleem, klein_rooster, "lokaal", "L1")
    assert tabel.loc[1, "maandag"] == "biologie\n1B\nAn"
    assert (tabel == "").sum().sum() == 3  # lab is op 3 van de 6 tijdslots bezet


def test_aantal_gevulde_cellen_komt_overeen_met_lesuren(klein_probleem, klein_rooster):
    totaal = sum(
        (rooster_tabel(klein_probleem, klein_rooster, "klas", klas) != "").sum().sum()
        for klas in klein_probleem.klassen
    )
    assert totaal == len(klein_probleem.lesuren)


def test_kleur_is_vast_per_vak():
    assert vak_kleur("wiskunde") == vak_kleur("wiskunde")
    assert vak_kleur("wiskunde") != vak_kleur("biologie")


def test_html_zet_vak_leraar_en_lokaal_onder_elkaar(klein_probleem, klein_rooster):
    html = rooster_html(klein_probleem, klein_rooster, "klas", "1A")
    assert "<b>wiskunde</b><span>Jan</span><span>Lokaal 1</span>" in html
    assert f"background:{vak_kleur('wiskunde')}" in html
    assert html.count('class="les"') == 4 and html.count('class="leeg"') == 2  # 1A: 4 lesuren, 6 slots
    assert "<th>Maandag</th>" in html and '<th class="uur">1</th>' in html and "Uur" not in html


def test_html_ontsnapt_namen(klein_probleem, klein_rooster):
    from dataclasses import replace

    jan = next(l for l in klein_probleem.leraren if l.id == "JAN")
    leraren = tuple(replace(l, naam="<script>x</script>") if l is jan else l for l in klein_probleem.leraren)
    data = replace(klein_probleem, leraren=leraren)
    html = rooster_html(data, klein_rooster, "klas", "1A")
    assert "<script>x" not in html and "&lt;script&gt;" in html


def test_keuzes(klein_probleem):
    assert keuzes(klein_probleem, "klas") == [("1A", "1A"), ("1B", "1B")]
    assert ("JAN", "Jan") in keuzes(klein_probleem, "leraar")
    assert ("L1", "Lab") in keuzes(klein_probleem, "lokaal")
