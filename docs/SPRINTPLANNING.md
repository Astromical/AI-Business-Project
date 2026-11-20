# Sprintplanning: prototype schoolrooster-solver

Laatst bijgewerkt: 23 oktober 2026

Dit document zet de sprintplanning uit het projectvoorstel (presentatie, slides 6–10) om in drie uitgeschreven sprints, zodat een agent per sessie meteen weet wat hij bouwt, in welke bestanden, met welke functies en hoe hij test.

## Hoe een agent dit document gebruikt

- `docs/PLAN.md` blijft leidend. Daar staan per sessie de volledige stappen onder "Doen", "Klaar als" en "Niet doen". Bij een tegenstrijdigheid wint `PLAN.md`.
- Dit document voegt per sessie toe: de afhankelijkheden, de bestanden die je aanraakt, het **contract** (publieke functies met signatuur) en de tests die je schrijft.
- Functienamen gemarkeerd met *(voorstel)* staan niet in `PLAN.md`. Gebruik ze tenzij er een goede reden is om af te wijken, en noteer een afwijking in `docs/STATUS.md`.
- Werkafspraken (één sessie per stap, afsluitprotocol, modulegrenzen) staan in `CLAUDE.md`.
- Bestaande domeinklassen staan al in `src/models.py` (S1.2): `Tijdslot`, `Lokaal`, `Leraar`, `Les`, `Lesuur`, `ProbleemData`, `Toewijzing`, `Resultaat`, `Melding`, `Schending`, `Instellingen`, plus `DAGEN` en `STANDAARD_GEWICHTEN`. Hergebruik ze; maak geen parallelle klassen.

## Productdoel

In 3 weken een werkend prototype dat binnen 30 seconden een geldig weekrooster berekent voor een middelbare school en het rooster toont per klas, leraar en lokaal.

**Demo-schaal:** 6 klassen, 10 leraren, 7 lokalen (5 regulier, 1 lab, 1 gym), 30 tijdslots (5 dagen × 6 uur) en 144 lesuren (24 per klas).

**Werking van de app (slide 3):**

1. **Inlezen** — klassen, leraren, lokalen en lessen uit SQLite, met controle op fouten.
2. **Oplossen** — OR-Tools CP-SAT plant elk lesuur zonder dubbele boekingen.
3. **Optimaliseren** — voorkeuren zoals weinig tussenuren wegen mee.
4. **Tonen** — rooster per klas, leraar en lokaal, opgeslagen in de database.

## Overzicht

| Sprint | Sprintdoel | SP | Sessies | Demo aan het einde |
| --- | --- | --- | --- | --- |
| 1 | De solver werkt in de terminal | 14 | S1.1 – S1.5 | `python -m src.cli seed` en `solve` live |
| 2 | Alle harde regels en een app in de browser | 14 | S2.1 – S2.5 | Streamlit-app, checker met 0 schendingen |
| 3 | Een beter rooster en de eindpresentatie | 18 | S3.1 – S3.6 | Eindpresentatie aan de project-eigenaar |
| 4 | Meer zachte regels (Z2–Z4) | 12 | S4.1 – S4.5 | Gewichten in de zijbalk verschuiven en het rooster zien veranderen |

Samen 58 story points (46 voor sprint 1–3). Werk de sessies strikt in volgorde af; de status per sessie houdt `docs/PLAN.md` bij.

**Modules en wie wie gebruikt:**

```text
seed.py ──► db.py ◄── loader.py ──► ProbleemData (models.py)
                                        │
                     constraints.py ◄── solver.py ──► Resultaat
                                        │
                     checker.py  (los van solver/constraints/OR-Tools)
                     views.py    (toewijzingen → pandas-tabellen)
cli.py, app.py, pages/*  ──► roepen loader, solver, checker, views aan (nooit OR-Tools zelf)
```

---

## Sprint 1: de solver werkt in de terminal (14 SP)

**Sprintdoel:** `python -m src.cli solve` maakt met de voorbeelddata een geldig rooster zonder dubbele boekingen (H1–H4).

**Sprint is klaar als:** seed en solve werken vanaf een lege map, `pytest` slaagt en de oplostijd staat in `docs/STATUS.md`.

