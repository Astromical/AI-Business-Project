"""Roosteren met OR-Tools CP-SAT. Kent geen SQLite en geen Streamlit."""

from __future__ import annotations

import os
import threading
from collections import defaultdict
from dataclasses import replace
from functools import partial
from typing import Callable

from ortools.sat.python import cp_model

from src import constraints
from src.lokalen import h5_geldt, wijs_lokalen_toe
from src.models import (
    STANDAARD_GEWICHTEN,
    Afwezigheid,
    Instellingen,
    ProbleemData,
    Resultaat,
    Status,
    Toewijzing,
    met_afwezigheid,
)

STATUS_VERTALING: dict[int, Status] = {
    cp_model.OPTIMAL: "optimaal",
    cp_model.FEASIBLE: "geldig",
    cp_model.INFEASIBLE: "onoplosbaar",
    cp_model.MODEL_INVALID: "onoplosbaar",
    cp_model.UNKNOWN: "geen_oplossing_binnen_tijd",
}

ZachteRegel = Callable[
    [cp_model.CpModel, constraints.Variabelen, ProbleemData], list[cp_model.IntVar]
]

# De gebouwde zachte regels: regelnaam -> functie die de strafvariabelen geeft.
ZACHTE_REGELS: dict[str, ZachteRegel] = {
    "Z1": constraints.z1_tussenuren_klassen,
    "Z2": constraints.z2_tussenuren_leraren,
    "Z3": constraints.z3_vak_een_keer_per_dag,
    "Z4": constraints.z4_zware_vakken_laatste_uur,  # bouw_model geeft de zware vakken mee
}

# Alle zachte regels uit (ook de nog niet gebouwde), bijvoorbeeld voor fase 1.
GEEN_ZACHTE_REGELS: dict[str, int] = dict.fromkeys(STANDAARD_GEWICHTEN, 0)


class Voortgang:
    """De stand van een lopende berekening, te lezen en te stoppen vanuit een andere draad.

    fase is "zoeken", "verbeteren" of "uitleg"; beste_straf is de beste strafscore tot
    nu toe in fase 2. stop() laat de solver stoppen met het beste rooster tot dan toe.
    """

    def __init__(self) -> None:
        self.fase = "zoeken"
        self.beste_straf: int | None = None
        self.gestopt = False
        self._solver: cp_model.CpSolver | None = None
        self._slot = threading.Lock()

    def stop(self) -> None:
        """Vraag de berekening te stoppen; mag vaker en vanuit elke draad."""
        with self._slot:
            self.gestopt = True
            if self._solver is not None:
                self._solver.stop_search()

    def _koppel(self, solver: cp_model.CpSolver | None) -> None:
        """Onthoud welke solver nu rekent (None: geen)."""
        with self._slot:
            self._solver = solver


class _Meeluisteraar(cp_model.CpSolverSolutionCallback):
    """Meldt elke nieuwe oplossing aan de voortgang en stopt als dat gevraagd is."""

    def __init__(self, voortgang: Voortgang) -> None:
        super().__init__()
        self._voortgang = voortgang

    def on_solution_callback(self) -> None:
        """Bij elke betere oplossing: strafscore doorgeven."""
        if self._voortgang.fase == "verbeteren":
            self._voortgang.beste_straf = round(self.ObjectiveValue())
        if self._voortgang.gestopt:
            self.StopSearch()


def actieve_regels(gewichten: dict[str, int]) -> list[str]:
    """De gebouwde zachte regels met een gewicht groter dan 0; een ontbrekende regel telt als 0."""
    return [regel for regel in ZACHTE_REGELS if gewichten.get(regel, 0) > 0]


def maak_variabelen(model: cp_model.CpModel, data: ProbleemData) -> constraints.Variabelen:
    """Maak x[l, s]: 1 als lesuur l in tijdslot s staat. Lokalen volgen na het oplossen."""
    return {
        (l, slot.id): model.NewBoolVar(f"x_{l}_{slot.id}")
        for l in range(len(data.lesuren))
        for slot in data.tijdslots
    }


