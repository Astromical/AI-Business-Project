# Plan: prototype schoolrooster-solver (OR-Tools)

Laatst bijgewerkt: 16 oktober 2026

Dit plan verdeelt het prototype in 16 kleine stappen: elke stap is één aparte Claude Code-sessie die één taak afwerkt, test, vastlegt en dan stopt.

## Doel en scope

Na 3 sprints van een week staat er een Streamlit-app die een geldig weekrooster berekent voor een middelbare school, met de gegevens in een SQLite-database en OR-Tools CP-SAT als solver.

**Het prototype kan:**

- lessen, leraren, lokalen, tijdslots en onbeschikbaarheid bewaren in `rooster.db`;
- die gegevens laden en valideren, met Nederlandse foutmeldingen;
- een rooster berekenen zonder dubbele boekingen (harde regels H1–H7);
- voorkeuren meewegen, zoals weinig tussenuren (zachte regels);
- het rooster tonen per klas, leraar en lokaal, opslaan in de database en exporteren naar CSV.

**Demo-schaal:** 6 klassen, 10 leraren, 7 lokalen (5 regulier, 1 lab, 1 gym), 30 tijdslots (5 dagen × 6 uur) en 144 lesuren. Oplostijd onder 30 seconden.

**Buiten scope:** inloggen, een serverdatabase, herplannen na ziekte, keuzevakken over meerdere klassen, lessen van twee uur, lokaalcapaciteit en klasgrootte, en echte schooldata.

## Werkwijze: één sessie per stap

Elke stap (S1.1, S1.2, …) is één nieuwe Claude Code-sessie. De agent voert alleen die ene stap uit, test hem, legt hem vast en stopt. Zo blijft elke sessie klein, controleerbaar en makkelijk terug te draaien.

**Drie bestanden houden het geheugen tussen sessies bij:**

| Bestand | Inhoud | Wie past het aan |
| --- | --- | --- |
| `CLAUDE.md` | Vaste werkafspraken (zie onderaan dit plan) | Het team |
| `docs/PLAN.md` | Dit plan | Het team; de agent past alleen de kolom "Status" in het sessieoverzicht aan |
| `docs/STATUS.md` | Per afgewerkte sessie: datum, wat er gebouwd is, testresultaat, open punten | De agent, aan het einde van elke sessie |

**Startprompt om in elke nieuwe sessie te plakken** (vervang alleen de stapcode):

```text
Voer sessie S1.3 uit volgens docs/PLAN.md.
Lees eerst CLAUDE.md, docs/PLAN.md (alleen sessie S1.3 en de algemene secties) en docs/STATUS.md.
Werk alleen deze ene sessie af. Begin niet aan een volgende sessie, ook niet als er tijd over is.
Sluit af met het afsluitprotocol en stop dan.
```

**Begin van elke sessie, door de agent:**

1. Lees `CLAUDE.md`, de eigen sessie in `docs/PLAN.md` en `docs/STATUS.md`.
2. Controleer dat de vorige sessie afgerond is: `pytest` slaagt en `docs/STATUS.md` vermeldt die sessie. Zo niet: meld het en stop, zonder iets te bouwen. Bij S1.1 vervalt deze stap, want er is nog geen vorige sessie.
3. Vat in drie tot vijf regels samen wat je gaat doen, en begin dan.

**Afsluitprotocol van elke sessie, door de agent:**

1. Draai `pytest` en de controles uit "Klaar als" van de sessie.
2. Voeg een blok toe aan `docs/STATUS.md`: sessiecode, datum, gemaakte of gewijzigde bestanden, testresultaat, open punten.
3. Zet de status van de sessie in het sessieoverzicht van `docs/PLAN.md` op "Klaar".
4. Maak één commit met als boodschap `<sessiecode>: <korte omschrijving>`, bijvoorbeeld `S1.3: SQLite-schema en voorbeelddata`.
5. Meld kort wat klaar is en wat de volgende sessie is. Stop.

**Als een stap niet lukt:** de agent commit niets dat tests breekt, schrijft het probleem in `docs/STATUS.md` onder "Geblokkeerd" en stopt. Het team beslist daarna.

## Tech stack en projectstructuur

Alles is Python 3.11 of hoger; de enige externe solver is OR-Tools.

| Onderdeel | Pakket |
| --- | --- |
| Solver | `ortools` (CP-SAT) |
| Database | `sqlite3` (standaard in Python) |
| Data | `pandas` |
| Interface | `streamlit` |
| Weergave | `pandas` Styler (vraagt `jinja2`) |
| Tests | `pytest` |

De hoofdmap van de git-repo (`project_ai_for_business/`) is de projectmap; `schoolrooster/` hieronder staat voor die map.

```text
schoolrooster/
  CLAUDE.md
  README.md
  requirements.txt
  config.toml              # tijdslimiet en gewichten zachte regels
  docs/
    PLAN.md
    STATUS.md
  data/
    schema.sql             # CREATE TABLE-statements
    rooster.db             # niet in git (.gitignore)
  src/
    __init__.py
    models.py              # dataclasses
    db.py                  # verbinding, schema, tijdslots, opslaan
    seed.py                # voorbeelddata
    loader.py              # database -> ProbleemData + validatie
    constraints.py         # harde en zachte regels, elk een functie
    solver.py              # solve(data, instellingen) -> Resultaat
    checker.py             # onafhankelijke controle van een rooster
    views.py               # rooster -> tabellen per klas/leraar/lokaal
    cli.py                 # python -m src.cli seed|solve|check
  app.py                   # Streamlit-startpagina
  pages/
    1_Gegevens.py          # beheerpagina (S3.5)
    2_Rooster.py           # rooster maken en bekijken
  tests/
    conftest.py
    test_*.py
```

**Grenzen tussen modules:** `solver.py` en `checker.py` kennen geen SQLite en geen Streamlit; ze werken alleen op `ProbleemData`. Alleen `db.py`, `seed.py` en `loader.py` spreken de database aan. De pagina's roepen `loader`, `solver`, `checker` en `views` aan, nooit OR-Tools zelf.

## Datamodel