| Sessie | Taak | Wat | Prio | SP | Hangt af van |
| --- | --- | --- | --- | --- | --- |
| S1.1 | T1 | Projectopzet | Must | 1 | – |
| S1.2 | T2, T5 | Domeinmodel en testopzet | Must | 3 | S1.1 |
| S1.3 | T3 | SQLite-schema en voorbeelddata | Must | 2 | S1.2 |
| S1.4 | T4 | Loader met validatie | Must | 3 | S1.3 |
| S1.5 | T6 | Solver met harde regels H1–H4 | Must | 5 | S1.4 |

### S1.1 · Projectopzet — Klaar

Mappen, `requirements.txt`, `.gitignore`, `CLAUDE.md`, `docs/STATUS.md`, `README.md` en een smoke-test. Zie `docs/STATUS.md`.

### S1.2 · Domeinmodel en testopzet — Klaar

`src/models.py`, fixtures `klein_probleem` en `onmogelijk_probleem` in `tests/conftest.py`, `pytest.ini`. De hulpfunctie `maak_lesuren` in `tests/conftest.py` verhuist inhoudelijk naar `loader.py` in S1.4.

### S1.3 · SQLite-schema en voorbeelddata

**Bestanden:** nieuw `data/schema.sql`, `src/db.py`, `src/seed.py`, `src/cli.py`, `tests/test_db.py`, `tests/test_seed.py`.

**Contract:**

```python
# src/db.py
def verbind(pad: str | Path) -> sqlite3.Connection        # zet PRAGMA foreign_keys = ON
def maak_schema(con: sqlite3.Connection) -> None           # voert data/schema.sql uit
def maak_tijdslots(con: sqlite3.Connection, uren_per_dag: dict[str, int]) -> None
def leeg_database(con: sqlite3.Connection) -> None

# src/seed.py
def seed(con: sqlite3.Connection, variant: str = "voorbeeld") -> None   # "voorbeeld" | "onmogelijk"
```

```text
python -m src.cli seed [--pad data/rooster.db] [--variant voorbeeld|onmogelijk]
```

**Voorbeelddata (variant "voorbeeld"):**

- klassen 1A, 1B, 2A, 2B, 3A, 3B, elk 24 lesuren → 144 lesuren;
- 10 leraren, waarvan 2 met enkele onbeschikbare tijdslots;
- 7 lokalen: 5 regulier, 1 lab, 1 gym;
- 30 tijdslots: maandag t/m vrijdag, 6 uur per dag.

**Oplosbaarheid zelf nagaan (en in een test vastleggen):**

- per leraar: lesuren ≤ 30 − onbeschikbare tijdslots;
- per lokaaltype: lesuren ≤ ongeveer 85% van (aantal lokalen × 30). Regulier: hoogstens 127 van 150; lab en gym: hoogstens 25 van 30 elk.

**Variant "onmogelijk":** dezelfde data met één duidelijke oorzaak, bijvoorbeeld één klas met 32 lesuren.

**Tests:** schema in een tijdelijke database (`tmp_path`), seed draaien, aantallen tellen (6 klassen, 10 leraren, 7 lokalen, 30 tijdslots, 144 lesuren), een les met onbekende leraar geeft `sqlite3.IntegrityError`, en de oplosbaarheidsgrenzen hierboven.

### S1.4 · Loader met validatie

**Bestanden:** nieuw `src/loader.py`, `tests/test_loader.py`.

**Contract:**

```python
# src/loader.py
def laad_probleem(con: sqlite3.Connection) -> ProbleemData   # lessen → lesuren (volgnummer 1..n)
def valideer(data: ProbleemData) -> list[Melding]
```

**Controles in `valideer`** (elk met een eigen test en een eigen kleine dataset):

| Controle | Ernst |
| --- | --- |
| geen tijdslots of geen lessen | fout |
| klas heeft meer lesuren dan tijdslots | fout |
| leraar heeft meer lesuren dan beschikbare tijdslots | fout |
| er is geen lokaal van een gevraagd type | fout |
| per lokaaltype meer lesuren dan lokalen × tijdslots | fout |

**Tests:** de voorbeelddata laadt zonder fouten; elke controle hierboven geeft precies de verwachte melding.

