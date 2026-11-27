"""Harde en zachte regels voor het CP-SAT-model, elk als aparte functie.

De variabele x[l, s] is 1 als lesuur l (index in data.lesuren) in tijdslot s (id)
staat. Lokalen zitten niet in het model: lokalen van hetzelfde type zijn
uitwisselbaar, dus het model eist alleen dat er per tijdslot en per type genoeg
lokalen zijn (H2 en H5 samen). Na het oplossen wijst src/lokalen.py de lokalen toe.

Schakelaars maken een harde regel per leraar of lokaaltype uitschakelbaar: de
regel geldt alleen als de literal 1 is. Sleutels: ("H5", type), ("H6", leraar_id),
("H6", leraar_id, tijdslot_id) en ("H7", leraar_id).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Hashable

from ortools.sat.python import cp_model

from src.models import DAGEN, Lesuur, ProbleemData

Variabelen = dict[tuple[int, int], cp_model.IntVar]
Schakelaars = dict[tuple[str, ...], cp_model.IntVar]


def _groepeer(
    x: Variabelen, sleutel: Callable[[int, int], Hashable]
) -> dict[Hashable, list[cp_model.IntVar]]:
    """Verzamel de variabelen per groep, bepaald door sleutel(l, s)."""
    groepen: dict[Hashable, list[cp_model.IntVar]] = defaultdict(list)
    for (l, s), var in x.items():
        groepen[sleutel(l, s)].append(var)
    return groepen


def _geldt_als(beperking: cp_model.Constraint, schakelaar: cp_model.IntVar | None) -> None:
    """Laat een beperking alleen gelden als de schakelaar 1 is (zonder schakelaar: altijd)."""
    if schakelaar is not None:
        beperking.OnlyEnforceIf(schakelaar)


def h1_elk_lesuur_een_keer(model: cp_model.CpModel, x: Variabelen, data: ProbleemData) -> None:
    """H1: elk lesuur staat precies één keer ingepland."""
    per_lesuur = _groepeer(x, lambda l, s: l)
    for l in range(len(data.lesuren)):
        if l in per_lesuur:
            model.AddExactlyOne(per_lesuur[l])
        else:  # een lesuur zonder enige plaats kan niet ingepland worden
            model.AddBoolOr([])


def toegelaten_lokalen(lesuur: Lesuur, data: ProbleemData) -> tuple[str, ...]:
    """H5: de ids van de lokalen met het type dat het lesuur vraagt."""
    return tuple(lokaal.id for lokaal in data.lokalen if lokaal.type == lesuur.lokaaltype)


def h2_h5_genoeg_lokalen(
    model: cp_model.CpModel,
    x: Variabelen,
    data: ProbleemData,
    uitgeschakeld: frozenset[str] = frozenset(),
    schakelaars: Schakelaars | None = None,
) -> None:
    """H2 en H5: per tijdslot niet meer lesuren dan lokalen, en per type niet meer dan
    lokalen van dat type.

    Daarmee bestaat er altijd een toewijzing van lokalen (stelling van Hall): eerst de
    lesuren die hun eigen type moeten krijgen, daarna de rest in de vrije lokalen.
    Met H5 uit (helemaal of voor één type) mag zo'n lesuur in elk lokaal.
    """
    schakelaars = schakelaars or {}
    per_slot = _groepeer(x, lambda l, s: s)
    per_type_slot = _groepeer(x, lambda l, s: (data.lesuren[l].lokaaltype, s))
    aantal: dict[str, int] = defaultdict(int)
    for lokaal in data.lokalen:
        aantal[lokaal.type] += 1
    for vars_ in per_slot.values():
        model.Add(sum(vars_) <= len(data.lokalen))
    if "H5" in uitgeschakeld:
        return
    for (soort, _), vars_ in per_type_slot.items():
        if f"H5:{soort}" not in uitgeschakeld:
            _geldt_als(model.Add(sum(vars_) <= aantal[soort]), schakelaars.get(("H5", soort)))


def h6_onbeschikbaarheid(
    model: cp_model.CpModel, x: Variabelen, data: ProbleemData, schakelaars: Schakelaars | None = None
) -> None:
    """H6: een leraar staat niet ingepland op een onbeschikbaar tijdslot."""
    schakelaars = schakelaars or {}
    onbeschikbaar = {leraar.id: leraar.onbeschikbaar for leraar in data.leraren}
    for (l, s), var in x.items():
        leraar_id = data.lesuren[l].leraar_id
        if s in onbeschikbaar.get(leraar_id, ()):
            schakelaar = schakelaars.get(("H6", leraar_id), schakelaars.get(("H6", leraar_id, s)))
            _geldt_als(model.Add(var == 0), schakelaar)


def h7_max_uren_per_dag(
    model: cp_model.CpModel, x: Variabelen, data: ProbleemData, schakelaars: Schakelaars | None = None
) -> None:
    """H7: een leraar geeft per dag niet meer dan zijn maximum."""
    schakelaars = schakelaars or {}
    leraar = [uur.leraar_id for uur in data.lesuren]
    dag = {slot.id: slot.dag for slot in data.tijdslots}
    maximum = {l.id: l.max_uren_per_dag for l in data.leraren}
    groepen = _groepeer(x, lambda l, s: (leraar[l], dag[s]))
    for (leraar_id, _), vars_ in groepen.items():
        _geldt_als(model.Add(sum(vars_) <= maximum[leraar_id]), schakelaars.get(("H7", leraar_id)))


def h3_leraar_een_les(model: cp_model.CpModel, x: Variabelen, data: ProbleemData) -> None:
    """H3: een leraar geeft per tijdslot hoogstens één les."""
    leraar = [uur.leraar_id for uur in data.lesuren]
    for vars_ in _groepeer(x, lambda l, s: (leraar[l], s)).values():
        model.AddAtMostOne(vars_)


def h4_klas_een_les(model: cp_model.CpModel, x: Variabelen, data: ProbleemData) -> None:
    """H4: een klas heeft per tijdslot hoogstens één les."""
    klas = [uur.klas for uur in data.lesuren]
    for vars_ in _groepeer(x, lambda l, s: (klas[l], s)).values():
        model.AddAtMostOne(vars_)


def volgende_slot(data: ProbleemData) -> dict[int, int]:
    """Per tijdslot het tijdslot één uur later op dezelfde dag, als een blokuur daar mag doorlopen.

    Na het laatste uur van een dag en over de pauze (na data.pauze_na_uur) is er geen volgende.
    """
    per_dag_uur = {(slot.dag, slot.uur): slot.id for slot in data.tijdslots}
    volgende = {}
    for slot in data.tijdslots:
        if data.pauze_na_uur and slot.uur == data.pauze_na_uur:
            continue
        nxt = per_dag_uur.get((slot.dag, slot.uur + 1))
        if nxt is not None:
            volgende[slot.id] = nxt
    return volgende


def blokparen(data: ProbleemData) -> list[tuple[int, int]]:
    """De lesuren (indexen) die samen een blokuur vormen: volgnummer 1 en 2, 3 en 4, ..."""
    blok = {les.id for les in data.lessen if les.blokuur}
    per_les: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for l, uur in enumerate(data.lesuren):
        if uur.les_id in blok:
            per_les[uur.les_id].append((uur.volgnummer, l))
    paren = []
    for uren in per_les.values():
        volgorde = [l for _, l in sorted(uren)]
        paren += list(zip(volgorde[0::2], volgorde[1::2]))
    return paren


def h9_blokuren(model: cp_model.CpModel, x: Variabelen, data: ProbleemData) -> None:
    """H9: de twee lesuren van een blok staan direct na elkaar op dezelfde dag, niet over de pauze.

    Het eerste uur van het blok bepaalt het tweede: x[b, volgende(s)] = x[a, s]. Een slot
    zonder volgende kan geen eerste uur zijn, een slot zonder vorige geen tweede uur.
    """
    volgende = volgende_slot(data)
    heeft_vorige = set(volgende.values())
    for a, b in blokparen(data):
        for slot in data.tijdslots:
            s = slot.id
            if s in volgende:
                model.Add(x[b, volgende[s]] == x[a, s])
            else:
                model.Add(x[a, s] == 0)
            if s not in heeft_vorige:
                model.Add(x[b, s] == 0)


def _past(lokaal_capaciteit: int | None, leerlingen: int) -> bool:
    """Past een groep van zoveel leerlingen in een lokaal (None: geen grens)?"""
    return lokaal_capaciteit is None or lokaal_capaciteit >= leerlingen


def h8_lokaalcapaciteit(
    model: cp_model.CpModel, x: Variabelen, data: ProbleemData, uitgeschakeld: frozenset[str] = frozenset()
) -> None:
    """H8: een les komt nooit in een te klein lokaal.

    Zoals bij H2 en H5 zonder lokaalvariabelen: per tijdslot en per grens c niet meer
    lesuren met minstens c leerlingen dan lokalen waar c leerlingen in passen (per type,
    en over alle types samen). Omdat die groepen in elkaar passen, bestaat er dan altijd
    een toewijzing: de grootste groepen eerst (zie src/lokalen.py).
    """
    leerlingen = [data.les_per_id[uur.les_id].aantal_leerlingen or 0 for uur in data.lesuren]
    grenzen = sorted({n for n in leerlingen if n > 0})
    if not grenzen or all(lokaal.capaciteit is None for lokaal in data.lokalen):
        return
    met_type = "H5" not in uitgeschakeld
    for c in grenzen:
        groot = _groepeer(
            {k: v for k, v in x.items() if leerlingen[k[0]] >= c},
            lambda l, s: (data.lesuren[l].lokaaltype if met_type else "", s),
        )
        for (soort, _), vars_ in groot.items():
            plaats = sum(
                1 for r in data.lokalen
                if _past(r.capaciteit, c) and (not soort or r.type == soort)
            )
            model.Add(sum(vars_) <= plaats)


def slotvolgorde(data: ProbleemData) -> dict[int, int]:
    """De plaats van elk tijdslot in de week: maandag uur 1 eerst."""
    dagnummer = {dag: i for i, dag in enumerate(DAGEN)}
    geordend = sorted(data.tijdslots, key=lambda s: (dagnummer.get(s.dag, len(DAGEN)), s.uur, s.id))
    return {slot.id: i for i, slot in enumerate(geordend)}


def volgorde_binnen_les(model: cp_model.CpModel, x: Variabelen, data: ProbleemData) -> None:
    """Symmetrie breken: de lesuren van één les zijn uitwisselbaar, dus volgnummer n
    staat altijd vroeger in de week dan volgnummer n + 1.

    Dit sluit geen enkel rooster uit (alleen de nummering ligt vast), maar CP-SAT
    hoeft zo niet alle gelijkwaardige nummeringen te doorzoeken.
    """
    positie = _posities(x, slotvolgorde(data))
    per_les: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for l, uur in enumerate(data.lesuren):
        per_les[uur.les_id].append((uur.volgnummer, l))
    for uren in per_les.values():
        volgorde = [l for _, l in sorted(uren)]
        for eerder, later in zip(volgorde, volgorde[1:]):
            if eerder in positie and later in positie:
                model.Add(positie[eerder] < positie[later])


def _posities(x: Variabelen, plaats: dict[int, int]) -> dict[int, cp_model.LinearExpr]:
    """Per lesuur de plaats in de week van zijn tijdslot, als lineaire uitdrukking."""
    termen: dict[int, list[tuple[int, cp_model.IntVar]]] = defaultdict(list)
    for (l, s), var in x.items():
        termen[l].append((plaats[s], var))
    return {
        l: cp_model.LinearExpr.WeightedSum([v for _, v in t], [p for p, _ in t])
        for l, t in termen.items()
    }


def _reif_of(model: cp_model.CpModel, literals: list[cp_model.IntVar]) -> cp_model.IntVar:
    """Een variabele die 1 is precies dan als minstens één literal 1 is."""
    var = model.NewBoolVar("of")
    model.AddBoolOr(literals).OnlyEnforceIf(var)
    model.AddBoolAnd([lit.Not() for lit in literals]).OnlyEnforceIf(var.Not())
    return var


def z1_tussenuren_klassen(
    model: cp_model.CpModel, x: Variabelen, data: ProbleemData
) -> list[cp_model.IntVar]:
    """Z1: geef een strafvariabele per tussenuur van een klas."""
    return _tussenuren(model, x, data, lambda uur: uur.klas, data.klassen)


def z2_tussenuren_leraren(
    model: cp_model.CpModel, x: Variabelen, data: ProbleemData
) -> list[cp_model.IntVar]:
    """Z2: geef een strafvariabele per tussenuur van een leraar."""
    leraren = tuple(leraar.id for leraar in data.leraren)
    return _tussenuren(model, x, data, lambda uur: uur.leraar_id, leraren)


def z3_vak_een_keer_per_dag(
    model: cp_model.CpModel, x: Variabelen, data: ProbleemData
) -> list[cp_model.IntVar]:
    """Z3: per klas, vak en dag een straf van max(0, n - 1) voor n lesuren van dat vak.

    De straf is met AddMaxEquality exact gelijk aan max(0, n - 1), niet alleen een ondergrens.
    """
    vak = [(uur.klas, uur.vak) for uur in data.lesuren]
    totaal: dict[tuple[str, str], int] = defaultdict(int)
    for sleutel in vak:
        totaal[sleutel] += 1
    dag = {slot.id: slot.dag for slot in data.tijdslots}
    groepen = _groepeer(x, lambda l, s: (vak[l], dag[s]))
    straf: list[cp_model.IntVar] = []
    for ((klas, naam), d), vars_ in groepen.items():
        n_max = totaal[klas, naam]
        if n_max < 2:  # één lesuur per week kan nooit dubbel staan
            continue
        n = model.NewIntVar(0, n_max, f"n_{klas}_{naam}_{d}")
        model.Add(n == sum(vars_))
        dubbel = model.NewIntVar(0, n_max - 1, f"dubbel_{klas}_{naam}_{d}")
        model.AddMaxEquality(dubbel, [n - 1, 0])
        straf.append(dubbel)
    return straf


def z4_zware_vakken_laatste_uur(
    model: cp_model.CpModel,
    x: Variabelen,
    data: ProbleemData,
    zware_vakken: tuple[str, ...] = (),
) -> list[cp_model.IntVar]:
    """Z4: de x-variabelen van zware vakken in het laatste uur van een dag.

    Het laatste uur is per dag het hoogste uur in de tijdslots, zodat een kortere dag
    (bijvoorbeeld woensdag) meetelt met zijn eigen laatste uur.
    """
    zwaar = {vak.lower() for vak in zware_vakken}
    laatste: dict[str, int] = {}
    for slot in data.tijdslots:
        laatste[slot.dag] = max(laatste.get(slot.dag, 0), slot.uur)
    laatste_slots = {slot.id for slot in data.tijdslots if slot.uur == laatste[slot.dag]}
    return [
        var
        for (l, s), var in x.items()
        if s in laatste_slots and data.lesuren[l].vak.lower() in zwaar
    ]


def _tussenuren(
    model: cp_model.CpModel,
    x: Variabelen,
    data: ProbleemData,
    groep_van: Callable[[Lesuur], str],
    groepen: tuple[str, ...],
) -> list[cp_model.IntVar]:
    """Strafvariabelen voor de tussenuren per groep (klas of leraar) en dag.

    Een tussenuur is een vrij uur met eerder en later die dag nog een les. Alle
    hulpvariabelen zijn in beide richtingen gekoppeld, dus een strafvariabele is
    precies dan 1 als er echt een tussenuur is.
    """
    groep = [groep_van(uur) for uur in data.lesuren]
    per_groep_slot = _groepeer(x, lambda l, s: (groep[l], s))
    straf: list[cp_model.IntVar] = []
    for g in groepen:
        for dag in data.dagen:
            slots = sorted((s for s in data.tijdslots if s.dag == dag), key=lambda s: s.uur)
            bezet = []
            for slot in slots:
                b = model.NewBoolVar(f"bezet_{g}_{slot.id}")
                model.Add(sum(per_groep_slot.get((g, slot.id), [])) == b)
                bezet.append(b)
            straf += _tussenuren_van_dag(model, bezet)
    return straf


def _tussenuren_van_dag(
    model: cp_model.CpModel, bezet: list[cp_model.IntVar]
) -> list[cp_model.IntVar]:
    """Strafvariabelen voor de binnenste uren van één dag (eerste en laatste kunnen geen gat zijn)."""
    n = len(bezet)
    if n < 3:
        return []
    eerder = [None, bezet[0]]  # eerder[i]: er is een les op een uur voor uur i
    for i in range(1, n - 2):
        eerder.append(_reif_of(model, [eerder[i], bezet[i]]))
    later = [None] * n  # later[i]: er is een les op een uur na uur i
    later[n - 2] = bezet[n - 1]
    for i in range(n - 3, 0, -1):
        later[i] = _reif_of(model, [later[i + 1], bezet[i + 1]])
    straf = []
    for i in range(1, n - 1):
        t = model.NewBoolVar(f"tussen_{i}")
        model.AddBoolAnd([bezet[i].Not(), eerder[i], later[i]]).OnlyEnforceIf(t)
        model.AddBoolOr([bezet[i], eerder[i].Not(), later[i].Not()]).OnlyEnforceIf(t.Not())
        straf.append(t)
    return straf