def harde_regels(
    model: cp_model.CpModel,
    x: constraints.Variabelen,
    data: ProbleemData,
    uitgeschakeld: frozenset[str] = frozenset(),
    schakelaars: constraints.Schakelaars | None = None,
    symmetrie: bool = False,
) -> None:
    """Voeg de harde regels toe; schakelaars maken H5, H6 en H7 per type of leraar uitschakelbaar.

    Met symmetrie staan de lesuren van één les in weekvolgorde. Dat voegt geen
    variabelen toe, dus een hint past op het model met en zonder.
    """
    constraints.h1_elk_lesuur_een_keer(model, x, data)
    constraints.h2_h5_genoeg_lokalen(model, x, data, uitgeschakeld, schakelaars)
    constraints.h3_leraar_een_les(model, x, data)
    constraints.h4_klas_een_les(model, x, data)
    constraints.h8_lokaalcapaciteit(model, x, data, uitgeschakeld)
    constraints.h9_blokuren(model, x, data)
    if symmetrie:
        constraints.volgorde_binnen_les(model, x, data)
    if "H6" not in uitgeschakeld:
        constraints.h6_onbeschikbaarheid(model, x, data, schakelaars)
    if "H7" not in uitgeschakeld:
        constraints.h7_max_uren_per_dag(model, x, data, schakelaars)


def bouw_model(
    data: ProbleemData,
    uitgeschakeld: frozenset[str] = frozenset(),
    gewichten: dict[str, int] | None = None,
    zware_vakken: tuple[str, ...] = (),
    symmetrie: bool = False,
) -> tuple[cp_model.CpModel, constraints.Variabelen, dict[str, cp_model.LinearExpr]]:
    """Bouw het CP-SAT-model.

    'uitgeschakeld' zet harde regels uit (bijvoorbeeld {"H6"}) voor tests. Zachte
    regels met gewicht 0 worden niet gebouwd. Geeft ook de strafsom per zachte regel.
    """
    model = cp_model.CpModel()
    x = maak_variabelen(model, data)
    harde_regels(model, x, data, uitgeschakeld, symmetrie=symmetrie)
    gewichten = Instellingen().gewichten if gewichten is None else gewichten
    regels = dict(ZACHTE_REGELS)
    regels["Z4"] = partial(constraints.z4_zware_vakken_laatste_uur, zware_vakken=zware_vakken)
    straffen: dict[str, cp_model.LinearExpr] = {
        regel: sum(regels[regel](model, x, data)) for regel in actieve_regels(gewichten)
    }
    model.Minimize(sum(gewichten[regel] * som for regel, som in straffen.items()))
    return model, x, straffen


MINIMUM_FASE_2_S = 1.0  # fase 2 krijgt minstens zoveel tijd om het startrooster te laden
Oplossing = dict[tuple[int, int], int]


def aantal_werkers(instellingen: Instellingen) -> int:
    """Het aantal zoekdraden: uit de instellingen, of anders het aantal processorkernen."""
    return instellingen.num_workers if instellingen.num_workers > 0 else (os.cpu_count() or 8)


def nieuwe_solver(tijdslimiet_s: float, instellingen: Instellingen | None = None) -> cp_model.CpSolver:
    """Een CP-SAT-solver met tijdslimiet, vaste seed, aantal werkers en lichte presolve."""
    instellingen = instellingen or Instellingen()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(tijdslimiet_s, 0.0)
    solver.parameters.num_workers = aantal_werkers(instellingen)
    solver.parameters.random_seed = instellingen.random_seed
    _lichte_presolve(solver)
    return solver


def _los_op(
    model: cp_model.CpModel,
    tijdslimiet_s: float,
    instellingen: Instellingen | None = None,
    voortgang: Voortgang | None = None,
) -> tuple[cp_model.CpSolver, Status]:
    """Draai CP-SAT met een tijdslimiet en vertaal de status.

    Met een voortgang ziet de gebruiker de strafscore lopen en kan hij stoppen; is er
    al gestopt, dan krijgt de solver geen tijd meer.
    """
    gestopt = voortgang is not None and voortgang.gestopt
    solver = nieuwe_solver(0.0 if gestopt else tijdslimiet_s, instellingen)
    if voortgang is None:
        code = solver.Solve(model)
    else:
        voortgang._koppel(solver)
        try:
            code = solver.Solve(model, _Meeluisteraar(voortgang))
        finally:
            voortgang._koppel(None)
    return solver, STATUS_VERTALING.get(code, "geen_oplossing_binnen_tijd")