De database bevat vijf invoertabellen en één uitvoertabel; foreign keys en checks weigeren foute invoer al bij het opslaan.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE tijdslot (
    id   INTEGER PRIMARY KEY,
    dag  TEXT    NOT NULL CHECK (dag IN ('maandag','dinsdag','woensdag','donderdag','vrijdag')),
    uur  INTEGER NOT NULL CHECK (uur BETWEEN 1 AND 8),
    UNIQUE (dag, uur)
);

CREATE TABLE lokaal (
    id    TEXT  PRIMARY KEY,
    naam  TEXT  NOT NULL,
    type  TEXT  NOT NULL CHECK (type IN ('regulier','lab','gym'))
);

CREATE TABLE leraar (
    id                TEXT    PRIMARY KEY,
    naam              TEXT    NOT NULL,
    max_uren_per_dag  INTEGER NOT NULL CHECK (max_uren_per_dag BETWEEN 1 AND 8)
);

CREATE TABLE onbeschikbaar (
    leraar_id    TEXT    NOT NULL REFERENCES leraar(id) ON DELETE CASCADE,
    tijdslot_id  INTEGER NOT NULL REFERENCES tijdslot(id) ON DELETE CASCADE,
    PRIMARY KEY (leraar_id, tijdslot_id)
);

CREATE TABLE les (
    id               TEXT    PRIMARY KEY,
    vak              TEXT    NOT NULL,
    klas             TEXT    NOT NULL,
    leraar_id        TEXT    NOT NULL REFERENCES leraar(id),
    aantal_per_week  INTEGER NOT NULL CHECK (aantal_per_week > 0),
    lokaaltype       TEXT    NOT NULL CHECK (lokaaltype IN ('regulier','lab','gym'))
);