### S1.5 · Solver met harde regels H1–H4

**Bestanden:** nieuw `src/constraints.py`, `src/solver.py`, `tests/test_solver.py`; uitbreiden `src/cli.py`.

**Contract:**

```python
# src/constraints.py — elke regel een eigen functie
def h1_precies_een_keer(model, x, data) -> None      # (voorstel)
def h2_lokaal_een_les(model, x, data) -> None        # (voorstel)
def h3_leraar_een_les(model, x, data) -> None        # (voorstel)
def h4_klas_een_les(model, x, data) -> None          # (voorstel)

# src/solver.py
def solve(data: ProbleemData, tijdslimiet_s: float = 30) -> Resultaat
```

- `x[l, s, r]` is een `BoolVar` per lesuur, tijdslot en lokaal (alle lokalen; het lokaaltype komt in S2.1).
- Solverstatus → `optimaal`, `geldig`, `onoplosbaar` of `geen_oplossing_binnen_tijd`.

```text
python -m src.cli solve      # laadt, valideert, lost op, drukt rooster per klas af
```

**Tests:** `klein_probleem` geeft `optimaal` of `geldig`; `onmogelijk_probleem` geeft `onoplosbaar`; per regel H1–H4 een test die de uitkomst zelf natelt (geen dubbele boeking).

**Sprintreview 1:** seed en solve live draaien, `docs/STATUS.md` tonen, velocity noteren.

---

## Sprint 2: alle harde regels en een app in de browser (14 SP)

**Sprintdoel:** in Streamlit klik je op "Rooster berekenen" en zie je een rooster dat H1–H7 respecteert, bevestigd door een onafhankelijke controle.

**Sprint is klaar als:** `streamlit run app.py` werkt, de checker vindt 0 schendingen voor de voorbeelddata en `pytest` slaagt.

| Sessie | Taak | Wat | Prio | SP | Hangt af van |
| --- | --- | --- | --- | --- | --- |
| S2.1 | T7 | Lokaaltype en beschikbaarheid (H5, H6) | Must | 3 | S1.5 |
| S2.2 | T8 | Maximum uren per dag (H7) | Should | 2 | S2.1 |
| S2.3 | T9 | Onafhankelijke roostercontrole | Must | 3 | S2.2 |
| S2.4 | T10 | Streamlit: laden en oplossen | Must | 3 | S2.3 |
| S2.5 | T11 | Roosterweergave per klas, leraar, lokaal | Must | 3 | S2.4 |

### S2.1 · Lokaaltype en beschikbaarheid (H5, H6)

**Bestanden:** uitbreiden `src/constraints.py`, `src/solver.py`, `tests/test_solver.py`.

**Contract:**

```python
# src/constraints.py
def toegelaten_lokalen(lesuur: Lesuur, data: ProbleemData) -> tuple[Lokaal, ...]   # H5
def h6_onbeschikbaarheid(model, x, data) -> None                                  # (voorstel)
```

- `solve` maakt alleen nog `x[l, s, r]` voor lokalen uit `toegelaten_lokalen`.

**Tests:** een leraar die maar op 1 tijdslot kan en een lables die maar in 1 lokaal past: de solver kiest precies die plaatsen. Elke test faalt als je de regel weghaalt.

### S2.2 · Maximum uren per dag (H7)

**Bestanden:** uitbreiden `src/constraints.py`, `src/loader.py`, tests.

**Contract:**

```python
# src/constraints.py
def h7_max_per_dag(model, x, data) -> None    # (voorstel)
```

- Nieuwe fout in `valideer`: lesuren van een leraar > `max_uren_per_dag × aantal dagen`.

**Tests:** leraar met maximum 1 en 3 lesuren over 3 dagen → spreiding over 3 dagen; de nieuwe validatiefout.

### S2.3 · Onafhankelijke roostercontrole

**Bestanden:** nieuw `src/checker.py`, `tests/test_checker.py`; uitbreiden `src/cli.py`.

**Contract:**

```python
# src/checker.py — gewone Python, geen OR-Tools, geen import uit solver/constraints
def controleer(data: ProbleemData, toewijzingen: Sequence[Toewijzing]) -> list[Schending]
```