def _lichte_presolve(solver: cp_model.CpSolver) -> None:
    """Beperk de voorbereiding (presolve) van CP-SAT.

    Op de grote variant ging de volledige presolve met alle tijd van fase 2 lopen,
    zodat er nooit gezocht werd. Licht: fase 1 daar 8 s in plaats van 23 s, en fase 2
    vindt binnen 30 s weer betere roosters.
    """
    solver.parameters.max_presolve_iterations = 1
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.symmetry_level = 0


def _waarden(solver: cp_model.CpSolver, x: constraints.Variabelen) -> Oplossing:
    """De waarde van elke x-variabele in de gevonden oplossing."""
    return {sleutel: solver.Value(var) for sleutel, var in x.items()}


def _toewijzingen(
    data: ProbleemData,
    oplossing: Oplossing,
    uitgeschakeld: frozenset[str] = frozenset(),
    voorkeur: dict[tuple[str, int], str] | None = None,
) -> tuple[Toewijzing, ...]:
    """Zet een oplossing (waarde per x-variabele) om in toewijzingen, met lokalen erbij."""
    plaatsing = {l: s for (l, s), waarde in oplossing.items() if waarde}
    return wijs_lokalen_toe(data, plaatsing, uitgeschakeld, voorkeur)


def _gestopt(voortgang: Voortgang | None) -> bool:
    """Heeft de gebruiker gevraagd te stoppen?"""
    return voortgang is not None and voortgang.gestopt


def solve(
    data: ProbleemData,
    instellingen: Instellingen | None = None,
    uitgeschakeld: frozenset[str] = frozenset(),
    voortgang: Voortgang | None = None,
) -> Resultaat:
    """Los het rooster op in twee fases en geef status, toewijzingen, tijden en strafpunten.

    Fase 1 zoekt alleen een rooster dat alle harde regels haalt, tot hoogstens
    max_tijd_zoeken_s. Lukt dat, dan begint de tijdslimiet te lopen: fase 2 verbetert
    dat rooster voor de zachte regels, met het rooster uit fase 1 als startpunt. Zo is
    er altijd een werkbaar rooster zodra er één gevonden is.
    """
    instellingen = instellingen or Instellingen()
    model, x, _ = bouw_model(
        data, uitgeschakeld, GEEN_ZACHTE_REGELS, symmetrie=instellingen.symmetrie_breken
    )
    solver, status = _los_op(model, instellingen.max_tijd_zoeken_s, instellingen, voortgang)
    tijd = solver.WallTime()
    if status not in ("optimaal", "geldig"):
        return Resultaat(status, (), tijd, tijd_zoeken_s=tijd, gestopt=_gestopt(voortgang))
    oplossing = _waarden(solver, x)
    if not actieve_regels(instellingen.gewichten):  # niets te verbeteren
        toewijzingen = _toewijzingen(data, oplossing, uitgeschakeld)
        return Resultaat(status, toewijzingen, tijd, tijd_zoeken_s=tijd, gestopt=_gestopt(voortgang))
    limiet = max(instellingen.tijdslimiet_s, MINIMUM_FASE_2_S)
    return _verbeter(data, uitgeschakeld, instellingen, oplossing, limiet, tijd, voortgang)