CREATE TABLE ingepland (
    les_id       TEXT    NOT NULL REFERENCES les(id) ON DELETE CASCADE,
    volgnummer   INTEGER NOT NULL,
    tijdslot_id  INTEGER NOT NULL REFERENCES tijdslot(id),
    lokaal_id    TEXT    NOT NULL REFERENCES lokaal(id),
    PRIMARY KEY (les_id, volgnummer)
);
```

**Domeinklassen in `models.py`** (frozen dataclasses, los van SQLite):

| Klasse | Velden |
| --- | --- |
| `Tijdslot` | `id, dag, uur` |
| `Lokaal` | `id, naam, type` |
| `Leraar` | `id, naam, max_uren_per_dag, onbeschikbaar: frozenset[int]` |
| `Les` | `id, vak, klas, leraar_id, aantal_per_week, lokaaltype` |
| `Lesuur` | `les_id, volgnummer, vak, klas, leraar_id, lokaaltype` (één per in te plannen uur) |
| `ProbleemData` | `tijdslots, lokalen, leraren, lessen, lesuren` |
| `Toewijzing` | `lesuur, tijdslot_id, lokaal_id` |
| `Resultaat` | `status, toewijzingen, oplostijd_s, strafscore, straf_per_regel` |
| `Melding` | `ernst` (`fout` of `waarschuwing`), `tekst` (uitvoer van `valideer`, S1.4) |
| `Schending` | `regel, lesuren, tekst` (uitvoer van `controleer`, S2.3) |
| `Instellingen` | `tijdslimiet_s, gewichten: dict[str, int]` (S3.2; tot dan geeft `solve` standaardwaarden mee) |

Gebruik tuples in plaats van lijsten in de frozen dataclasses, zodat ze echt onveranderlijk zijn.

De loader zet elke `les` met `aantal_per_week = 4` om in vier `Lesuur`-objecten met volgnummer 1 tot 4. De solver plant lesuren, geen vakken.

## Constraints

Harde regels mogen nooit geschonden worden; zachte regels geven strafpunten die de solver minimaliseert. Elke regel is een aparte functie in `constraints.py` en heeft eigen tests.

**Basisvariabele:** `x[l, s, r]` is een booleaanse variabele die 1 is als lesuur `l` in tijdslot `s` en lokaal `r` staat. In S1.5 bestaan er variabelen voor alle lokalen. In S2.1 komt de functie `toegelaten_lokalen(lesuur, data)`, waarna er alleen nog variabelen voor lokalen van het juiste type bestaan: dat is H5, en het houdt het model klein.

**Optionele versnelling:** lokalen van hetzelfde type zijn onderling inwisselbaar. Je kunt dus ook `x[l, s]` gebruiken met "per tijdslot en lokaaltype hoogstens het aantal lokalen van dat type", en de lokalen achteraf toewijzen. Dat geeft veel minder symmetrie. Doe dit alleen als de oplostijd een probleem wordt.

| Nr | Harde regel | Sessie |
| --- | --- | --- |
| H1 | Elk lesuur staat precies één keer ingepland | S1.5 |
| H2 | Een lokaal heeft per tijdslot hoogstens één les | S1.5 |
| H3 | Een leraar geeft per tijdslot hoogstens één les | S1.5 |
| H4 | Een klas heeft per tijdslot hoogstens één les | S1.5 |
| H5 | Een les gebruikt alleen een lokaal van het gevraagde type | S2.1 |
| H6 | Een leraar staat niet ingepland op een onbeschikbaar tijdslot | S2.1 |
| H7 | Een leraar geeft per dag niet meer dan zijn maximum | S2.2 |

| Nr | Zachte regel | Gewicht | Sessie |
| --- | --- | --- | --- |
| Z1 | Geen tussenuren voor klassen | 10 | S3.1 |
| Z2 | Geen tussenuren voor leraren | 5 | S4.2 |
| Z3 | Hetzelfde vak voor een klas niet twee keer op één dag | 5 | S4.3 |
| Z4 | Zware vakken liever niet in het laatste uur | 2 | S4.4 |

**Modelleertip voor tussenuren (Z1):** maak per klas, dag en uur een hulpvariabele `bezet[k, d, u]`. Een tussenuur op uur `u` betekent: `u` is vrij, terwijl er eerder en later die dag nog een les is. Modelleer dat met hulpvariabelen `eerder_bezet` en `later_bezet` per uur, en tel `vrij AND eerder_bezet AND later_bezet` als strafpunt. Koppel elke hulpvariabele en strafvariabele in beide richtingen (volledige reïficatie, met `AddBoolAnd` en `AddBoolOr` plus `OnlyEnforceIf`), niet alleen met een ondergrens. Anders kan een strafvariabele bij een niet-optimale oplossing op 1 staan zonder echt tussenuur, en dan telt de checker iets anders dan de solver.

## Sessieoverzicht

21 sessies over 4 sprints, samen 58 story points; werk ze strikt in deze volgorde af en zet de status hier bij na elke sessie.

| Sessie | Taak | Wat | Prio | SP | Status |
| --- | --- | --- | --- | --- | --- |
| S1.1 | T1 | Projectopzet | Must | 1 | Klaar |
| S1.2 | T2, T5 | Domeinmodel en testopzet | Must | 3 | Klaar |
| S1.3 | T3 | SQLite-schema en voorbeelddata | Must | 2 | Klaar |
| S1.4 | T4 | Loader met validatie | Must | 3 | Klaar |
| S1.5 | T6 | Solver met harde regels H1–H4 | Must | 5 | Klaar |
| S2.1 | T7 | Lokaaltype en beschikbaarheid (H5, H6) | Must | 3 | Klaar |
| S2.2 | T8 | Maximum uren per dag (H7) | Should | 2 | Klaar |
| S2.3 | T9 | Onafhankelijke roostercontrole | Must | 3 | Klaar |
| S2.4 | T10 | Streamlit: laden en oplossen | Must | 3 | Klaar |
| S2.5 | T11 | Roosterweergave per klas, leraar, lokaal | Must | 3 | Klaar |
| S3.1 | T12 | Zachte regel: geen tussenuren klassen | Should | 5 | Klaar |
| S3.2 | T13 | Instellingen: tijdslimiet en gewichten | Should | 2 | Klaar |
| S3.3 | T14 | Rooster opslaan en exporteren | Should | 1 | Klaar |
| S3.4 | T15 | Uitleg bij onoplosbaar rooster | Should | 5 | Klaar |
| S3.5 | T19 | Beheerpagina voor gegevens | Should | 3 | Klaar |
| S3.6 | T18 | Documentatie en demo | Must | 2 | Klaar |
| S4.1 | T16 | Zachte regels generiek maken | Could | 2 | Klaar |
| S4.2 | T16 | Geen tussenuren leraren (Z2) | Could | 3 | Klaar |
| S4.3 | T16 | Vak niet twee keer per dag (Z3) | Could | 2 | Klaar |
| S4.4 | T16 | Zware vakken niet in het laatste uur (Z4) | Could | 3 | Klaar |
| S4.5 | T16 | Meting, documentatie en demo | Could | 2 | Klaar |

Sprint 1 telt 14 SP, sprint 2 14 SP, sprint 3 18 SP en sprint 4 12 SP. Sprint 3 is dus te vol: valt er tijd tekort, dan schuiven eerst S3.4 en daarna S3.2 naar Could. S3.6 doet het team altijd.

T19 (beheerpagina) is nieuw ten opzichte van de presentatie en moet daar nog bij. T16 (Z2–Z4) staat sinds 30 oktober 2026 in sprint 4. T17 komt hier niet voor; controleer dat dit klopt met de backlog in de presentatie.

## Sprint 1: de solver werkt in de terminal

Sprintdoel: `python -m src.cli solve` maakt met de voorbeelddata een geldig rooster zonder dubbele boekingen. Demo aan het einde van de week: die opdracht live draaien en het resultaat tonen.

### S1.1 · Projectopzet (T1, 1 SP)

**Doel:** een lege, werkende projectbasis waarop alle volgende sessies bouwen.

**Doen:**

1. Maak de mappen uit "Tech stack en projectstructuur", met een lege `__init__.py` in `src/`. Maak de andere bestanden pas in de sessie die ze nodig heeft.
2. Verplaats `plan.md` uit de hoofdmap naar `docs/PLAN.md` met `git mv`.
3. Schrijf `requirements.txt` met `ortools`, `pandas`, `jinja2`, `streamlit`, `pytest`, zonder vaste versies behalve een minimum voor `ortools`.
4. Schrijf `.gitignore` (venv, `__pycache__`, `data/rooster.db`, `.pytest_cache`).
5. Zet `CLAUDE.md` in de hoofdmap met de inhoud uit de sectie "CLAUDE.md om te kopiëren".
6. Maak `docs/STATUS.md` met een kop per sprint en een sectie "Geblokkeerd".
7. Schrijf een korte `README.md`: installatie (`python -m venv .venv`, `pip install -r requirements.txt`) en hoe je tests draait.
8. Voeg `tests/test_smoke.py` toe dat `ortools`, `pandas` en `streamlit` importeert.

**Klaar als:**

- [ ] `pip install -r requirements.txt` werkt in een nieuwe virtuele omgeving
- [ ] `pytest` slaagt met de smoke-test
- [ ] `docs/PLAN.md` bestaat en `plan.md` staat niet meer in de hoofdmap
- [ ] `docs/STATUS.md` vermeldt S1.1

**Niet doen:** geen domeinklassen, database of solvercode.

### S1.2 · Domeinmodel en testopzet (T2 + T5, 3 SP)

**Doel:** alle domeinklassen bestaan en zijn getest; er zijn herbruikbare test-fixtures.

**Doen:**

1. Schrijf in `src/models.py` de dataclasses uit "Datamodel", frozen en met type hints.
2. Voeg aan `ProbleemData` handige opzoekingen toe: `klassen` (gesorteerde set), `dagen`, `uren_per_dag`, en dictionaries van id naar object.
3. Maak in `tests/conftest.py` een fixture `klein_probleem`: 2 klassen, 2 leraren, 2 lokalen, 2 dagen × 3 uur, ongeveer 8 lesuren. Bouw die rechtstreeks met dataclasses, zonder database.
4. Maak een fixture `onmogelijk_probleem`: meer lesuren voor één klas dan er tijdslots zijn.
5. Schrijf `tests/test_models.py` met tests voor de opzoekingen.

**Klaar als:**

- [ ] `pytest` slaagt
- [ ] beide fixtures zijn bruikbaar vanuit elke testmodule

**Niet doen:** geen SQLite, nog geen solver.

### S1.3 · SQLite-schema en voorbeelddata (T3, 2 SP)

**Doel:** één commando maakt een `rooster.db` met schema en realistische voorbeelddata.

**Doen:**

1. Zet het schema uit "Datamodel" in `data/schema.sql`.
2. Schrijf in `src/db.py`: `verbind(pad)` (zet `PRAGMA foreign_keys = ON`), `maak_schema(con)`, `maak_tijdslots(con, uren_per_dag: dict[str, int])` (bijvoorbeeld `{"maandag": 6, ..., "woensdag": 4}`, zodat een kortere woensdag kan) en `leeg_database(con)`.
3. Schrijf in `src/seed.py` een functie `seed(con, variant="voorbeeld")` met de voorbeelddata: 6 klassen (1A, 1B, 2A, 2B, 3A, 3B), 10 leraren, 7 lokalen (5 regulier, 1 lab, 1 gym), 30 tijdslots en lessen goed voor 24 lesuren per klas (144 in totaal). Geef 2 leraren enkele onbeschikbare momenten.
4. Controleer zelf dat de data oplosbaar kan zijn: per leraar niet meer uren dan tijdslots min onbeschikbaarheid, en per lokaaltype (ook regulier) hoogstens ongeveer 85% van lokalen × tijdslots bezet.
5. Voeg een tweede variant `"onmogelijk"` toe: dezelfde data, maar met één duidelijke oorzaak waardoor geen rooster bestaat (bijvoorbeeld een klas met 32 lesuren). Die gebruik je in de demo.
6. Voeg `python -m src.cli seed [--pad data/rooster.db] [--variant voorbeeld|onmogelijk]` toe in `src/cli.py`.
7. Test: schema aanmaken in een tijdelijke database, seed draaien, aantallen controleren, en een les met een onbekende leraar geeft een `IntegrityError`.

**Klaar als:**

- [ ] `python -m src.cli seed` maakt `data/rooster.db` met 144 lesuren in totaal
- [ ] foute invoer wordt door SQLite geweigerd (getest)
- [ ] `pytest` slaagt

**Niet doen:** geen loader of solver; de voorbeelddata niet als echte schooldata voorstellen.

### S1.4 · Loader met validatie (T4, 3 SP)

**Doel:** de database wordt ingelezen als `ProbleemData`, en problemen worden vooraf gemeld in begrijpelijk Nederlands.

**Doen:**

1. Schrijf `laad_probleem(con) -> ProbleemData` in `src/loader.py`, met de omzetting van lessen naar lesuren.
2. Schrijf `valideer(data) -> list[Melding]`, met per melding een ernst (`fout` of `waarschuwing`) en een tekst. Controleer minstens:
    - een klas heeft meer lesuren dan er tijdslots zijn;
    - een leraar heeft meer lesuren dan beschikbare tijdslots;
    - er is geen lokaal van een gevraagd type;
    - per lokaaltype zijn er meer lesuren dan lokalen × tijdslots;
    - er zijn geen tijdslots of geen lessen.
3. Test elke controle met een eigen kleine dataset die precies die fout bevat.

**Klaar als:**

- [ ] de voorbeelddata laadt zonder fouten
- [ ] elke controle heeft een test die de melding afdwingt
- [ ] `pytest` slaagt

**Niet doen:** geen solver; geen controles die alleen de solver kan doen.

### S1.5 · Solver met harde regels H1–H4 (T6, 5 SP)

**Doel:** de kern van het project: OR-Tools maakt een rooster zonder dubbele boekingen.

**Doen:**

1. Bouw in `src/solver.py` de functie `solve(data, tijdslimiet_s=30) -> Resultaat` met de variabele `x[l, s, r]` voor alle lokalen (het lokaaltype komt pas in S2.1).
2. Zet H1 tot en met H4 elk in een eigen functie in `src/constraints.py` die `(model, x, data)` krijgt.
3. Vertaal de solverstatus naar `optimaal`, `geldig`, `onoplosbaar` of `geen_oplossing_binnen_tijd`.
4. Voeg `python -m src.cli solve` toe: laadt de database, valideert, lost op en drukt het rooster per klas af.
5. Test: `klein_probleem` geeft een geldig rooster, `onmogelijk_probleem` geeft `onoplosbaar`, en een test per regel controleert de uitkomst zelf (geen enkele dubbele boeking).

**Klaar als:**

- [ ] de voorbeelddata geeft binnen 30 seconden een geldig rooster
- [ ] `pytest` slaagt
- [ ] de oplostijd voor de voorbeelddata staat in `docs/STATUS.md`

**Niet doen:** nog geen lokaaltype-, beschikbaarheids- of zachte regels; geen Streamlit.

**Sprintreview 1 (team):** draai `python -m src.cli seed` en `solve` live, toon `docs/STATUS.md` en noteer de werkelijk gehaalde story points als velocity.

## Sprint 2: alle harde regels en een app in de browser

Sprintdoel: in Streamlit klik je op "Rooster berekenen" en zie je een rooster dat alle harde regels H1–H7 respecteert, bevestigd door een onafhankelijke controle. Demo: de app live tonen.

### S2.1 · Lokaaltype en beschikbaarheid (T7, 3 SP)

**Doel:** lessen staan in het juiste soort lokaal en leraren worden niet ingepland wanneer ze niet kunnen.

**Doen:**

1. H5: schrijf in `constraints.py` de functie `toegelaten_lokalen(lesuur, data)` en laat `solver.py` voor elk lesuur alleen variabelen maken voor die lokalen. Zo blijft de regel zichtbaar en kan de test hem uitschakelen.
2. H6: zet in `constraints.py` alle `x[l, s, r]` op 0 waarvoor de leraar van `l` onbeschikbaar is op `s`.
3. Test met een klein geval: een leraar die maar op 1 tijdslot kan, en een lables die maar in 1 lokaal past. Controleer dat de solver precies die plaatsen kiest.

**Klaar als:**

- [ ] beide regels hebben een eigen test die faalt als je de regel weghaalt
- [ ] de voorbeelddata blijft binnen 30 seconden oplosbaar
- [ ] `pytest` slaagt

**Niet doen:** geen maximum per dag; geen interface.

### S2.2 · Maximum uren per dag (T8, 2 SP)

**Doel:** geen enkele leraar geeft op een dag meer uren dan zijn `max_uren_per_dag`.

**Doen:**

1. H7: tel per leraar en per dag de som van zijn `x`-variabelen en beperk die tot het maximum.
2. Voeg aan `valideer` een fout toe als een leraar meer uren per week heeft dan `max_uren_per_dag × dagen` (dan is er zeker geen rooster mogelijk).
3. Test met een leraar met maximum 1 en 3 lesuren over 3 dagen: het rooster moet ze over 3 dagen spreiden.

**Klaar als:**

- [ ] de test voor H7 slaagt en faalt zonder de regel
- [ ] `pytest` slaagt

**Niet doen:** geen zachte regels.

### S2.3 · Onafhankelijke roostercontrole (T9, 3 SP)

**Doel:** een tweede, eenvoudige controle die een rooster nakijkt zonder OR-Tools. Zo test je de solver echt.

**Doen:**

1. Schrijf in `src/checker.py` `controleer(data, toewijzingen) -> list[Schending]`, met gewone Python-lussen en tellers, geen OR-Tools.
2. Controleer H1 tot en met H7 elk apart; een `Schending` bevat de regel, de betrokken lesuren en een Nederlandse tekst.
3. Voeg `python -m src.cli check` toe: lost op en controleert.
4. Test de checker met handgemaakte foute roosters (één per regel), en voeg een test toe: elk rooster van de solver op `klein_probleem` en de voorbeelddata geeft 0 schendingen.

**Klaar als:**

- [ ] de checker vindt elke opzettelijk ingebouwde fout
- [ ] het solverrooster voor de voorbeelddata geeft 0 schendingen
- [ ] `pytest` slaagt

**Niet doen:** de checker niet laten steunen op code uit `solver.py` of `constraints.py`.

### S2.4 · Streamlit: laden en oplossen (T10, 3 SP)

**Doel:** een werkende app met zijbalk en een pagina om een rooster te berekenen.

**Doen:**

1. Maak `app.py` (titel en korte uitleg) en `pages/2_Rooster.py`.
2. Zijbalk: databasepad, knoppen "Voorbeelddata laden" en "Onmogelijk voorbeeld laden" (roepen `seed` aan met de juiste variant) en knop "Database leegmaken" met bevestiging.
3. Op de roosterpagina: toon de aantallen (klassen, leraren, lokalen, tijdslots, lesuren) en de meldingen van `valideer`. Bij een fout is de knop "Rooster berekenen" uitgeschakeld.
4. "Rooster berekenen" roept `solve` en daarna `controleer` aan, toont een spinner tijdens het rekenen en daarna status, oplostijd en aantal schendingen.
5. Bewaar het resultaat in `st.session_state`, zodat het niet verdwijnt bij een klik.
6. Test de logica die niet in Streamlit zit; de pagina zelf controleer je met `streamlit run app.py`.

**Klaar als:**

- [ ] `streamlit run app.py` start zonder fouten
- [ ] voorbeelddata laden en een rooster berekenen werkt in de browser
- [ ] `pytest` slaagt

**Niet doen:** nog geen roostertabel; geen beheerpagina.

### S2.5 · Roosterweergave (T11, 3 SP)

**Doel:** het rooster is leesbaar per klas, per leraar en per lokaal.

**Doen:**

1. Schrijf in `src/views.py` `rooster_tabel(data, toewijzingen, soort, id) -> pandas.DataFrame`: rijen zijn uren, kolommen zijn dagen, cellen tonen vak, leraar of klas, en lokaal.
2. Geef elk vak een vaste kleur via pandas Styler, met donkere tekst op lichte achtergrond.
3. Op de roosterpagina: tabs "Per klas", "Per leraar", "Per lokaal", elk met een keuzelijst.
4. Test `rooster_tabel` met `klein_probleem`: juiste vorm en juiste inhoud in een paar cellen.

**Klaar als:**

- [ ] de drie weergaven werken in de app voor de voorbeelddata
- [ ] `pytest` slaagt

**Niet doen:** geen export; geen instellingen.

**Sprintreview 2 (team):** demo in de browser, de checker tonen met 0 schendingen, velocity noteren en beslissen wat in sprint 3 past.

## Sprint 3: een beter rooster en de eindpresentatie

Sprintdoel: het rooster heeft zo weinig mogelijk tussenuren, is in te stellen, op te slaan en uit te leggen, en de demo voor de project-eigenaar staat klaar. Deze sprint is te vol (18 SP): S3.4 en daarna S3.2 vallen eerst weg.

### S3.1 · Geen tussenuren voor klassen (T12, 5 SP)

**Doel:** de solver zoekt het geldige rooster met zo weinig mogelijk tussenuren per klas.

**Doen:**

1. Zet Z1 in `constraints.py` volgens de modelleertip bij "Constraints". De functie geeft een lijst strafvariabelen terug.
2. Laat `solve` de som van gewicht × strafvariabelen minimaliseren, en vul `strafscore` en `straf_per_regel` in het `Resultaat`.
3. Tel in de checker het aantal tussenuren per klas, los van de solver.
4. Doe eerst een nulmeting: tel met de checker de tussenuren in het rooster zonder Z1 (gewicht 0) en zet dat cijfer in `docs/STATUS.md`.
5. Test: een klein geval waarbij het beste rooster 0 tussenuren heeft; en de voorbeelddata heeft met Z1 minder tussenuren dan de nulmeting (zet ook dat cijfer in `docs/STATUS.md`).
6. Toon in de app de strafscore en het aantal tussenuren.

**Klaar als:**

- [ ] de checker telt hetzelfde aantal tussenuren als de solver rapporteert
- [ ] de voorbeelddata blijft binnen 30 seconden een geldig rooster geven
- [ ] `pytest` slaagt

**Niet doen:** Z2 tot en met Z4 niet bouwen; ze zijn Could.

### S3.2 · Instellingen (T13, 2 SP)

**Doel:** de gebruiker kan tijdslimiet en gewichten kiezen.

**Doen:**

1. Maak `config.toml` met `tijdslimiet_s = 30` en een sectie `[gewichten]`.
2. Lees het in met `tomllib` en geef een `Instellingen`-object door aan `solve`.
3. In de app: schuifregelaars in de zijbalk die de standaardwaarden uit `config.toml` overnemen.
4. Test: gewicht 0 voor Z1 schakelt de regel uit; een tijdslimiet van 1 seconde wordt gerespecteerd.

**Klaar als:**

- [ ] wijzigingen in de zijbalk veranderen het resultaat zichtbaar
- [ ] `pytest` slaagt

**Niet doen:** de instellingen niet in de database bewaren.

### S3.3 · Rooster opslaan en exporteren (T14, 1 SP)

**Doel:** een berekend rooster blijft bewaard en is te downloaden.

**Doen:**

1. Schrijf in `db.py` `bewaar_rooster(con, toewijzingen)` (vervangt de inhoud van `ingepland`) en `laad_rooster(con)`.
2. In de app: knop "Opslaan in database", en bij het openen een bewaard rooster tonen als dat er is.
3. Knop "Download CSV" met kolommen `klas, dag, uur, vak, leraar, lokaal`.
4. Test: opslaan en weer laden geeft exact dezelfde toewijzingen.

**Klaar als:**

- [ ] een rooster overleeft het herstarten van de app
- [ ] `pytest` slaagt

### S3.4 · Uitleg bij een onoplosbaar rooster (T15, 5 SP)

**Doel:** als er geen rooster mogelijk is, ziet de gebruiker waarom.

**Doen:**

1. Toon eerst de meldingen van `valideer`; die vangen de meeste oorzaken.
2. Is er toch geen oplossing: geef elke versoepelbare regel per leraar (H6, H7) en per lokaaltype (H5) een eigen booleaanse "schakelaar" en gebruik CP-SAT-assumpties (`AddAssumptions` en daarna `SufficientAssumptionsForInfeasibility`) om te vinden welke schakelaars samen het probleem veroorzaken. Eenvoudiger alternatief: los opnieuw op met telkens één regel voor één leraar of lokaaltype versoepeld.
3. Zet de uitkomst om in een concrete tekst, bijvoorbeeld "Zonder de onbeschikbaarheid van Claes lukt het wel. Kijk of Claes op maandag uur 1 toch kan." Noem alleen een tijdslot als dat ook echt uit de analyse blijkt.
4. Test met drie opzettelijk onmogelijke datasets, elk met een andere oorzaak. Elke dataset moet zonder fouten door `valideer` komen en toch onoplosbaar zijn; anders test je de validatie in plaats van de uitleg.

**Klaar als:**

- [ ] elke testdataset geeft de juiste oorzaak
- [ ] de app crasht nooit op een onmogelijk probleem
- [ ] `pytest` slaagt

**Niet doen:** geen automatische aanpassing van de data.

### S3.5 · Beheerpagina voor gegevens (T19, 3 SP)

**Doel:** de gebruiker vult leraren, lokalen, onbeschikbaarheid en lessen in via de app, zonder SQLite te openen.

**Doen:**

1. Maak `pages/1_Gegevens.py` met bovenaan dagen en uren per dag en de knop "Tijdslots aanmaken". Zijn er al tijdslots, dan waarschuw je eerst: opnieuw aanmaken wist de onbeschikbaarheid en het bewaarde rooster (`ingepland` eerst leegmaken).
2. Tabs voor Leraren, Lokalen, Onbeschikbaar en Lessen, elk met `st.data_editor(num_rows="dynamic")`.
3. "Opslaan" schrijft één tabel weg in een transactie: nieuwe en gewijzigde rijen met een upsert (`INSERT ... ON CONFLICT DO UPDATE`), en alleen de rijen die de gebruiker echt verwijderd heeft met `DELETE`. Verwijder en herschrijf nooit de hele tabel: door `ON DELETE CASCADE` verdwijnen dan ongemerkt de onbeschikbaarheid of het bewaarde rooster. Een `IntegrityError` wordt een begrijpelijke Nederlandse melding, en er wordt niets half opgeslagen.
4. Gebruik een vaste lijst toegestane tabelnamen; plak nooit invoer van de gebruiker in SQL.
5. Test de opslagfunctie: geldige wijziging, onbekende leraar geweigerd, rollback na een fout, en een leraar wijzigen laat diens onbeschikbaarheid staan.

**Klaar als:**

- [ ] vanuit een lege database kun je alles invullen en een rooster berekenen
- [ ] foute invoer geeft een melding en laat de database ongewijzigd
- [ ] `pytest` slaagt

### S3.6 · Documentatie en demo (T18, 2 SP)

**Doel:** het project is over te dragen en de demo loopt zonder verrassingen.

**Doen:**

1. Werk `README.md` bij: installatie, opstarten, de twee pagina's, de regels H1–H7 en Z1, en bekende beperkingen.
2. Schrijf `docs/DEMO.md`: een stappenplan van 5 minuten voor de presentatie (database leegmaken, voorbeelddata laden, rooster berekenen, weergaven tonen, onmogelijk voorbeeld laden en de melding tonen).
3. Noteer de oplostijd en strafscore voor de voorbeelddata in de README.
4. Loop de Definition of Done hieronder volledig na en vat het resultaat samen in `docs/STATUS.md`.

**Klaar als:**

- [ ] iemand buiten het team kan het project installeren en starten met alleen de README
- [ ] de demo uit `docs/DEMO.md` werkt van begin tot einde
- [ ] `pytest` slaagt

**Sprintreview 3 (team):** eindpresentatie aan de project-eigenaar, gevolgd door een retrospective.

## Sprint 4: meer zachte regels

Sprintdoel: naast Z1 houdt de solver ook rekening met tussenuren van leraren (Z2), spreiding van vakken over de week (Z3) en zware vakken aan het einde van de dag (Z4). Elke regel staat aan of uit met een eigen gewicht in de zijbalk, en de checker telt elke regel na zonder OR-Tools.

**Teamkeuzes vóór S4.1:**

- [x] Welke vakken zijn "zwaar" voor Z4? Voorstel: wiskunde, nederlands, frans en natuurkunde. De lijst komt in `config.toml`, niet in de database. *Beslist op 30 oktober 2026: alleen wiskunde.*
- [x] Kloppen de standaardgewichten Z1 = 10, Z2 = 5, Z3 = 5 en Z4 = 2? *Beslist op 30 oktober 2026: ja, ongewijzigd.*

**Werkwijze:** S4.2 tot en met S4.4 volgen hetzelfde patroon als Z1 in S3.1: een functie in `constraints.py` die strafvariabelen teruggeeft, een telfunctie in `checker.py`, een schuifregelaar in de zijbalk en een cijfer op de pagina Rooster. De test "de checker telt hetzelfde als de solver" is voor elke regel verplicht: daarom moet elke strafvariabele in beide richtingen gekoppeld zijn (zie de modelleertip bij "Constraints").

**Let op bij bestaande tests:** een regel die niet in `gewichten` staat, telt als gewicht 0. Tests die nu `{"Z1": 0}` of `{"Z1": 10}` meegeven, blijven dus alleen Z1 testen. Tests die de standaardgewichten gebruiken (`Instellingen()`) krijgen vanaf S4.2 ook Z2–Z4 mee; past zo'n test niet meer, geef dan expliciet `{"Z1": ...}` mee in plaats van de verwachting te verzwakken, en noteer het in `docs/STATUS.md`.

### S4.1 · Zachte regels generiek maken (T16, 2 SP)

**Doel:** de code rond zachte regels werkt voor Z1–Z4, zodat elke volgende sessie alleen haar eigen regel toevoegt.

**Doen:**

1. Vervang in `solver.py` de vaste verwijzingen naar `"Z1"` door een tabel `ZACHTE_REGELS: dict[str, Callable]` van regelnaam naar constraintfunctie. `bouw_model` bouwt elke regel met gewicht > 0.
2. Fase 2 draait zodra minstens één zachte regel een gewicht > 0 heeft (nu kijkt `solve` alleen naar Z1).
3. `GEEN_ZACHTE_REGELS` zet alle zachte regels op 0, en staat op één plaats: `uitleg.py` gebruikt die uit `solver.py` in plaats van een eigen kopie.
4. Maak in `checker.py` een functie `tel_straf(data, toewijzingen, gewichten) -> dict[str, int]` die per regel gewicht × aantal geeft, voorlopig alleen voor Z1.
5. Test: met alleen Z1 aan is het resultaat gelijk aan dat van vóór deze sessie; met alle gewichten op 0 draait fase 2 niet; `tel_straf` geeft dezelfde `straf_per_regel` als de solver.

**Klaar als:**

- [ ] er staat buiten `ZACHTE_REGELS` en de zijbalk geen `"Z1"` meer hard in `solver.py`, `service.py` en `uitleg.py`
- [ ] `pytest` slaagt, zonder dat bestaande tests aangepast moeten worden

**Niet doen:** nog geen nieuwe regel bouwen; niets aan het datamodel veranderen.

### S4.2 · Geen tussenuren voor leraren (T16, Z2, 3 SP)

**Doel:** de solver vermijdt ook tussenuren van leraren.

**Doen:**

1. Bouw `z2_tussenuren_leraren` in `constraints.py`. Hergebruik `_tussenuren_van_dag`: maak een gedeelde hulpfunctie die `bezet` per groep en dag opbouwt, zodat Z1 (per klas) en Z2 (per leraar) dezelfde code gebruiken.
2. Voeg Z2 toe aan `ZACHTE_REGELS`.
3. Tel in `checker.py` de tussenuren per leraar (`tel_tussenuren_leraren`) en neem Z2 op in `tel_straf`.
4. Zijbalk: schuifregelaar "Gewicht tussenuren leraren (Z2)", 0–20, standaard uit `config.toml`. Pagina Rooster: toon het aantal tussenuren van leraren naast dat van klassen.
5. Meet op de voorbeelddata het aantal tussenuren van leraren met en zonder Z2 en zet beide cijfers in `docs/STATUS.md`.
6. Test: een klein geval waarbij een leraar met Z2 0 tussenuren krijgt en zonder Z2 niet gegarandeerd; de checker telt evenveel als de solver.

**Klaar als:**

- [ ] de checker telt hetzelfde aantal tussenuren van leraren als de solver rapporteert
- [ ] de voorbeelddata met Z1 en Z2 aan geeft binnen 30 seconden verbetertijd een geldig rooster
- [ ] `pytest` slaagt

**Niet doen:** geen maximum op het aantal tussenuren als harde regel.

### S4.3 · Vak niet twee keer op één dag (T16, Z3, 2 SP)

**Doel:** een klas krijgt een vak liefst hoogstens één keer per dag.

**Doen:**

1. Bouw `z3_vak_een_keer_per_dag` in `constraints.py`: per klas, vak en dag is `n` het aantal ingeplande lesuren, en de straf is `max(0, n − 1)`. Gebruik een `IntVar` met `AddMaxEquality`, zodat de straf exact gelijk is aan `max(0, n − 1)` en niet alleen een ondergrens.
2. Groepeer op `(klas, vak)`, niet op `les_id`: twee lessen met hetzelfde vak voor dezelfde klas tellen samen.
3. Tel in `checker.py` per klas het aantal "dubbele" lesuren (`tel_dubbele_vakken`) en neem Z3 op in `tel_straf`.
4. Zijbalk: schuifregelaar voor Z3. Pagina Rooster: toon het aantal dubbele vakuren.
5. Test: een vak met 2 uur per week op een week van 2 dagen geeft met Z3 straf 0; een vak met meer uren dan er dagen zijn geeft de kleinst mogelijke straf; de checker telt evenveel als de solver.

**Klaar als:**

- [ ] de checker telt hetzelfde aantal dubbele vakuren als de solver rapporteert
- [ ] `pytest` slaagt

**Niet doen:** geen blokuren (twee opeenvolgende uren) toestaan of afdwingen; lessen van twee uur zijn buiten scope.

### S4.4 · Zware vakken niet in het laatste uur (T16, Z4, 3 SP)

**Doel:** zware vakken staan liefst niet in het laatste uur van de dag.

**Doen:**

1. Voeg in `config.toml` `zware_vakken = [...]` toe (de lijst uit de teamkeuze), en in `Instellingen` het veld `zware_vakken: tuple[str, ...]`. `laad_instellingen` leest het in; ontbreekt het, dan is de lijst leeg.
2. Het "laatste uur" van een dag is het hoogste uur van die dag in de tijdslots. Dagen kunnen verschillend lang zijn (bijvoorbeeld een korte woensdag).
3. Bouw `z4_zware_vakken_laatste_uur` in `constraints.py`: de straf is de som van alle `x[l, s, r]` met een zwaar vak in een laatste uur. Er zijn geen hulpvariabelen nodig. Geef de lijst zware vakken mee via de functie; `constraints.py` leest `config.toml` niet zelf.
4. Tel in `checker.py` het aantal zware lesuren in een laatste uur (`tel_zware_laatste_uren`) en neem Z4 op in `tel_straf`.
5. Zijbalk: schuifregelaar voor Z4, en de lijst zware vakken als tekst (alleen tonen, niet bewerken). Pagina Rooster: toon het aantal zware laatste uren.
6. Test: een klein geval waarin een zwaar vak met Z4 nooit in het laatste uur staat; een dag met minder uren telt het juiste laatste uur; een lege lijst geeft altijd straf 0; de checker telt evenveel als de solver.

**Klaar als:**

- [ ] de checker telt hetzelfde aantal zware laatste uren als de solver rapporteert
- [ ] `pytest` slaagt

**Niet doen:** geen kolom "zwaar" in de tabel `les` en geen aanpassing van het schema; de lijst staat alleen in `config.toml`.

### S4.5 · Meting, documentatie en demo (T16, 2 SP)

**Doel:** het team weet wat de vier zachte regels samen kosten en kan ze tonen in de demo.

**Doen:**

1. Meet op de voorbeelddata en de variant `groot` met alle regels op hun standaardgewicht: zoektijd, verbetertijd, status, strafscore en de telling per regel. Zet dat in een tabel in `docs/STATUS.md` en de README.
2. Wordt de voorbeelddata niet meer binnen 30 seconden `optimaal`, noteer dat dan als bevinding; pas de standaardgewichten niet aan zonder teambeslissing.
3. Werk de README bij: de tabel met zachte regels, de zin "Z2 tot en met Z4 zijn niet gebouwd" eruit, en `zware_vakken` in `config.toml` uitgelegd. Haal ook de opmerking "Alleen Z1 is gebouwd" uit `config.toml`.
4. Voeg in `docs/DEMO.md` een korte stap toe: zet Z2 op 0 en weer aan, en laat zien hoe het rooster van een leraar verandert.

**Klaar als:**

- [ ] de README en `config.toml` beschrijven Z1–Z4 zoals ze gebouwd zijn
- [ ] de demo uit `docs/DEMO.md` werkt van begin tot einde
- [ ] `pytest` slaagt

**Niet doen:** geen nieuwe zachte regels toevoegen.

**Sprintreview 4 (team):** demo van de vier zachte regels en de meting.

## Definition of Done en eindcontrole

Een sessie is pas klaar als alles hieronder klopt; de agent meldt per punt hoe het gecontroleerd is.

**Per sessie:**

- alle punten onder "Klaar als" van die sessie zijn aantoonbaar gehaald;
- `pytest` slaagt, zonder overgeslagen tests;
- nieuwe functies hebben type hints, een korte docstring en minstens één test;
- `docs/STATUS.md` is bijgewerkt en er is één commit met de sessiecode;
- een teamlid heeft de wijziging bekeken voordat de volgende sessie start.

**Eindcontrole na S3.6:**

- [ ] `pytest` slaagt op een schone installatie
- [ ] de voorbeelddata geeft binnen 30 seconden een geldig rooster
- [ ] de checker vindt 0 schendingen van H1–H7 in dat rooster
- [ ] een onmogelijke dataset geeft een duidelijke melding in plaats van een crash (met uitleg van de oorzaak als S3.4 gedaan is)
- [ ] vanuit een lege database kun je via de app alles invullen en een rooster maken (als S3.5 gedaan is)
- [ ] `streamlit run app.py` werkt met alleen de stappen uit de README
- [ ] de demo uit `docs/DEMO.md` loopt van begin tot einde

## CLAUDE.md om te kopiëren

Zet deze tekst als `CLAUDE.md` in de hoofdmap; Claude Code leest hem bij elke nieuwe sessie.

```markdown
# Schoolrooster-solver: werkafspraken