```text
python -m src.cli check      # lost op en controleert
```

**Tests:** per regel H1–H7 een handgemaakt fout rooster dat precies die schending geeft; het solverrooster voor `klein_probleem` en de voorbeelddata geeft 0 schendingen.

### S2.4 · Streamlit: laden en oplossen

**Bestanden:** nieuw `app.py`, `pages/2_Rooster.py`; eventueel kleine hulpfuncties buiten Streamlit met tests.

**Schermen:**

- **Zijbalk:** databasepad; knoppen "Voorbeelddata laden", "Onmogelijk voorbeeld laden", "Database leegmaken" (met bevestiging).
- **Roosterpagina:** aantallen (klassen, leraren, lokalen, tijdslots, lesuren) en meldingen van `valideer`; knop "Rooster berekenen" uitgeschakeld bij een fout; spinner tijdens het rekenen; daarna status, oplostijd en aantal schendingen.
- Resultaat in `st.session_state`.

**Tests:** alleen logica buiten Streamlit; de pagina zelf met `streamlit run app.py`.

### S2.5 · Roosterweergave

**Bestanden:** nieuw `src/views.py`, `tests/test_views.py`; uitbreiden `pages/2_Rooster.py`.

**Contract:**

```python
# src/views.py
def rooster_tabel(data: ProbleemData, toewijzingen: Sequence[Toewijzing],
                  soort: str, id: str) -> pandas.DataFrame   # soort: "klas" | "leraar" | "lokaal"
```

- Rijen = uren, kolommen = dagen; cel = vak + leraar of klas + lokaal.
- Vaste kleur per vak via pandas Styler, donkere tekst op lichte achtergrond.
- Tabs "Per klas", "Per leraar", "Per lokaal", elk met een keuzelijst.

**Tests:** `rooster_tabel` op `klein_probleem`: juiste vorm en enkele cellen.

**Sprintreview 2:** demo in de browser, checker met 0 schendingen tonen, velocity noteren, beslissen wat in sprint 3 past.

---

## Sprint 3: een beter rooster en de eindpresentatie (18 SP)

**Sprintdoel:** het rooster heeft zo weinig mogelijk tussenuren, is in te stellen, op te slaan en uit te leggen, en de demo staat klaar.

**Sprint is klaar als:** de eindcontrole onderaan `docs/PLAN.md` volledig klopt.

**Te vol:** 18 SP tegenover 14 in de vorige sprints. Valt er tijd tekort, dan schuift eerst S3.4 en daarna S3.2 naar Could. S3.6 gebeurt altijd.

| Sessie | Taak | Wat | Prio | SP | Hangt af van |
| --- | --- | --- | --- | --- | --- |
| S3.1 | T12 | Zachte regel Z1: geen tussenuren klassen | Should | 5 | S2.5 |
| S3.2 | T13 | Instellingen: tijdslimiet en gewichten | Should | 2 | S3.1 |
| S3.3 | T14 | Rooster opslaan en exporteren | Should | 1 | S2.5 |
| S3.4 | T15 | Uitleg bij onoplosbaar rooster | Should | 5 | S2.3 |
| S3.5 | T19 | Beheerpagina voor gegevens | Should | 3 | S2.4 |
| S3.6 | T18 | Documentatie en demo | Must | 2 | alle vorige |

### S3.1 · Geen tussenuren voor klassen (Z1)

**Bestanden:** uitbreiden `src/constraints.py`, `src/solver.py`, `src/checker.py`, `pages/2_Rooster.py`, tests.

**Contract:**

```python
# src/constraints.py
def z1_tussenuren_klassen(model, x, data) -> list[cp_model.IntVar]   # (voorstel) strafvariabelen

# src/checker.py
def tel_tussenuren(data: ProbleemData,
                   toewijzingen: Sequence[Toewijzing]) -> dict[str, int]   # (voorstel) per klas
```

- Modelleer met `bezet[k, d, u]`, `eerder_bezet`, `later_bezet` en volledige reïficatie (zie "Modelleertip" in `PLAN.md`).
- `solve` minimaliseert gewicht × strafvariabelen en vult `strafscore` en `straf_per_regel`.

**Volgorde:**