def _verbeter(
    data: ProbleemData,
    uitgeschakeld: frozenset[str],
    instellingen: Instellingen,
    start: Oplossing,
    tijdslimiet_s: float,
    tijd_fase_1: float,
    voortgang: Voortgang | None = None,
) -> Resultaat:
    """Fase 2: minimaliseer de strafpunten, vertrekkend van het rooster uit fase 1.

    Het startrooster gaat als volledige hint mee (ook de hulpvariabelen van de zachte
    regels), zodat CP-SAT het meteen als oplossing heeft en alleen nog moet verbeteren.
    """
    gewichten, zware_vakken = instellingen.gewichten, instellingen.zware_vakken
    waarden, straf, tijd_doorrekenen = _vast_rooster(
        data, uitgeschakeld, gewichten, start, zware_vakken
    )
    if voortgang is not None:
        voortgang.fase = "verbeteren"
        voortgang.beste_straf = None if straf is None else sum(straf.values())
    model, x, straffen = bouw_model(
        data, uitgeschakeld, gewichten, zware_vakken, instellingen.symmetrie_breken
    )
    if waarden is not None:  # niet doorgerekend: fase 2 zoekt dan zonder hint
        _zet_hint(model, waarden)
    solver, status = _los_op(model, tijdslimiet_s, instellingen, voortgang)
    tijd = tijd_fase_1 + tijd_doorrekenen + solver.WallTime()
    gestopt = _gestopt(voortgang)
    if status in ("optimaal", "geldig"):
        toewijzingen = _toewijzingen(data, _waarden(solver, x), uitgeschakeld)
        straf = {regel: gewichten[regel] * solver.Value(som) for regel, som in straffen.items()}
        return Resultaat(
            status, toewijzingen, tijd, sum(straf.values()), straf, tijd_fase_1, gestopt
        )
    # Fase 2 kwam niet tot een rooster: houd het startrooster met zijn eigen straf
    # (None als die niet uit te rekenen was; het rooster zelf blijft geldig).
    strafscore = sum(straf.values()) if straf is not None else None
    toewijzingen = _toewijzingen(data, start, uitgeschakeld)
    return Resultaat("geldig", toewijzingen, tijd, strafscore, straf or {}, tijd_fase_1, gestopt)


def verbeter_verder(
    data: ProbleemData,
    toewijzingen: tuple[Toewijzing, ...],
    instellingen: Instellingen | None = None,
    uitgeschakeld: frozenset[str] = frozenset(),
    voortgang: Voortgang | None = None,
) -> Resultaat:
    """Reken verder vanaf een bestaand geldig rooster; het resultaat is nooit slechter.

    Het bestaande rooster is de veilige versie: de solver vertrekt ervan en krijgt de
    volledige tijdslimiet. Vindt hij niets beters, dan blijft het rooster ongewijzigd.
    """
    instellingen = instellingen or Instellingen()
    gewichten, zware_vakken = instellingen.gewichten, instellingen.zware_vakken
    start = _als_oplossing(data, toewijzingen, uitgeschakeld)
    straf = waardeer(data, uitgeschakeld, gewichten, start, zware_vakken)
    if straf is None:  # straf van het rooster onbekend: niets om mee te vergelijken
        veilig = Resultaat("geldig", tuple(toewijzingen), 0.0, None, {})
    else:
        veilig = Resultaat("geldig", tuple(toewijzingen), 0.0, sum(straf.values()), straf)
    if veilig.strafscore == 0:  # niets meer te verbeteren
        return replace(veilig, status="optimaal")
    limiet = max(instellingen.tijdslimiet_s, MINIMUM_FASE_2_S)
    nieuw = _verbeter(data, uitgeschakeld, instellingen, start, limiet, 0.0, voortgang)
    if _slechter(nieuw.strafscore, veilig.strafscore):  # vangnet: nooit slechter teruggeven
        return replace(veilig, oplostijd_s=nieuw.oplostijd_s, gestopt=nieuw.gestopt)
    return nieuw


def _slechter(nieuw: int | None, veilig: int | None) -> bool:
    """Is de nieuwe strafscore slechter dan de veilige? Onbekend (None) telt als slechter."""
    if veilig is None:
        return False
    return nieuw is None or nieuw > veilig


def _als_oplossing(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], uitgeschakeld: frozenset[str]
) -> Oplossing:
    """Zet toewijzingen om in een waarde per x-variabele; fout als het rooster niet past.

    De lesuren van één les zijn uitwisselbaar, dus ze krijgen hun tijdslots opnieuw in
    weekvolgorde (volgnummer 1 het vroegst); zo past het rooster ook als symmetrie_breken aan staat.
    """
    slots_per_les = _slots_per_les(data, toewijzingen, uitgeschakeld)
    plaats = constraints.slotvolgorde(data)
    uren_per_les: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for l, uur in enumerate(data.lesuren):
        uren_per_les[uur.les_id].append((uur.volgnummer, l))
    oplossing = dict.fromkeys(maak_variabelen(cp_model.CpModel(), data).keys(), 0)
    for les_id, uren in uren_per_les.items():
        slots = sorted(slots_per_les.get(les_id, []), key=plaats.__getitem__)
        if len(slots) != len(uren):
            raise ValueError("Het rooster plant niet elk lesuur precies één keer in.")
        for (_, l), s in zip(sorted(uren), slots):
            oplossing[l, s] = 1
    return oplossing