## Eén sessie, één stap
- Elke sessie voert precies één stap uit docs/PLAN.md uit (S1.1, S1.2, ...).
- Lees bij de start: dit bestand, je eigen stap in docs/PLAN.md en docs/STATUS.md.
- Controleer eerst dat de vorige stap klaar is (pytest slaagt, staat in STATUS.md). Zo niet: meld het en stop. Bij S1.1 vervalt deze controle.
- Begin nooit aan een volgende stap, ook niet als er tijd over is.
- Volg de stap letterlijk: doe wat onder "Doen" staat, niets uit "Niet doen".

## Afsluiten
1. Draai pytest en de controles uit "Klaar als".
2. Voeg een blok toe aan docs/STATUS.md: stap, datum, bestanden, testresultaat, open punten.
3. Zet de status van de stap in het sessieoverzicht van docs/PLAN.md op "Klaar". Verander verder niets aan PLAN.md.
4. Eén commit met als boodschap: "<stap>: <korte omschrijving>".
5. Meld kort wat klaar is en wat de volgende stap is. Stop dan.

## Als iets niet lukt
- Commit niets dat tests breekt.
- Schrijf het probleem onder "Geblokkeerd" in docs/STATUS.md en stop.
- Vraag het team om een keuze als de stap het datamodel of de scope zou veranderen.

