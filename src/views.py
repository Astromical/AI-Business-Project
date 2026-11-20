"""Het rooster als tabellen per klas, leraar of lokaal. Kent geen Streamlit."""

from __future__ import annotations

import hashlib
import html
from typing import Literal

import pandas as pd

from src.models import ProbleemData, Toewijzing

Soort = Literal["klas", "leraar", "lokaal"]
SOORTEN: tuple[Soort, ...] = ("klas", "leraar", "lokaal")


def keuzes(data: ProbleemData, soort: Soort) -> list[tuple[str, str]]:
    """De te kiezen (id, naam)-paren voor een soort weergave."""
    if soort == "klas":
        return [(klas, klas) for klas in data.klassen]
    if soort == "leraar":
        return [(leraar.id, leraar.naam) for leraar in data.leraren]
    return [(lokaal.id, lokaal.naam) for lokaal in data.lokalen]


def _hoort_bij(t: Toewijzing, soort: Soort, id: str) -> bool:
    """Hoort deze toewijzing bij de gekozen klas, leraar of lokaal?"""
    if soort == "klas":
        return t.lesuur.klas == id
    if soort == "leraar":
        return t.lesuur.leraar_id == id
    return t.lokaal_id == id


def _regels(t: Toewijzing, soort: Soort, data: ProbleemData) -> tuple[str, str, str]:
    """Vak plus de twee gegevens die niet al uit de gekozen weergave blijken."""
    lokaal = data.lokaal_per_id[t.lokaal_id].naam
    leraar = data.leraar_per_id[t.lesuur.leraar_id].naam
    if soort == "klas":
        return t.lesuur.vak, leraar, lokaal
    if soort == "leraar":
        return t.lesuur.vak, t.lesuur.klas, lokaal
    return t.lesuur.vak, t.lesuur.klas, leraar


def _tekst(t: Toewijzing, soort: Soort, data: ProbleemData) -> str:
    """De celtekst: vak, daaronder de twee andere gegevens."""
    return "\n".join(_regels(t, soort, data))


def _lege_tabel(data: ProbleemData) -> pd.DataFrame:
    """Lege tabel met uren als rijen en dagen als kolommen."""
    uren = sorted({slot.uur for slot in data.tijdslots})
    tabel = pd.DataFrame("", index=uren, columns=list(data.dagen))
    tabel.index.name = "uur"
    return tabel


def _vul(data, toewijzingen, soort, id, tekst) -> pd.DataFrame:
    """Vul een tabel met tekst(t) voor elke toewijzing die bij id hoort."""
    tabel = _lege_tabel(data)
    for t in toewijzingen:
        if _hoort_bij(t, soort, id):
            slot = data.tijdslot_per_id[t.tijdslot_id]
            tabel.loc[slot.uur, slot.dag] = tekst(t)
    return tabel


def rooster_tabel(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], soort: Soort, id: str
) -> pd.DataFrame:
    """Het rooster voor één klas, leraar of lokaal: rijen zijn uren, kolommen dagen."""
    return _vul(data, toewijzingen, soort, id, lambda t: _tekst(t, soort, data))


def vak_kleur(vak: str) -> str:
    """Een vaste, lichte achtergrondkleur voor een vak."""
    tint = int(hashlib.md5(vak.encode("utf-8")).hexdigest(), 16) % 360
    return f"hsl({tint}, 70%, 85%)"


ROOSTER_CSS = """
<style>
.rooster-wrap { overflow-x: auto; }
.rooster { width: 100%; min-width: 640px; border-collapse: separate; border-spacing: 6px;
  table-layout: fixed; }
.rooster th { text-align: left; font-weight: 600; padding: 2px 4px; }
.rooster th.uur { width: 2rem; font-weight: 500; opacity: .7; vertical-align: top; }
.rooster td { vertical-align: top; padding: 0; height: 4.6rem; }
.rooster .les { height: 100%; box-sizing: border-box; padding: 6px 8px; border-radius: 8px;
  border-left: 5px solid rgba(0, 0, 0, .28); color: #1a1a1a; line-height: 1.3; }
.rooster .les b { display: block; font-size: .95rem; }
.rooster .les span { display: block; font-size: .82rem; opacity: .78; }
.rooster .leeg { height: 100%; box-sizing: border-box; border-radius: 8px;
  border: 1px dashed rgba(128, 128, 128, .3); }
</style>
"""


def _cel(t: Toewijzing | None, soort: Soort, data: ProbleemData) -> str:
    """Eén cel: een gekleurd blok met het vak vet en daaronder twee regels, of een leeg vakje."""
    if t is None:
        return '<td><div class="leeg"></div></td>'
    vak, eerste, tweede = (html.escape(regel) for regel in _regels(t, soort, data))
    kleur = vak_kleur(t.lesuur.vak)
    return (
        f'<td><div class="les" style="background:{kleur}">'
        f"<b>{vak}</b><span>{eerste}</span><span>{tweede}</span></div></td>"
    )


def rooster_html(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], soort: Soort, id: str
) -> str:
    """Het rooster voor één klas, leraar of lokaal als HTML: uren als rijen, dagen als kolommen."""
    per_slot = {
        (data.tijdslot_per_id[t.tijdslot_id].dag, data.tijdslot_per_id[t.tijdslot_id].uur): t
        for t in toewijzingen
        if _hoort_bij(t, soort, id)
    }
    uren = sorted({slot.uur for slot in data.tijdslots})
    kop = "".join(f"<th>{html.escape(dag.capitalize())}</th>" for dag in data.dagen)
    rijen = "".join(
        f'<tr><th class="uur">{uur}</th>'
        + "".join(_cel(per_slot.get((dag, uur)), soort, data) for dag in data.dagen)
        + "</tr>"
        for uur in uren
    )
    return (
        f'{ROOSTER_CSS}<div class="rooster-wrap"><table class="rooster">'
        f'<tr><th class="uur"></th>{kop}</tr>{rijen}</table></div>'
    )


def rooster_csv(data: ProbleemData, toewijzingen: tuple[Toewijzing, ...]) -> str:
    """Het hele rooster als CSV met de kolommen klas, dag, uur, vak, leraar, lokaal."""
    dag_volgorde = {dag: i for i, dag in enumerate(data.dagen)}
    rijen = []
    for t in toewijzingen:
        slot = data.tijdslot_per_id[t.tijdslot_id]
        rijen.append(
            {
                "klas": t.lesuur.klas,
                "dag": slot.dag,
                "uur": slot.uur,
                "vak": t.lesuur.vak,
                "leraar": data.leraar_per_id[t.lesuur.leraar_id].naam,
                "lokaal": data.lokaal_per_id[t.lokaal_id].naam,
            }
        )
    tabel = pd.DataFrame(rijen, columns=["klas", "dag", "uur", "vak", "leraar", "lokaal"])
    tabel["_dag"] = tabel["dag"].map(dag_volgorde)
    tabel = tabel.sort_values(["klas", "_dag", "uur"]).drop(columns="_dag")
    return tabel.to_csv(index=False, lineterminator="\n")