def _slots_per_les(
    data: ProbleemData, toewijzingen: tuple[Toewijzing, ...], uitgeschakeld: frozenset[str]
) -> dict[str, list[int]]:
    """De tijdslots per les; fout als een les, tijdslot of lokaal niet (meer) past."""
    slots: dict[str, list[int]] = defaultdict(list)
    for t in toewijzingen:
        les = data.les_per_id.get(t.lesuur.les_id)
        lokaal = data.lokaal_per_id.get(t.lokaal_id)
        past = les is not None and lokaal is not None and t.tijdslot_id in data.tijdslot_per_id
        if past and h5_geldt(les.lokaaltype, uitgeschakeld):
            past = lokaal.type == les.lokaaltype
        if not past:
            raise ValueError("Het rooster past niet bij de huidige gegevens.")
        slots[les.id].append(t.tijdslot_id)
    return slots


WAARDEER_LIMIET_S = 30.0  # een volledig vastgezet rooster is normaal in milliseconden doorgerekend


def waardeer(
    data: ProbleemData,
    uitgeschakeld: frozenset[str],
    gewichten: dict[str, int],
    oplossing: Oplossing,
    zware_vakken: tuple[str, ...] = (),
) -> dict[str, int] | None:
    """De strafpunten per zachte regel van een vast rooster (alle x vastgezet).

    Geeft None als de strafpunten niet uit te rekenen zijn; het rooster blijft dan bruikbaar.
    """
    return _vast_rooster(data, uitgeschakeld, gewichten, oplossing, zware_vakken)[1]


def _vast_rooster(
    data: ProbleemData,
    uitgeschakeld: frozenset[str],
    gewichten: dict[str, int],
    oplossing: Oplossing,
    zware_vakken: tuple[str, ...],
) -> tuple[list[int] | None, dict[str, int] | None, float]:
    """Reken een vast rooster door: waarde van elke modelvariabele, straf per regel en tijd.

    Omdat bouw_model altijd dezelfde variabelen in dezelfde volgorde maakt, passen de
    waarden als volledige hint op een nieuw model met dezelfde gewichten. Lukt het
    doorrekenen niet binnen WAARDEER_LIMIET_S, dan zijn waarden en straf None.
    """
    model, x, straffen = bouw_model(data, uitgeschakeld, gewichten, zware_vakken)
    for sleutel, var in x.items():
        model.Add(var == oplossing[sleutel])
    solver = nieuwe_solver(WAARDEER_LIMIET_S)
    if solver.Solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None, solver.WallTime()
    straf = {regel: gewichten[regel] * solver.Value(som) for regel, som in straffen.items()}
    return list(solver.ResponseProto().solution), straf, solver.WallTime()


def _zet_hint(model: cp_model.CpModel, waarden: list[int]) -> None:
    """Geef elke variabele van het model een startwaarde (een volledige hint)."""
    proto = model.Proto()
    if len(waarden) != len(proto.variables):
        raise RuntimeError("De hint past niet op het model.")
    proto.solution_hint.vars.extend(range(len(waarden)))
    proto.solution_hint.values.extend(waarden)


def _aantal_wijzigingen(
    model: cp_model.CpModel, x: constraints.Variabelen, data: ProbleemData, oud: tuple[Toewijzing, ...]
) -> cp_model.LinearExpr:
    """Het aantal oude (les, tijdslot)-plaatsen dat niet meer gebruikt wordt.

    Per les en niet per lesuur: de lesuren van één les zijn uitwisselbaar, dus het
    telt niet als een wijziging als twee lesuren van dezelfde les van nummer ruilen.
    """
    per_les: dict[str, list[int]] = defaultdict(list)
    for l, uur in enumerate(data.lesuren):
        per_les[uur.les_id].append(l)
    plekken = {(t.lesuur.les_id, t.tijdslot_id) for t in oud}
    blijft = []
    for les_id, s in sorted(plekken):
        if s in data.tijdslot_per_id and les_id in per_les:
            houd = model.NewBoolVar(f"houd_{les_id}_{s}")
            model.Add(sum(x[l, s] for l in per_les[les_id]) >= houd)
            blijft.append(houd)
    return len(plekken) - sum(blijft)


