"""SQLite-verbinding, schema en tijdslots."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.models import DAGEN, Gebruiker, Lesuur, Toewijzing

SCHEMA_PAD = Path(__file__).resolve().parent.parent / "data" / "schema.sql"

# Vaste tabelnamen, in een volgorde die foreign keys respecteert bij wissen.
TABELLEN_WISVOLGORDE: tuple[str, ...] = (
    "ingepland",
    "onbeschikbaar",
    "les",
    "leraar",
    "lokaal",
    "tijdslot",
)


def verbind(pad: str | Path) -> sqlite3.Connection:
    """Open een verbinding met foreign keys aan."""
    con = sqlite3.connect(pad)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def maak_schema(con: sqlite3.Connection) -> None:
    """Maak de tabellen uit data/schema.sql (bestaande tabellen blijven staan)."""
    con.executescript(SCHEMA_PAD.read_text(encoding="utf-8"))
    with con:  # de rol beheerder bestaat niet meer: oude accounts worden roostermaker
        con.execute("UPDATE gebruiker SET rol = 'roostermaker' WHERE rol = 'beheerder'")


def _tijdslot_rijen(uren_per_dag: dict[str, int]) -> list[tuple[str, int]]:
    """De (dag, uur)-paren voor maak_tijdslots; weigert onbekende dagen."""
    onbekend = set(uren_per_dag) - set(DAGEN)
    if onbekend:
        raise ValueError(f"Onbekende dag(en): {', '.join(sorted(onbekend))}")
    return [(dag, uur) for dag in DAGEN for uur in range(1, uren_per_dag.get(dag, 0) + 1)]


def maak_tijdslots(con: sqlite3.Connection, uren_per_dag: dict[str, int]) -> None:
    """Maak tijdslots per dag, bijvoorbeeld {"maandag": 6, "woensdag": 4}."""
    rijen = _tijdslot_rijen(uren_per_dag)
    with con:
        con.executemany("INSERT INTO tijdslot (dag, uur) VALUES (?, ?)", rijen)


def maak_tijdslots_opnieuw(con: sqlite3.Connection, uren_per_dag: dict[str, int]) -> None:
    """Vervang alle tijdslots; dit wist ook de onbeschikbaarheid en het bewaarde rooster."""
    rijen = _tijdslot_rijen(uren_per_dag)
    with con:  # één transactie
        con.execute("DELETE FROM ingepland")  # geen cascade op tijdslot, dus eerst leegmaken
        con.execute("DELETE FROM tijdslot")  # onbeschikbaar verdwijnt via ON DELETE CASCADE
        con.executemany("INSERT INTO tijdslot (dag, uur) VALUES (?, ?)", rijen)


def leeg_database(con: sqlite3.Connection) -> None:
    """Verwijder alle rijen uit alle tabellen; het schema blijft bestaan."""
    with con:
        for tabel in TABELLEN_WISVOLGORDE:
            con.execute(f"DELETE FROM {tabel}")  # vaste namen, geen invoer


def bewaar_rooster(con: sqlite3.Connection, toewijzingen: tuple[Toewijzing, ...]) -> None:
    """Vervang het bewaarde rooster (tabel ingepland) door deze toewijzingen."""
    rijen = [
        (t.lesuur.les_id, t.lesuur.volgnummer, t.tijdslot_id, t.lokaal_id)
        for t in toewijzingen
    ]
    with con:  # één transactie: bij een fout blijft het oude rooster staan
        con.execute("DELETE FROM ingepland")
        con.executemany("INSERT INTO ingepland VALUES (?, ?, ?, ?)", rijen)


def laad_rooster(con: sqlite3.Connection) -> tuple[Toewijzing, ...]:
    """Lees het bewaarde rooster; leeg als er geen is."""
    rijen = con.execute(
        """SELECT i.les_id, i.volgnummer, l.vak, l.klas, l.leraar_id, l.lokaaltype,
                  i.tijdslot_id, i.lokaal_id
           FROM ingepland i JOIN les l ON l.id = i.les_id
           ORDER BY i.les_id, i.volgnummer"""
    )
    return tuple(Toewijzing(Lesuur(*rij[:6]), rij[6], rij[7]) for rij in rijen)


class OpslaanFout(Exception):
    """Opslaan is mislukt; de tekst is bedoeld voor de gebruiker."""


# tabel -> (kolommen, sleutelkolommen). Alleen deze vaste namen komen in SQL.
TABEL_CONFIG: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "leraar": (("id", "naam", "max_uren_per_dag"), ("id",)),
    "lokaal": (("id", "naam", "type"), ("id",)),
    "onbeschikbaar": (("leraar_id", "tijdslot_id"), ("leraar_id", "tijdslot_id")),
    "les": (
        ("id", "vak", "klas", "leraar_id", "aantal_per_week", "lokaaltype"),
        ("id",),
    ),
}
LEESBARE_TABELLEN: dict[str, tuple[str, ...]] = {
    **{naam: kolommen for naam, (kolommen, _) in TABEL_CONFIG.items()},
    "tijdslot": ("id", "dag", "uur"),
}


def lees_tabel(con: sqlite3.Connection, tabel: str) -> list[dict]:
    """Alle rijen van een tabel uit de vaste lijst, als lijst van dicts."""
    if tabel not in LEESBARE_TABELLEN:
        raise ValueError(f"Onbekende tabel: {tabel}")
    kolommen = LEESBARE_TABELLEN[tabel]
    sql = f"SELECT {', '.join(kolommen)} FROM {tabel} ORDER BY {', '.join(kolommen)}"
    return [dict(zip(kolommen, rij)) for rij in con.execute(sql)]


def _vertaal(fout: sqlite3.IntegrityError) -> str:
    """Zet een SQLite-fout om in een begrijpelijke Nederlandse melding."""
    tekst = str(fout)
    if "FOREIGN KEY" in tekst:
        return (
            "Een verwijzing klopt niet: kies een bestaande leraar of een bestaand tijdslot, "
            "of verwijder eerst de lessen die nog naar dit item verwijzen."
        )
    if "CHECK" in tekst:
        return "Een waarde is niet toegestaan: controleer het type, de aantallen en het maximum per dag."
    if "NOT NULL" in tekst:
        return "Vul alle verplichte velden in."
    if "UNIQUE" in tekst or "PRIMARY KEY" in tekst:
        return "Deze waarde bestaat al."
    return f"De wijziging is niet toegestaan: {tekst}"


def _upsert_sql(tabel: str) -> str:
    """De upsert voor een tabel uit de vaste lijst."""
    kolommen, sleutel = TABEL_CONFIG[tabel]
    overig = [k for k in kolommen if k not in sleutel]
    actie = (
        "DO UPDATE SET " + ", ".join(f"{k} = excluded.{k}" for k in overig)
        if overig
        else "DO NOTHING"
    )
    return (
        f"INSERT INTO {tabel} ({', '.join(kolommen)}) VALUES ({', '.join('?' * len(kolommen))}) "
        f"ON CONFLICT ({', '.join(sleutel)}) {actie}"
    )


def _waarden(tabel: str, rijen: list[dict]) -> list[tuple]:
    """De rijen als tuples in de kolomvolgorde van de tabel."""
    return [tuple(rij[k] for k in TABEL_CONFIG[tabel][0]) for rij in rijen]


def sla_tabel_op(
    con: sqlite3.Connection,
    tabel: str,
    rijen: list[dict],
    verwijder: list[tuple],
) -> None:
    """Schrijf wijzigingen van één tabel weg in één transactie.

    Verwijdert alleen de opgegeven sleutels en schrijft de rijen met een upsert; de
    hele tabel wordt nooit gewist, zodat ON DELETE CASCADE niets ongemerkt meeneemt.
    Een verwijderd lokaal verdwijnt ook uit het bewaarde rooster; die lesuren staan dan
    niet meer ingepland en de app meldt dat het rooster niet meer past.
    Bij een fout wordt niets opgeslagen.
    """
    if tabel not in TABEL_CONFIG:
        raise ValueError(f"Onbekende tabel: {tabel}")
    sleutel = TABEL_CONFIG[tabel][1]
    wis = f"DELETE FROM {tabel} WHERE " + " AND ".join(f"{k} = ?" for k in sleutel)
    try:
        with con:
            if tabel == "lokaal":  # ingepland heeft geen cascade op lokaal
                con.executemany("DELETE FROM ingepland WHERE lokaal_id = ?", verwijder)
            con.executemany(wis, verwijder)
            con.executemany(_upsert_sql(tabel), _waarden(tabel, rijen))
    except sqlite3.IntegrityError as fout:
        raise OpslaanFout(_vertaal(fout)) from fout


def voeg_basis_toe(
    con: sqlite3.Connection, tijdslots: list[tuple[str, int]], lokalen: list[dict]
) -> None:
    """Voeg ontbrekende tijdslots en lokalen toe; bestaande rijen blijven ongemoeid."""
    with con:
        con.executemany("INSERT OR IGNORE INTO tijdslot (dag, uur) VALUES (?, ?)", tijdslots)
        con.executemany(_upsert_sql("lokaal"), _waarden("lokaal", lokalen))


def importeer_lessen(
    con: sqlite3.Connection, leraren: list[dict], lessen: list[dict]
) -> None:
    """Schrijf nieuwe leraren en lessen in één transactie: alles of niets."""
    try:
        with con:
            con.executemany(_upsert_sql("leraar"), _waarden("leraar", leraren))
            con.executemany(_upsert_sql("les"), _waarden("les", lessen))
    except sqlite3.IntegrityError as fout:
        raise OpslaanFout(_vertaal(fout)) from fout


def heeft_gebruikers(con: sqlite3.Connection) -> bool:
    """Bestaat er minstens één account?"""
    return con.execute("SELECT EXISTS (SELECT 1 FROM gebruiker)").fetchone()[0] == 1


def lees_gebruiker(con: sqlite3.Connection, naam: str) -> Gebruiker | None:
    """Het account met deze naam, zonder wachtwoord."""
    rij = con.execute(
        "SELECT naam, rol, leraar_id FROM gebruiker WHERE naam = ?", (naam,)
    ).fetchone()
    return Gebruiker(*rij) if rij else None


def lees_gebruikers(con: sqlite3.Connection) -> list[Gebruiker]:
    """Alle accounts, zonder wachtwoorden."""
    rijen = con.execute("SELECT naam, rol, leraar_id FROM gebruiker ORDER BY naam")
    return [Gebruiker(*rij) for rij in rijen]


def lees_wachtwoord_hash(con: sqlite3.Connection, naam: str) -> str | None:
    """De opgeslagen wachtwoordhash, of None als het account niet bestaat."""
    rij = con.execute("SELECT wachtwoord_hash FROM gebruiker WHERE naam = ?", (naam,)).fetchone()
    return rij[0] if rij else None


def voeg_gebruiker_toe(
    con: sqlite3.Connection, gebruiker: Gebruiker, wachtwoord_hash: str
) -> None:
    """Maak een account aan."""
    try:
        with con:
            con.execute(
                "INSERT INTO gebruiker (naam, wachtwoord_hash, rol, leraar_id) VALUES (?, ?, ?, ?)",
                (gebruiker.naam, wachtwoord_hash, gebruiker.rol, gebruiker.leraar_id),
            )
    except sqlite3.IntegrityError as fout:
        raise OpslaanFout(_vertaal(fout)) from fout


def voeg_gebruikers_toe(con: sqlite3.Connection, nieuw: list[tuple[Gebruiker, str]]) -> None:
    """Maak meerdere accounts aan in één transactie: allemaal of geen."""
    try:
        with con:
            con.executemany(
                "INSERT INTO gebruiker (naam, wachtwoord_hash, rol, leraar_id) VALUES (?, ?, ?, ?)",
                [(g.naam, wachtwoord_hash, g.rol, g.leraar_id) for g, wachtwoord_hash in nieuw],
            )
    except sqlite3.IntegrityError as fout:
        raise OpslaanFout(_vertaal(fout)) from fout


def voeg_eerste_roostermaker_toe(con: sqlite3.Connection, naam: str, wachtwoord_hash: str) -> bool:
    """Maak in één opdracht de roostermaker aan, alleen als er nog geen enkel account is."""
    with con:
        cursor = con.execute(
            """INSERT INTO gebruiker (naam, wachtwoord_hash, rol)
               SELECT ?, ?, 'roostermaker' WHERE NOT EXISTS (SELECT 1 FROM gebruiker)""",
            (naam, wachtwoord_hash),
        )
    return cursor.rowcount == 1


_NOG_EEN_ROOSTERMAKER = "EXISTS (SELECT 1 FROM gebruiker AS g WHERE g.rol = 'roostermaker' AND g.naam <> ?)"


def wijzig_gebruiker(con: sqlite3.Connection, gebruiker: Gebruiker) -> None:
    """Wijzig rol en leraar; de laatste roostermaker blijft roostermaker."""
    try:
        with con:
            cursor = con.execute(
                f"""UPDATE gebruiker SET rol = ?, leraar_id = ?
                    WHERE naam = ? AND (rol <> 'roostermaker' OR ? = 'roostermaker' OR {_NOG_EEN_ROOSTERMAKER})""",
                (gebruiker.rol, gebruiker.leraar_id, gebruiker.naam, gebruiker.rol, gebruiker.naam),
            )
    except sqlite3.IntegrityError as fout:
        raise OpslaanFout(_vertaal(fout)) from fout
    if cursor.rowcount == 0:
        raise OpslaanFout("Er moet minstens één roostermaker overblijven.")


def wijzig_wachtwoord(con: sqlite3.Connection, naam: str, wachtwoord_hash: str) -> None:
    """Vervang het wachtwoord van een account."""
    with con:
        con.execute("UPDATE gebruiker SET wachtwoord_hash = ? WHERE naam = ?", (wachtwoord_hash, naam))


def verwijder_gebruiker(con: sqlite3.Connection, naam: str) -> None:
    """Verwijder een account; de laatste roostermaker blijft staan."""
    with con:
        cursor = con.execute(
            f"DELETE FROM gebruiker WHERE naam = ? AND (rol <> 'roostermaker' OR {_NOG_EEN_ROOSTERMAKER})",
            (naam, naam),
        )
    if cursor.rowcount == 0:
        raise OpslaanFout("Er moet minstens één roostermaker overblijven.")