1. Nulmeting: tussenuren in het rooster zonder Z1 tellen met de checker → `docs/STATUS.md`.
2. Z1 bouwen.
3. Nieuwe meting met Z1 → `docs/STATUS.md`.

**Tests:** klein geval met 0 tussenuren als optimum; checker telt evenveel tussenuren als de solver rapporteert; voorbeelddata met Z1 heeft minder tussenuren dan de nulmeting en blijft onder 30 s.

### S3.2 · Instellingen

**Bestanden:** nieuw `config.toml`; uitbreiden `src/solver.py`, `app.py` of `pages/2_Rooster.py`, tests.

**Contract:**

```python
def laad_instellingen(pad: str | Path = "config.toml") -> Instellingen   # (voorstel) met tomllib
def solve(data: ProbleemData, instellingen: Instellingen = Instellingen()) -> Resultaat
```

- `config.toml`: `tijdslimiet_s = 30` en een sectie `[gewichten]`.
- Zijbalk: schuifregelaars met de standaardwaarden uit `config.toml`.
- Niet in de database bewaren.

**Tests:** gewicht 0 voor Z1 schakelt de regel uit; tijdslimiet van 1 s wordt gerespecteerd.

### S3.3 · Rooster opslaan en exporteren

**Bestanden:** uitbreiden `src/db.py`, `src/loader.py` of `src/views.py`, `pages/2_Rooster.py`, tests.

**Contract:**

```python
# src/db.py
def bewaar_rooster(con: sqlite3.Connection, toewijzingen: Sequence[Toewijzing]) -> None  # vervangt 'ingepland'
def laad_rooster(con: sqlite3.Connection) -> list[Toewijzing]
```

- Knop "Opslaan in database"; bij openen een bewaard rooster tonen.
- Knop "Download CSV" met kolommen `klas, dag, uur, vak, leraar, lokaal`.

**Tests:** opslaan en weer laden geeft exact dezelfde toewijzingen.

### S3.4 · Uitleg bij een onoplosbaar rooster

**Bestanden:** uitbreiden `src/solver.py` (of `src/constraints.py`), `pages/2_Rooster.py`, tests.

**Contract:**

```python
def verklaar_onoplosbaar(data: ProbleemData) -> list[str]   # (voorstel) Nederlandse uitleg
```

- Eerst de meldingen van `valideer` tonen.
- Daarna: een booleaanse schakelaar per leraar (H6, H7) en per lokaaltype (H5), met `AddAssumptions` en `SufficientAssumptionsForInfeasibility`. Eenvoudiger alternatief: telkens één regel voor één leraar of lokaaltype versoepelen en opnieuw oplossen.
- Tekst zoals: "Zonder de onbeschikbaarheid van Claes lukt het wel." Noem een tijdslot alleen als de analyse dat aantoont.

**Tests:** drie onmogelijke datasets met elk een andere oorzaak, die alle drie zonder fouten door `valideer` komen; elke dataset geeft de juiste oorzaak; de app crasht nooit.

### S3.5 · Beheerpagina voor gegevens (T19)

**Bestanden:** nieuw `pages/1_Gegevens.py`; uitbreiden `src/db.py`, tests.

**Contract:**

```python
# src/db.py — vaste lijst toegestane tabellen, nooit gebruikersinvoer in SQL
def bewaar_wijzigingen(con: sqlite3.Connection, tabel: str,
                       rijen: list[dict], verwijderde_ids: list) -> None   # (voorstel)
```

- Bovenaan: dagen, uren per dag, knop "Tijdslots aanmaken" (met waarschuwing als er al tijdslots zijn; `ingepland` eerst leegmaken).
- Tabs Leraren, Lokalen, Onbeschikbaar, Lessen met `st.data_editor(num_rows="dynamic")`.
- Opslaan per tabel in één transactie: upsert (`INSERT ... ON CONFLICT DO UPDATE`) en `DELETE` alleen voor echt verwijderde rijen. Nooit de hele tabel wissen (door `ON DELETE CASCADE`).
- `IntegrityError` → Nederlandse melding, niets half opgeslagen.

**Tests:** geldige wijziging; onbekende leraar geweigerd; rollback na fout; leraar wijzigen laat onbeschikbaarheid staan.