def herplan(
    data: ProbleemData,
    oud: tuple[Toewijzing, ...],
    afwezig: Afwezigheid,
    instellingen: Instellingen | None = None,
    voortgang: Voortgang | None = None,
) -> Resultaat:
    """Pas een rooster aan voor afwezige leraren, met zo weinig mogelijk wijzigingen.

    Lexicografisch, in twee stappen binnen de tijdslimiet: eerst zo weinig mogelijk
    verplaatste lesuren (de afwezige uren tellen als onbeschikbaar), daarna, met dat
    aantal als bovengrens, zo weinig mogelijk strafpunten. Lokalen blijven waar het kan.
    """
    instellingen = instellingen or Instellingen()
    data_afw = met_afwezigheid(data, afwezig)
    limiet = max(instellingen.tijdslimiet_s, MINIMUM_FASE_2_S)
    model, x, _ = bouw_model(data_afw, gewichten=GEEN_ZACHTE_REGELS)
    wijzigingen = _aantal_wijzigingen(model, x, data_afw, oud)
    model.Minimize(wijzigingen)
    _hint_rooster(model, x, data_afw, oud)
    solver, status = _los_op(model, limiet / 2, instellingen, voortgang)
    tijd = solver.WallTime()
    if status not in ("optimaal", "geldig"):
        return Resultaat(status, (), tijd, tijd_zoeken_s=tijd, gestopt=_gestopt(voortgang))
    minimum, eerste = round(solver.ObjectiveValue()), _waarden(solver, x)
    return _herplan_stap_2(data_afw, oud, instellingen, minimum, eerste, limiet / 2, tijd, voortgang)


def _herplan_stap_2(
    data: ProbleemData,
    oud: tuple[Toewijzing, ...],
    instellingen: Instellingen,
    maximum: int,
    start: Oplossing,
    tijdslimiet_s: float,
    tijd: float,
    voortgang: Voortgang | None,
) -> Resultaat:
    """Stap 2: hoogstens 'maximum' wijzigingen, zo weinig mogelijk strafpunten."""
    gewichten, voorkeur = instellingen.gewichten, {(t.lesuur.les_id, t.tijdslot_id): t.lokaal_id for t in oud}
    model, x, straffen = bouw_model(data, gewichten=gewichten, zware_vakken=instellingen.zware_vakken)
    model.Add(_aantal_wijzigingen(model, x, data, oud) <= maximum)
    for sleutel, var in x.items():
        model.AddHint(var, start[sleutel])
    if voortgang is not None:
        voortgang.fase = "verbeteren"
    solver, status = _los_op(model, tijdslimiet_s, instellingen, voortgang)
    tijd += solver.WallTime()
    if status in ("optimaal", "geldig"):
        straf = {regel: gewichten[regel] * solver.Value(som) for regel, som in straffen.items()}
        oplossing = _waarden(solver, x)
    else:  # stap 2 vond niets binnen de tijd: houd de oplossing van stap 1
        straf, oplossing, status = {}, start, "geldig"
    toewijzingen = _toewijzingen(data, oplossing, voorkeur=voorkeur)
    score = sum(straf.values()) if straf or not actieve_regels(gewichten) else None
    return Resultaat(status, toewijzingen, tijd, score, straf, 0.0, _gestopt(voortgang))


def _hint_rooster(
    model: cp_model.CpModel, x: constraints.Variabelen, data: ProbleemData, oud: tuple[Toewijzing, ...]
) -> None:
    """Geef het oude rooster als hint (alleen de x-variabelen; ook als het nu niet meer past)."""
    plekken = {(t.lesuur.les_id, t.lesuur.volgnummer): t.tijdslot_id for t in oud}
    for (l, s), var in x.items():
        uur = data.lesuren[l]
        model.AddHint(var, int(plekken.get((uur.les_id, uur.volgnummer)) == s))