## Code
- Python 3.11, type hints, korte docstrings, functies onder ongeveer 40 regels.
- solver.py en checker.py kennen geen SQLite en geen Streamlit.
- Alleen db.py, seed.py en loader.py spreken de database aan.
- checker.py gebruikt geen OR-Tools en geen code uit solver.py of constraints.py.
- Nooit gebruikersinvoer in SQL-strings plakken; gebruik parameters en vaste tabelnamen.
- Geen nieuwe pakketten zonder ze te melden en in requirements.txt te zetten.
- Meldingen voor de gebruiker in het Nederlands.

## Data
- Voorbeelddata staat alleen in src/seed.py en is als voorbeeld gelabeld.
- data/rooster.db hoort niet in git.
```

## Open keuzes voor het team

Beslis deze punten voordat S1.1 start; ze bepalen de voorbeelddata en de planning.

- [ ] Komt T19 (beheerpagina) in de presentatie en de backlog, en wat valt in sprint 3 weg als het te krap wordt?
- [ ] Klopt de demo-schaal (6 klassen, 10 leraren, 7 lokalen), of willen jullie de school nabootsen die jullie kennen?
- [ ] Is woensdagnamiddag vrij? Dan krijgt woensdag minder lesuren in de tijdslots.
- [ ] Mag Claude Code de code schrijven, en hoe verantwoorden jullie dat tegenover de docent?
- [ ] Wie reviewt na elke sessie, en wie start de volgende?