### S3.6 · Documentatie en demo

**Bestanden:** uitbreiden `README.md`; nieuw `docs/DEMO.md`; `docs/STATUS.md`.

- README: installatie, opstarten, de twee pagina's, regels H1–H7 en Z1, bekende beperkingen, oplostijd en strafscore voor de voorbeelddata.
- `docs/DEMO.md`: stappenplan van 5 minuten (database leegmaken → voorbeelddata laden → rooster berekenen → weergaven tonen → onmogelijk voorbeeld laden en melding tonen).
- Definition of Done uit `PLAN.md` nalopen en samenvatten in `docs/STATUS.md`.

**Sprintreview 3:** eindpresentatie aan de project-eigenaar, daarna retrospective.

---

## Productbacklog en MoSCoW

| Prioriteit | Taken |
| --- | --- |
| **Must** | T1 Projectopzet · T2 Domeinmodel · T3 Schema + voorbeelddata · T4 Loader + validatie · T5 Testopzet · T6 Harde regels H1–H4 · T7 Lokaaltype en beschikbaarheid · T9 Roostercontrole · T10 Laden en oplossen · T11 Roosterweergave · T18 Documentatie en demo |
| **Should** | T8 Max. uren per dag · T12 Geen tussenuren klassen · T13 Instellingen · T14 Opslaan en export · T15 Uitleg onoplosbaar · T19 Beheerpagina *(nieuw t.o.v. de presentatie)* |
| **Could** | T16 Overige zachte regels (Z2–Z4) *(ingepland in sprint 4)* · T17 Schaaltest met 20 klassen · kleur per vak · export naar PDF · CSV-import naar SQLite |
| **Won't (nu)** | inloggen en rollen · serverdatabase · herplannen na ziekte · keuzevakken over klassen · webbackend (FastAPI) |

Could-taken komen pas aan bod als alle Must- en Should-sessies klaar zijn, en dan alleen na een teambeslissing en een eigen sessie in `PLAN.md`.

## Risico's

| Risico | Impact | Maatregel | Waar in de planning |
| --- | --- | --- | --- |
| Model wordt traag bij meer klassen | Hoog | Tijdslimiet instellen; zo nodig `x[l, s]` per lokaaltype (zie `PLAN.md`) | S1.5, S3.2 |
| Geen geldig rooster mogelijk | Hoog | Validatie vooraf en uitleg bij onoplosbaar | S1.4, S2.2, S3.4 |
| Nieuwe regels van de school | Middel | Elke regel een aparte functie; zachte regels uit te zetten met gewicht 0 | S1.5, S2.1, S2.2, S3.2 |
| OR-Tools is nieuw voor het team | Middel | Eerste sprint klein houden, tests per regel, onafhankelijke checker | Sprint 1, S2.3 |
| Sprint loopt uit | Laag | Should-taken schuiven, Must blijft vast | Sprint 3 (eerst S3.4, dan S3.2) |

## Afwijkingen ten opzichte van de presentatie

Werk de presentatie hierop bij:

- **Lokalen:** 7 (5 regulier, 1 lab, 1 gym) in plaats van 6. Beslist op 23 oktober 2026: zo blijft de bezetting van reguliere lokalen onder ongeveer 85%.
- **"30 lesuren per week"** in de presentatie betekent 30 tijdslots; er worden 144 lesuren ingepland (24 per klas).
- **T19 beheerpagina** (Should, 3 SP) is nieuw. Sprint 3 telt daardoor 18 SP in plaats van 15, het totaal 46 in plaats van 43.
- **Plotly** staat in de architectuurschets, maar wordt niet gebruikt: de weergave gebeurt met pandas Styler. Plotly staat niet in `requirements.txt`.
- **T17 schaaltest** (Could) heeft nog geen sessie in `PLAN.md`.
- **T16 overige zachte regels** (Could, 12 SP) is op 30 oktober 2026 ingepland als sprint 4 (S4.1–S4.5). De sessies staan alleen in `PLAN.md`; dit document heeft voor sprint 4 geen eigen contracten.
- **"Regels aan en uit zetten"** geldt alleen voor zachte regels, via gewicht 0. Harde regels staan altijd aan.
