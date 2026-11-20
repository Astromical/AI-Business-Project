# Status

Per afgewerkte sessie: datum, wat er gebouwd is, testresultaat en open punten.

## Sprint 1

### S1.1 · Projectopzet (16 oktober 2026)

**Bestanden:**

- nieuw: `requirements.txt`, `.gitignore`, `CLAUDE.md`, `docs/STATUS.md`, `src/__init__.py`, `tests/test_smoke.py`, `data/.gitkeep`, `pages/.gitkeep`
- verplaatst: `plan.md` → `docs/PLAN.md` (met `git mv`)
- gewijzigd: `README.md` (installatie en tests)

**Testresultaat:**

- `pip install -r requirements.txt` werkt in een nieuwe `.venv` (Python 3.12.3; ortools 9.15.6755, pandas 3.0.6, streamlit 1.66.0)
- `pytest`: 1 geslaagd, 0 overgeslagen

**Open punten:**

- `data/` en `pages/` hebben een lege `.gitkeep`, zodat de mappen in git staan zolang ze nog leeg zijn.
- De "Open keuzes voor het team" onderaan `docs/PLAN.md` zijn nog niet afgevinkt; vooral de demo-schaal en de vrije woensdagnamiddag bepalen de voorbeelddata in S1.3.

### S1.2 · Domeinmodel en testopzet (16 oktober 2026)

**Bestanden:**

- nieuw: `src/models.py`, `tests/conftest.py`, `tests/test_models.py`, `pytest.ini`

**Testresultaat:**

- `pytest`: 10 geslaagd, 0 overgeslagen (ook via `python -m pytest`)
- `klein_probleem` en `onmogelijk_probleem` staan in `tests/conftest.py` en zijn zo bruikbaar vanuit elke testmodule

**Open punten:**

- `pytest.ini` (`pythonpath = .`) is toegevoegd zodat `import src...` ook werkt met gewoon `pytest`; dit bestand stond niet in de projectstructuur.
- `ProbleemData` heeft de opzoekingen `klassen`, `dagen`, `uren_per_dag` (aantal tijdslots per dag), `tijdslot_per_id`, `lokaal_per_id`, `leraar_per_id` en `les_per_id`, als `cached_property`.
- `Instellingen` heeft standaardwaarden: tijdslimiet 30 s en gewichten Z1=10, Z2=5, Z3=5, Z4=2 (uit de tabel in PLAN.md).
- De omzetting les → lesuren staat voorlopig als hulpfunctie `maak_lesuren` in `tests/conftest.py`; de echte omzetting hoort in `loader.py` (S1.4).
- `klein_probleem` heeft 1 regulier lokaal en 1 lab (5 regulier- en 3 lablesuren), zodat het ook met H5–H7 oplosbaar blijft. `onmogelijk_probleem` heeft als enige oorzaak dat klas 1A 7 lesuren heeft voor 6 tijdslots.

### S1.3 · SQLite-schema en voorbeelddata (23 oktober 2026)

**Bestanden:**

- nieuw: `data/schema.sql`, `src/db.py`, `src/seed.py`, `src/cli.py`, `tests/test_db_seed.py`

**Testresultaat:**

- `pytest`: 21 geslaagd, 0 overgeslagen
- `python -m src.cli seed` maakt `data/rooster.db` met 144 lesuren (6 klassen × 24, 10 leraren, 7 lokalen, 30 tijdslots, 2 leraren met onbeschikbaarheid)
- `--variant onmogelijk`: klas 1A heeft 32 lesuren op 30 tijdslots (152 lesuren in totaal); dit is de enige oorzaak
- Foute invoer (les met onbekende leraar, ongeldig lokaaltype) geeft een `IntegrityError` (getest)
- Oplosbaarheidscheck (getest): elke leraar heeft hoogstens tijdslots min onbeschikbaarheid aan uren (meeste: 24 van 28 voor Dubois); regulier 102 van 150 (68%), lab 24 van 30 (80%), gym 18 van 30 (60%), allemaal onder 85%

**Open punten:**

- `data/schema.sql` gebruikt `CREATE TABLE IF NOT EXISTS` (PLAN.md heeft `CREATE TABLE`), zodat `maak_schema` een bestaande database niet laat falen.
- `seed` wist eerst alle tabellen (`leeg_database`) en maakt daarna de data aan; het schema moet al bestaan (`maak_schema`, in de CLI gedaan).
- Voor de voorbeelddata is gekozen voor een volle week van 30 tijdslots (geen vrije woensdagnamiddag); `maak_tijdslots` ondersteunt een kortere woensdag al. De open keuzes in PLAN.md zijn nog niet beslist.
- `.venv` bestond nog niet in deze checkout en is aangemaakt met `pip install -r requirements.txt` (staat in `.gitignore`).

### S1.4 · Loader met validatie (23 oktober 2026)

**Bestanden:**

- nieuw: `src/loader.py`, `tests/test_loader.py`

**Testresultaat:**

- `pytest`: 31 geslaagd, 0 overgeslagen
- de voorbeelddata laadt (144 lesuren) zonder fouten of waarschuwingen
- elke controle heeft een eigen test: klas te veel uren, leraar te veel uren, geen lokaal van type, te weinig plaatsen per type, geen tijdslots, geen lessen

**Open punten:**

- `maak_lesuren` staat nu in `src/loader.py`; de kopie in `tests/conftest.py` blijft bestaan zodat de fixtures los van de loader blijven.
- `valideer` geeft tot nu toe alleen meldingen met ernst `fout`; `waarschuwing` wordt nog niet gebruikt.

### S1.5 · Solver met harde regels H1–H4 (23 oktober 2026)

**Bestanden:**

- nieuw: `src/constraints.py` (H1–H4), `src/solver.py`, `tests/test_solver.py`
- gewijzigd: `src/cli.py` (opdracht `solve`)

**Testresultaat:**

- `pytest`: 40 geslaagd, 0 overgeslagen
- oplostijd voor de voorbeelddata (144 lesuren): ongeveer 3,8 s, status `optimaal` (zonder zachte regels is elk geldig rooster optimaal)
- `klein_probleem` geeft een geldig rooster, `onmogelijk_probleem` geeft `onoplosbaar`; H1–H4 hebben elk een test die de uitkomst met gewone Python natelt

**Open punten:**

- Nog zonder lokaaltype: de CLI toont daarom lessen in een verkeerd lokaal (bijvoorbeeld nederlands in de sporthal). Dat lost S2.1 (H5) op.
- `solve` gebruikt 8 werkers (`num_workers = 8`).
- `python -m src.cli solve` heeft de extra optie `--tijdslimiet`.

## Sprint 2

### S2.1 · Lokaaltype en beschikbaarheid (23 oktober 2026)

**Bestanden:**

- nieuw: `tests/test_h5_h6.py`
- gewijzigd: `src/constraints.py` (`toegelaten_lokalen`, H6), `src/solver.py` (H5 bij het maken van de variabelen, parameter `uitgeschakeld`)

**Testresultaat:**

- `pytest`: 47 geslaagd, 0 overgeslagen
- oplostijd voor de voorbeelddata met H1–H6: ongeveer 2,4 s
- H5 en H6 hebben elk een test die de precieze plaats afdwingt én een test die faalt als je de regel weghaalt (zonder de regel wordt de onoplosbare dataset oplosbaar)

**Open punten:**

- `solve` en `bouw_model` hebben de parameter `uitgeschakeld: frozenset[str]` (bijvoorbeeld `{"H5"}`), alleen bedoeld voor tests.

### S2.2 · Maximum uren per dag (23 oktober 2026)

**Bestanden:**

- nieuw: `tests/test_h7.py`
- gewijzigd: `src/constraints.py` (H7), `src/solver.py`, `src/loader.py` (nieuwe fout in `valideer`)

**Testresultaat:**

- `pytest`: 52 geslaagd, 0 overgeslagen
- oplostijd voor de voorbeelddata met H1–H7: ongeveer 4 s
- H7-test: maximum 1 en 3 lesuren over 3 dagen geeft precies 1 uur per dag; zonder de regel (`uitgeschakeld={"H7"}`) wordt een onoplosbare dataset oplosbaar
- `valideer` meldt een leraar met meer lesuren per week dan `max_uren_per_dag × dagen`

**Open punten:**

- Geen.

### S2.3 · Onafhankelijke roostercontrole (23 oktober 2026)

**Bestanden:**

- nieuw: `src/checker.py`, `tests/test_checker.py`
- gewijzigd: `src/cli.py` (opdracht `check`)

**Testresultaat:**

- `pytest`: 64 geslaagd, 0 overgeslagen (ongeveer 28 s, vooral de solver-tests op de voorbeelddata)
- de checker vindt elke opzettelijk ingebouwde fout: H1 (ontbrekend en dubbel), H2, H3, H4, H5, H6 en H7, elk met een handgemaakt rooster
- het solverrooster voor `klein_probleem` en voor de voorbeelddata (144 lesuren) geeft 0 schendingen; `python -m src.cli check` meldt "Schendingen van H1-H7: 0"
- `checker.py` importeert alleen `src.models` (geen OR-Tools, geen `solver.py` of `constraints.py`)

**Open punten:**

- Geen.

### S2.4 · Streamlit: laden en oplossen (23 oktober 2026)

**Bestanden:**

- nieuw: `app.py`, `pages/2_Rooster.py`, `src/service.py`, `src/ui.py`, `tests/test_service.py`

**Testresultaat:**

- `pytest`: 72 geslaagd, 0 overgeslagen
- `streamlit run app.py --server.headless true` start zonder fouten (health-check 200)
- de logica buiten Streamlit staat in `src/service.py` en is getest; de pagina's zijn getest met `streamlit.testing.v1.AppTest`: zonder database, met onmogelijk voorbeeld (knop uitgeschakeld, foutmelding), en met voorbeelddata (rooster berekenen geeft status optimaal en 0 schendingen)
- de browser zelf (klikken in de zijbalk) is niet met de hand bekeken, alleen via AppTest en de health-check

**Open punten:**

- `src/service.py` en `src/ui.py` staan niet in de projectstructuur van PLAN.md; ze houden de pagina's dun en de logica testbaar. `src/ui.py` is de enige module met Streamlit (naast `app.py` en `pages/`).
- Het pad van de database staat in de zijbalk (`st.session_state["pad"]`, standaard `data/rooster.db`).
- "Database leegmaken" vraagt bevestiging met een vinkje; de knop is pas actief als het vinkje aan staat.

### S2.5 · Roosterweergave per klas, leraar, lokaal (23 oktober 2026)

**Bestanden:**

- nieuw: `src/views.py`, `tests/test_views.py`
- gewijzigd: `pages/2_Rooster.py` (tabs "Per klas", "Per leraar", "Per lokaal" met keuzelijst), `tests/conftest.py` (fixture `klein_rooster`), `tests/test_service.py`

**Testresultaat:**

- `pytest`: 80 geslaagd, 0 overgeslagen
- `rooster_tabel` is getest met `klein_probleem`: juiste vorm (uren × dagen) en juiste inhoud in een paar cellen voor klas, leraar en lokaal
- de AppTest van de roosterpagina bevestigt voor de voorbeelddata drie tabs, drie keuzelijsten en drie tabellen

**Open punten:**

- Kleuren per vak zijn afgeleid van een hash van de vaknaam (`vak_kleur`), dus vast per vak maar niet handmatig gekozen.
- De tabellen worden getoond met `st.table` (nodig voor meerregelige cellen met kleur); de opmaak is niet met het oog in de browser gecontroleerd.

**Sprintreview 2 (team):** nog te doen door het team (demo in de browser, velocity noteren).

## Sprint 3

### S3.1 · Zachte regel: geen tussenuren voor klassen (23 oktober 2026)

**Bestanden:**

- nieuw: `tests/test_z1.py`
- gewijzigd: `src/constraints.py` (Z1 met volledig gekoppelde hulpvariabelen), `src/solver.py` (doelfunctie, `strafscore` en `straf_per_regel`, parameter `gewichten`), `src/checker.py` (`tel_tussenuren`), `src/service.py`, `pages/2_Rooster.py` (strafscore en tussenuren in de app)

**Testresultaat:**

- `pytest`: 87 geslaagd, 0 overgeslagen
- **Nulmeting** (Z1 gewicht 0, voorbeelddata): 21 tussenuren in het rooster (het aantal verschilt per run, omdat het rooster dan willekeurig is)
- **Met Z1** (gewicht 10): 0 tussenuren, status `optimaal`, oplostijd ongeveer 4 s
- de checker (`tel_tussenuren`) telt hetzelfde aantal als de solver rapporteert: `straf_per_regel["Z1"] == 10 × tussenuren` (getest op de voorbeelddata en op een geval met een onvermijdelijk tussenuur)
- klein geval met 0 tussenuren in het beste rooster, een geval met een onvermijdelijk tussenuur (strafscore 10) en gewicht 0 dat Z1 uitschakelt zijn getest

**Open punten:**

- `straf_per_regel` bevat gewogen strafpunten per regel (gewicht × aantal tussenuren), geen aantallen. Het aantal tussenuren in de app komt uit de checker.
- `solve(..., gewichten=None)` gebruikt de standaardgewichten uit `models.py`; S3.2 vervangt dit door een `Instellingen`-object.
- Z2 tot en met Z4 zijn niet gebouwd (Could).

### S3.2 · Instellingen: tijdslimiet en gewichten (23 oktober 2026)

**Bestanden:**

- nieuw: `config.toml`, `src/config.py`, `tests/test_config.py`
- gewijzigd: `src/solver.py` (`solve(data, instellingen)`), `src/service.py`, `src/cli.py`, `src/ui.py` (schuifregelaars in de zijbalk), `pages/2_Rooster.py`, bestaande tests (aangepast aan de nieuwe `solve`-aanroep)

**Testresultaat:**

- `pytest`: 93 geslaagd, 0 overgeslagen (ongeveer 52 s)
- `config.toml` wordt met `tomllib` ingelezen; ontbrekende waarden krijgen de standaardwaarde
- gewicht 0 voor Z1 schakelt de regel uit (geen strafvariabelen, `straf_per_regel` leeg)
- een tijdslimiet van 1 seconde wordt gerespecteerd (oplostijd onder 5 s op de voorbeelddata)
- AppTest: de schuifregelaar voor Z1 verandert het resultaat zichtbaar (gewicht 10: 0 tussenuren; gewicht 0: meer dan 0 tussenuren)

**Open punten:**

- `solve` heeft nu de signatuur `solve(data, instellingen=None, uitgeschakeld=frozenset())`; de oude `tijdslimiet_s`-parameter is vervangen.
- De CLI gebruikt `config.toml`; `--tijdslimiet` overschrijft alleen de tijdslimiet.
- De zijbalk toont alleen schuifregelaars voor tijdslimiet en Z1, omdat Z2 tot en met Z4 niet gebouwd zijn.
- De instellingen worden niet in de database bewaard (zoals in het plan).

### S3.3 · Rooster opslaan en exporteren (23 oktober 2026)

**Bestanden:**

- nieuw: `tests/test_opslaan.py`
- gewijzigd: `src/db.py` (`bewaar_rooster`, `laad_rooster`), `src/views.py` (`rooster_csv`), `src/service.py` (`bewaar`, `bewaard_rooster`), `pages/2_Rooster.py` (knoppen "Opslaan in database" en "Download CSV", bewaard rooster tonen bij het openen)

**Testresultaat:**

- `pytest`: 98 geslaagd, 0 overgeslagen (ongeveer 78 s)
- opslaan en weer laden geeft exact dezelfde 144 toewijzingen; opnieuw opslaan vervangt het oude rooster
- de CSV heeft de kolommen `klas, dag, uur, vak, leraar, lokaal` en 144 rijen
- AppTest: na "Rooster berekenen" en "Opslaan in database" toont een nieuwe sessie (zoals na herstarten van de app) het bewaarde rooster zonder te rekenen, met 3 tabellen en 0 schendingen

**Open punten:**

- Een bewaard rooster wordt bij het openen met de checker gecontroleerd; als de gegevens daarna zijn aangepast, verschijnen de schendingen dus in de app.
- Het rooster wordt gewist als de database opnieuw gevuld of leeggemaakt wordt (`leeg_database` wist ook `ingepland`).

### S3.4 · Uitleg bij een onoplosbaar rooster (23 oktober 2026)

**Bestanden:**

- nieuw: `src/uitleg.py`, `tests/test_uitleg.py`
- gewijzigd: `src/solver.py` (H5 kan per lokaaltype uit, `uitgeschakeld={"H5:lab"}`), `src/service.py` (`Berekening.uitleg`), `pages/2_Rooster.py` (uitleg onder de foutmelding), `tests/test_service.py`

**Testresultaat:**

- `pytest`: 105 geslaagd, 0 overgeslagen (ongeveer 79 s)
- drie opzettelijk onmogelijke datasets, elk zonder fouten door `valideer` en toch `onoplosbaar`, geven elk de juiste oorzaak:
    - twee leraren die alleen op uur 1 kunnen: H6, "Zonder de onbeschikbaarheid van … lukt het wel", met het tijdslot "maandag uur 2" dat uit de analyse blijkt
    - twee klassen met een gewoon lokaal en een lab: H5 voor beide lokaaltypes samen (met alleen lab versoepeld botsen de gewone lessen op het ene gewone lokaal)
    - een leraar met maximum 1 uur per dag die door een beschikbaarheidsbeperking twee uur op één dag moet geven: H7
- elke gevonden set is aantoonbaar minimaal: de set lost het probleem op en zonder één van de versoepelingen lukt het niet meer
- de pagina crasht niet op een onmogelijk probleem (AppTest met een database die door `valideer` komt maar onoplosbaar is)

**Open punten:**

- Gekozen is het "eenvoudiger alternatief" uit het plan (opnieuw oplossen met regels versoepeld, met een deletiefilter voor een minimale set), niet CP-SAT-assumpties. Versoepelbaar zijn H6 en H7 per leraar en H5 per lokaaltype.
- Oorzaken in H1–H4 (te veel lessen tegelijk voor klas, leraar of lokaal) worden niet verder uitgesplitst; dan komt een algemene tekst.
- Elke analyse-oplossing krijgt maximaal 10 s; bij een grote dataset kan de uitleg dus enkele tientallen seconden duren. Dit is niet op een grote onoplosbare dataset gemeten.
- Een tijdslot wordt alleen genoemd als de analyse bij één enkele oorzaak per tijdslot laat zien dat het oplost.
- Het deletiefilter geeft één minimale set; bij meerdere gelijkwaardige oorzaken (bijvoorbeeld twee leraren die allebei kunnen helpen) wordt er één genoemd.

### S3.5 · Beheerpagina voor gegevens (23 oktober 2026)

**Bestanden:**

- nieuw: `pages/1_Gegevens.py`, `src/beheer.py`, `tests/test_beheer.py`
- gewijzigd: `src/db.py` (`sla_tabel_op`, `lees_tabel`, `maak_tijdslots_opnieuw`, `OpslaanFout`)

**Testresultaat:**

- `pytest`: 119 geslaagd, 0 overgeslagen (ongeveer 82 s)
- opslaan werkt met een upsert (`INSERT ... ON CONFLICT DO UPDATE`) voor nieuwe en gewijzigde rijen en `DELETE` voor alleen de echt verwijderde rijen; de hele tabel wordt nooit gewist
- getest: geldige wijziging; les met onbekende leraar geweigerd met een Nederlandse melding en database ongewijzigd; rollback na een fout (een geldige rij naast een ongeldige wordt niet half opgeslagen); een leraar wijzigen laat diens onbeschikbaarheid staan; een leraar met lessen verwijderen mislukt zonder gevolgen; lege sleutel en dubbele rij geweigerd; onbekende tabelnamen geweigerd
- tijdslots opnieuw aanmaken wist de onbeschikbaarheid en het bewaarde rooster (eerst `ingepland` leeggemaakt) en laat de lessen staan
- vanuit een lege database zijn tijdslots, leraren, lokalen, onbeschikbaarheid en lessen ingevuld via dezelfde functies als de pagina, waarna `valideer` en `solve` een geldig rooster geven zonder schendingen
- AppTest: de beheerpagina start zonder fouten met een lege database en toont de waarschuwing (en een uitgeschakelde knop tot bevestiging) bij bestaande tijdslots

**Open punten:**

- `st.data_editor` zelf (typen en klikken in de tabel) is niet geautomatiseerd getest, omdat AppTest dat niet ondersteunt; de logica erachter staat in `src/beheer.py` en is getest. Controleer de pagina één keer met de hand in de browser.
- Een id van een bestaande rij aanpassen telt als verwijderen en nieuw aanmaken; bij een leraar met lessen of onbeschikbaarheid wordt dat geweigerd of leidt het tot verlies van de onbeschikbaarheid van de oude id. Pas liever de naam aan dan het id.
- In de tabel Onbeschikbaar kiest de gebruiker dag en uur in plaats van een tijdslot-id.
- Een gevulde `ingepland`-tabel wordt niet automatisch gewist bij het wijzigen van lessen; een bewaard rooster wordt wel bij het openen opnieuw gecontroleerd.

### S3.6 · Documentatie en demo (23 oktober 2026)

**Bestanden:**

- gewijzigd: `README.md` (installatie, opstarten, de twee pagina's, regels H1–H7 en Z1, resultaat op de voorbeelddata, beperkingen)
- nieuw: `docs/DEMO.md` (stappenplan van 5 minuten, met terugvaloptie in de terminal)

**Testresultaat:**

- `pytest`: 119 geslaagd, 0 overgeslagen
- voorbeelddata: oplostijd ongeveer 4,5 tot 5,3 s, status `optimaal`, strafscore 0, 0 tussenuren, 0 schendingen (drie metingen; staat ook in de README)

**Eindcontrole (Definition of Done):**

- [x] `pytest` slaagt op een schone installatie: nieuwe virtuele omgeving, alleen `pip install -r requirements.txt`, 119 geslaagd in 93 s
- [x] de voorbeelddata geeft binnen 30 seconden een geldig rooster: ongeveer 5 s
- [x] de checker vindt 0 schendingen van H1–H7 in dat rooster (`python -m src.cli check`, en getest)
- [x] een onmogelijke dataset geeft een duidelijke melding in plaats van een crash: de onmogelijke variant geeft "Klas 1A heeft 32 lesuren, maar er zijn maar 30 tijdslots." met uitgeschakelde knop; een dataset die door `valideer` komt maar onoplosbaar is, geeft een uitleg (S3.4, getest met AppTest)
- [x] vanuit een lege database alles invullen en een rooster maken: getest via dezelfde functies als de pagina Gegevens (S3.5)
- [x] `streamlit run app.py` start met alleen de README-stappen (health-check 200, de pagina's draaien in AppTest)
- [~] de demo uit `docs/DEMO.md`: de stappen zijn doorlopen via de CLI (seed, check, onmogelijke variant) en via AppTest (berekenen, weergaven, gewicht 0, opslaan, onmogelijk voorbeeld). **Niet met de hand in de browser doorlopen.**

**Open punten:**

- Het team moet de demo één keer met de hand in de browser doorlopen, vooral de pagina Gegevens (de tabeleditor is niet geautomatiseerd getest) en het uiterlijk van de roostertabellen.
- Sprintreview 3 (eindpresentatie en retrospective) en de "Open keuzes voor het team" onderaan `docs/PLAN.md` zijn nog aan het team.
- Een teamlid moet elke stap nog reviewen (Definition of Done per sessie).

### Extra: grote voorbeeldvariant (23 oktober 2026)

Op verzoek van het team, buiten de stappen van PLAN.md.

**Bestanden:** gewijzigd: `src/seed.py` (variant `groot`), `src/ui.py` (knop "Groot voorbeeld laden (traag)"), `tests/test_db_seed.py`, `README.md`.

**Testresultaat:** `pytest`: 121 geslaagd, 0 overgeslagen.

**Gemeten op de grote variant** (16 klassen, 28 leraren, 16 lokalen, 40 tijdslots, 512 lesuren; gewone lokalen 84% bezet, labs 80%, gym 60%):

- limiet 30 s: status `geldig` na 30,6 s, 65 tussenuren (strafscore 650), 0 schendingen
- limiet 90 s: status `optimaal` na 55,8 s, 0 tussenuren

**Open punten:**

- De grote variant staat niet in de tests als oplostest (die duurt te lang); alleen de aantallen, de bezetting en de validatie zijn getest.
- Rekenen op deze variant blokkeert de pagina Rooster tot de solver klaar is.

### Fix: crash bij een verouderd rooster (23 oktober 2026)

Gevonden bij het doorklikken door het team: `KeyError` in `rooster_csv` op de pagina Rooster.

**Oorzaak:** de pagina bewaarde het berekende rooster in `st.session_state` en toonde het ook als de database intussen veranderd was (bijvoorbeeld via een ander tabblad of een andere databank in de zijbalk). Verwijst dat oude rooster naar een tijdslot dat niet meer bestaat, dan crasht de weergave.

**Oplossing:** `Berekening` onthoudt nu op welke `ProbleemData` het rooster berekend is (`service.is_actueel`). Klopt dat niet meer met de database, dan gooit de pagina het resultaat weg en meldt ze "De gegevens zijn veranderd sinds de laatste berekening. Bereken het rooster opnieuw."

**Bestanden:** `src/service.py`, `pages/2_Rooster.py`, `tests/test_service.py` (regressietest die de crash eerst reproduceerde, en een test voor `is_actueel`).

**Testresultaat:** `pytest`: 123 geslaagd, 0 overgeslagen.

### Solver in twee fases (23 oktober 2026)

Op verzoek van het team: eerst een werkbaar rooster, dan verbeteren. Aanleiding: op de grote variant gaf de solver soms na 30 s "geen oplossing binnen tijd", omdat hij met Z1 erbij het eerste geldige rooster niet op tijd vond.

**Wat veranderd is:**

- `solve` zoekt in fase 1 alleen een rooster dat H1–H7 haalt. Fase 2 minimaliseert Z1 in de resterende tijd, met het rooster uit fase 1 als startpunt (`AddHint`). Vindt fase 2 niets, dan blijft het rooster uit fase 1 staan met status `geldig`, en `waardeer` rekent de strafpunten ervan uit.
- Fase 2 krijgt minstens 1 s, dus de totale oplostijd kan de limiet iets overschrijden.
- De pagina Rooster toont "-" in plaats van 0 bij schendingen, strafscore en tussenuren als er geen rooster is.

**Bestanden:** `src/solver.py`, `pages/2_Rooster.py`, `tests/test_twee_fases.py` (nieuw), `tests/test_service.py`, `README.md`.

**Testresultaat:** `pytest`: 128 geslaagd, 0 overgeslagen (ongeveer 2 min 45 s, door de nieuwe test op de grote variant).

**Gemeten:**

- voorbeelddata: `optimaal` in ongeveer 7,5 s (was ongeveer 5 s in één fase)
- grote variant, limiet 30 s: `geldig` na 30,1 s, strafscore 880, 0 schendingen (vroeger soms geen rooster)
- grote variant, limiet 90 s: `optimaal` na 53,6 s, strafscore 0

**Open punten:**

- De terugvaloptie (fase 2 vindt niets) is getest door de tweede solveraanroep in de test bewust te laten mislukken (monkeypatch); de rest gebruikt de echte solver.
- Vindt fase 1 binnen de limiet niets, dan is er nog steeds geen rooster. De versnelling uit het plan (lokalen achteraf toewijzen) zou fase 1 sneller maken, maar is niet gebouwd.

### Tijdslimiet pas vanaf een geldig rooster (23 oktober 2026)

Op verzoek van het team: de tijdslimiet geldt alleen voor het verbeteren, niet voor het zoeken naar een eerste geldig rooster.

**Wat veranderd is:**

- `Instellingen` heeft een nieuw veld `max_tijd_zoeken_s` (standaard 300 s, in `config.toml`). Fase 1 zoekt tot er een geldig rooster is, tot hoogstens die grens. Fase 2 krijgt daarna de volledige `tijdslimiet_s`, niet wat er overblijft.
- `Resultaat` heeft een nieuw veld `tijd_zoeken_s`; `oplostijd_s` blijft de totale tijd. De app en de CLI tonen zoeken en verbeteren apart.
- De schuif in de zijbalk heet nu "Tijd om te verbeteren (seconden)". De melding bij "geen oplossing" noemt de zoekgrens.
- De uitleg bij een onoplosbaar rooster gebruikt per analyse-oplossing nog steeds een korte grens (10 s), ook voor het zoeken.

**Bestanden:** `src/models.py`, `src/solver.py`, `src/config.py`, `config.toml`, `src/uitleg.py`, `src/cli.py`, `src/ui.py`, `pages/2_Rooster.py`, `tests/test_config.py`, `tests/test_twee_fases.py`, `README.md`, `docs/DEMO.md`.

**Testresultaat:** `pytest`: 131 geslaagd, 0 overgeslagen (ongeveer 3 min).

**Gemeten:** grote variant met verbetertijd 30 s: `geldig` na 45,1 s in totaal (zoeken plus 30 s verbeteren), strafscore 880, 0 schendingen.

**Open punten:**

- Streamlit kan een lopende berekening niet netjes onderbreken; in het slechtste geval wacht de gebruiker tot de zoekgrens (5 minuten).
- De versnelling uit het plan (lokalen achteraf toewijzen, symmetrie wegnemen) is nog niet gebouwd; die zou het zoeken korter maken.

## Sprint 4

Teamkeuzes (30 oktober 2026): zware vakken voor Z4 = alleen wiskunde; standaardgewichten blijven Z1 = 10, Z2 = 5, Z3 = 5, Z4 = 2.

### S4.1 · Zachte regels generiek maken (30 oktober 2026)

**Bestanden:** `src/solver.py` (tabel `ZACHTE_REGELS`, functie `actieve_regels`, `GEEN_ZACHTE_REGELS` voor alle regels Z1–Z4), `src/uitleg.py` (gebruikt `GEEN_ZACHTE_REGELS` uit `solver.py`), `src/checker.py` (`tel_straf`), nieuw `tests/test_zachte_regels.py`.

**Wat veranderd is:** `bouw_model` bouwt elke regel uit `ZACHTE_REGELS` met gewicht > 0; een regel die niet in de gewichten staat telt als 0. Fase 2 draait zodra minstens één gebouwde regel een gewicht > 0 heeft. `service.py` had geen vaste verwijzing naar Z1 en is niet gewijzigd.

**Testresultaat:** `pytest`: 136 geslaagd, 0 overgeslagen (ongeveer 3 min 20 s). Geen bestaande test aangepast.

**Open punten:** geen.

### S4.2 · Geen tussenuren voor leraren (Z2) (30 oktober 2026)

**Bestanden:** `src/constraints.py` (`z2_tussenuren_leraren`; Z1 en Z2 delen de hulpfunctie `_tussenuren`), `src/solver.py` (Z2 in `ZACHTE_REGELS`), `src/checker.py` (`tel_tussenuren_leraren`, gedeelde `_tel_gaten`, `tel_per_regel`), `src/service.py` (`Berekening.tellingen`), `src/ui.py` (`ZACHTE_REGEL_NAMEN`, schuifregelaar per regel), `pages/2_Rooster.py` (tweede rij met een telling per zachte regel), nieuw `tests/test_z2.py`.

**Aangepaste tests:** `tests/test_z1.py` en `tests/test_twee_fases.py` geven nu expliciet `{"Z1": 10}` mee waar ze alleen Z1 testen (met de standaardgewichten telt Z2 mee). `tests/test_service.py` zet in de zijbalktest ook Z2 op 0 voordat het strafscore 0 verwacht. De verwachtingen zelf zijn niet verzwakt.

**Testresultaat:** `pytest`: 141 geslaagd, 0 overgeslagen (ongeveer 4 min 20 s).

**Gemeten op de voorbeelddata** (verbetertijd 30 s):

- tussenuren leraren zonder Z2 (alleen Z1): 40
- met Z1 en Z2: 0 tussenuren leraren, 0 tussenuren klassen, status `optimaal` na 9,8 s (zoeken 3,4 s)
- grote variant met alleen Z1, ter vergelijking: `geldig`, 54,4 s, strafscore 640

**Open punten:** de grote variant met Z1 en Z2 samen is nog niet gemeten; dat gebeurt in S4.5.

### S4.3 · Vak niet twee keer op één dag (Z3) (30 oktober 2026)

**Bestanden:** `src/constraints.py` (`z3_vak_een_keer_per_dag`: per klas, vak en dag een `IntVar` gelijk aan `max(0, n − 1)` via `AddMaxEquality`; groepen met maar één lesuur per week krijgen geen variabele), `src/solver.py` (Z3 in `ZACHTE_REGELS`), `src/checker.py` (`tel_dubbele_vakken`, Z3 in `tel_per_regel`), `src/ui.py` (schuifregelaar en telling "Dubbele vakuren"), nieuw `tests/test_z3.py`.

**Aangepaste tests:** `tests/test_z1.py::test_z1_kiest_het_rooster_zonder_tussenuur` geeft nu `{"Z1": 10}` mee (twee uur hetzelfde vak op één dag is daar onvermijdelijk, dus Z3 gaf straf 5). De zijbalktest in `tests/test_service.py` zet nu alle schuifregelaars uit `ZACHTE_REGEL_NAMEN` op 0.

**Testresultaat:** `pytest`: 146 tests; in de volledige run faalde alleen de hierboven aangepaste Z1-test, die daarna apart slaagt (7 van 7 in `tests/test_z1.py`).

**Gemeten tijdens de testrun:** voorbeelddata met Z1 en Z2 (Z3 uit): `optimaal` in 11,4 s; grote variant met alleen Z1: `geldig`, 47,2 s, strafscore 640.

**Open punten:** de voorbeelddata met alle regels samen wordt gemeten in S4.5.

### S4.4 · Zware vakken niet in het laatste uur (Z4) (30 oktober 2026)

**Bestanden:** `config.toml` (`zware_vakken = ["wiskunde"]`, teamkeuze), `src/models.py` (`Instellingen.zware_vakken`, standaard leeg), `src/config.py` (leest de lijst), `src/constraints.py` (`z4_zware_vakken_laatste_uur`: de x-variabelen van zware vakken in het laatste uur van hun dag, zonder hulpvariabelen), `src/solver.py` (Z4 in `ZACHTE_REGELS`; `bouw_model`, `_verbeter` en `waardeer` geven de zware vakken door), `src/checker.py` (`tel_zware_laatste_uren`, Z4 in `tel_per_regel` en `tel_straf`), `src/service.py` en `pages/2_Rooster.py` (zware vakken mee voor de telling, ook bij een bewaard rooster), `src/ui.py` (schuifregelaar Z4 en de lijst zware vakken als tekst), `src/cli.py` (neemt de zware vakken uit `config.toml` over), nieuw `tests/test_z4.py`.

**Keuzes:** het laatste uur is per dag het hoogste uur in de tijdslots. Vaknamen worden zonder onderscheid tussen hoofdletters en kleine letters vergeleken ("Wiskunde" telt als "wiskunde"). Het schema is niet aangepast.

**Testresultaat:** `pytest`: 153 geslaagd, 0 overgeslagen (ongeveer 4 min 40 s). Geen bestaande test aangepast.

**Open punten:** de lijst zware vakken is in de app alleen te lezen, niet te bewerken (zoals gepland).

### S4.5 · Meting, documentatie en demo (30 oktober 2026)

**Bestanden:** `README.md` (tabel met Z1–Z4, `zware_vakken`, nieuwe metingen, testduur, beperkingen), `config.toml` (opmerking "Alleen Z1 is gebouwd" vervangen door een korte uitleg van Z1–Z4), `docs/DEMO.md` (stap 3 bijgewerkt, nieuwe optionele stap 5b met Z2).

**Gemeten** met `config.toml` (verbetertijd 30 s, gewichten Z1 = 10, Z2 = 5, Z3 = 5, Z4 = 2, zware vakken: wiskunde):

| Data | Status | Zoeken | Totaal | Strafscore | Z1 | Z2 | Z3 | Z4 | Checker = solver | Schendingen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| voorbeeld (run 1) | `optimaal` | 3,3 s | 17,5 s | 0 | 0 | 0 | 0 | 0 | ja | 0 |
| voorbeeld (run 2) | `optimaal` | 3,3 s | 14,5 s | 0 | 0 | 0 | 0 | 0 | ja | 0 |
| groot | `geldig` | 16,6 s | 47,0 s | 2662 | 88 | 281 | 71 | 11 | ja | 0 |

(Z1–Z4 zijn aantallen, geen strafpunten.) De voorbeelddata blijft binnen 30 seconden verbetertijd `optimaal`; de standaardgewichten zijn niet aangepast.

**Demo:** headless doorlopen met Streamlit `AppTest` (stappen 2, 3, 5b en 7): stap 3 gaf `optimaal`, 0 schendingen en alle tellingen 0 (20,5 s); met Z2 = 0 waren er 50 tussenuren voor leraren, met Z2 = 5 weer 0; het onmogelijke voorbeeld toont de melding over klas 1A en schakelt de knop uit, zonder fout.

**Testresultaat:** `pytest`: 153 geslaagd, 0 overgeslagen (ongeveer 5 min).

**Open punten:**

- De demo moet nog één keer met de hand in de browser doorlopen worden (uiterlijk van de tweede rij met tellingen en de schuifregelaars).
- Op de grote variant zijn er na 30 s verbeteren nog veel strafpunten, vooral tussenuren van leraren; meer verbetertijd helpt, maar dat is niet opnieuw gemeten met alle regels aan.
- Sprintreview 4 en de review per stap door een teamlid zijn aan het team.

## Extra's na sprint 4

### Rollen en inloggen (30 oktober 2026)

Op verzoek van het team, buiten de stappen van PLAN.md. Inloggen staat in PLAN.md nog onder "Buiten scope"; dat moet het team zelf bijwerken.

**Bestanden:**

- nieuw: `src/auth.py`, `pages/3_Mijn_rooster.py`, `pages/4_Gebruikers.py`, `tests/test_rollen.py`
- gewijzigd: `data/schema.sql` (tabel `gebruiker`), `src/models.py` (`Gebruiker`, `Rol`, `ROLLEN`), `src/db.py`, `src/service.py`, `src/ui.py`, `app.py` (`st.navigation` per rol), `pages/1_Gegevens.py`, `pages/2_Rooster.py`, `README.md`, `docs/DEMO.md`, `tests/conftest.py`, `tests/test_beheer.py`, `tests/test_opslaan.py`, `tests/test_service.py`

**Wat er gebouwd is:** drie rollen (beheerder, roostermaker, leraar) met een vaste rechtentabel in `src/auth.py`. Wachtwoorden met `hashlib.scrypt` uit de standaardbibliotheek, dus geen nieuw pakket. Het eerste account wordt in de app aangemaakt; er staat geen standaardwachtwoord in de code. Elke pagina controleert de rol zelf (`vereis_recht`), en de rol wordt bij elke klik opnieuw uit de database gelezen. Uitloggen wist de hele sessie behalve het databasepad.

**Keuzes:**

- De SQL staat in `db.py`; `auth.py` kent geen database.
- `app.py` gebruikt ook vóór het inloggen `st.navigation`, anders toont Streamlit de map `pages/` in de zijbalk.
- De eerste beheerder wordt met één `INSERT ... WHERE NOT EXISTS` aangemaakt, zodat er nooit twee kunnen ontstaan.
- `leraar_id` staat op `ON DELETE SET NULL`: voorbeelddata opnieuw laden laat het account staan, maar de koppeling valt weg.
- De pagina Rooster toont bij een lege database nu een uitleg; de oude melding "Er is nog geen database" kon niet meer voorkomen, want de accounts staan in diezelfde database.

**Aangepaste tests:** de paginatests loggen nu eerst in via `log_in_op_pagina`. `test_pagina_zonder_database_toont_uitleg` heet nu `test_pagina_zonder_gegevens_toont_uitleg` en verwacht de nieuwe tekst. `test_startpagina_start` gebruikt een tijdelijke database, zodat de test `data/rooster.db` niet meer aanraakt.

**Testresultaat:**

- `tests/test_rollen.py`: 50 geslaagd. Tien bewust ingebouwde lekken (controle weg, elk wachtwoord goed, andermans rooster en dergelijke) werden elk door minstens één test gevangen.
- Volledige run: 200 geslaagd, 2 gefaald (daarna kwam er in `tests/test_rollen.py` nog één test bij, die hierboven is meegeteld).
- De 2 gefaalde tests zijn `test_voorbeelddata_binnen_30_seconden` en `test_voorbeelddata_met_h5_h6_blijft_oplosbaar`: 34 à 38 s tegen een limiet van 30 s. Ze falen op een schone kopie van `main` (a43acc2) op dezelfde manier (36 s), en `solver.py` en `constraints.py` zijn niet gewijzigd. Deze stap is dus niet de oorzaak.
- Oorzaak van die 2 tests: sinds "Tijdslimiet pas vanaf een geldig rooster" krijgt fase 2 zelf al 30 s, dus `oplostijd_s < 30` lukt alleen als het optimum vroeg gevonden wordt. Op een druk toestel (hier onder meer Docker) gebeurde dat niet: status `geldig`, strafscore 151 à 160, zoeken 6 à 8 s in plaats van ongeveer 3 s. Niet gemeten op een rustig toestel.

**Open punten:**

- Inloggen, de navigatie als beheerder en het account `peeters` zijn door het team in de browser gebruikt. De rest van de rondgang (pagina Gebruikers, inloggen als leraar en roostermaker) is getest met AppTest en nog niet bevestigd in de browser.
- Beslissing nodig over de 2 tijdtests: de test aanpassen aan de nieuwe tijdslimiet, of de limiet herzien.
- Streamlit is standaard vanaf het netwerk bereikbaar en wie als eerste een database zonder accounts opent, wordt beheerder. De README beschrijft `--server.address localhost`.
- Een bewaard rooster is meteen zichtbaar voor leraren; er is geen concept of publicatie.
- Geen blokkering na foute pogingen, geen HTTPS en geen wachtwoordherstel voor de enige beheerder. Na vernieuwen van de pagina log je opnieuw in.
- Een gebruiker kan het eigen wachtwoord niet zelf wijzigen; dat doet de beheerder.

### Roosters omzetten met MCP (30 oktober 2026)

Op verzoek van het team, buiten de stappen van PLAN.md, op branch `feature/conversie` (vanaf `main`). De eerste commit zet alleen om; daarna is op verzoek de uploadzone toegevoegd.

**Bestanden:** nieuw: `src/conversie.py`, `mcp_server.py`, `.mcp.json`, `tests/test_conversie.py`. Gewijzigd: `requirements.txt` (`openpyxl`, `mcp>=2`), `README.md`.

**Wat er gebouwd is:** omzetten naar `klas, vak, leraar, uren_per_week, soort_lokaal` vanuit CSV, TSV, Excel, JSON en WebUntis-JSON, met de MCP-tools `formaat`, `bekijk_bestand`, `converteer_bestand` en `converteer_rijen`. De laatste controleert rijen die een AI-assistent uit bijvoorbeeld een PDF haalt. Uren worden uit de duur van blokken opgeteld; wat niet past, wordt gemeld.

**Testresultaat:** `tests/test_conversie.py`: 35 geslaagd, met verzonnen gegevens. De MCP is getest via een echte stdio-verbinding en op één echte WebUntis-export; die export staat niet in de repo. Geen bestaand bestand onder `src/`, `pages/` of `tests/` is gewijzigd, dus de volledige suite is niet opnieuw gedraaid.

**Open punten:**

- `.mcp.json` is niet getest vanuit een nieuwe Claude Code-sessie.
- Echte namen gaan via de MCP naar de AI-assistent; het team moet afspreken of dat mag.
- Gedeelde lessen, blokken en parallelle lessen passen niet in het model en worden alleen gemeld.

### Uploadzone in de app (30 oktober 2026)

Op verzoek van het team, op branch `feature/conversie`.

**Bestanden:** nieuw: `pages/6_Importeren.py`. Gewijzigd: `app.py`, `src/auth.py` (recht `importeren` voor beheerder en roostermaker), `src/beheer.py` (`importeer`), `src/db.py` (`importeer_lessen` in één transactie; `sla_tabel_op` deelt nu de upsert), `tests/test_conversie.py`, `README.md`.

**Wat er gebouwd is:** bestand kiezen, voorbeeld en meldingen bekijken, en pas daarna toevoegen. Een onvolledige omzetting moet eerst bevestigd worden. Opnieuw importeren verdubbelt niets.

**Testresultaat:** `tests/test_conversie.py`, `tests/test_beheer.py` en `tests/test_rollen.py`: 106 geslaagd, met nagebootst uploaden via AppTest. De volledige suite is niet opnieuw gedraaid; de solver is niet gewijzigd.

**Volledige route:** een verzonnen WebUntis-JSON (klas 4TEST, 24 lesuren) bovenop de voorbeelddata gaf via de pagina's Importeren en Rooster (AppTest) status `geldig`, 37 s, strafscore 102 en 0 schendingen. Een echte export met 50 lesuren past niet: het schema laat maximaal 40 tijdslots toe.

**Open punten:** Geïmporteerde leraren krijgen maximaal 8 uur per dag.

### Parallelle vakken als groepen (30 oktober 2026)

Op verzoek van het team, op branch `feature/conversie`. De WebUntis-omzetting zet vakken die parallel lopen in aparte groepen (`3ITAI`, `3ITAI-2`, ...), omdat H4 een klas maar één les tegelijk geeft. De indeling is per vak en altijd gelijk. `.gitignore` negeert nu `data/*.db`.

**Testresultaat:** `tests/test_conversie.py`: 45 geslaagd. Een echte export via de pagina's Importeren en Rooster (AppTest, op een kopie): 15 lessen, 50 lesuren, 4 groepen, 12 leraren, 5 dagen × 8 uur, 6 verzonnen lokalen: status `optimaal` in 19 s, strafscore 25 (5 dubbele vakuren), 0 schendingen. De export staat niet in de repo.

**Open punten:**

- De solver houdt niet tegen dat een vak uit `3ITAI-2` samenvalt met een vak uit `3ITAI` dat dezelfde studenten volgen. Dit is geen fout in de checker: het model kent de overlap tussen groepen niet.
- Gedeelde lessen met andere klassen, de echte lokalen en de beschikbaarheid van docenten zitten niet in dit rooster.

### Upload op een lege database (30 oktober 2026)

Op verzoek van het team, op branch `feature/conversie`: één database, en een upload is genoeg om te rekenen. Vóór het toevoegen vult `beheer.vul_basis_aan` ontbrekende tijdslots (tot 8 uur per dag) en automatische lokalen aan. Er wordt niets gewist.

**Testresultaat:** `tests/test_conversie.py` en `tests/test_beheer.py`: 61 geslaagd. Een echte export op een kopie van een lege database: 40 tijdslots, 4 automatische lokalen, 12 leraren, 15 lessen, 50 lesuren, status `optimaal` in 10 s, strafscore 25, 0 schendingen.

**Open punten:** de automatische lokalen zijn geen echte lokalen en krijgen geen namen uit het bestand. Niet in de browser getest.

### Extra: verder verbeteren vanaf een veilige versie (30 oktober 2026)

Op verzoek van het team, buiten de stappen van PLAN.md: als een berekend rooster nog strafpunten heeft, moet je verder kunnen rekenen vanaf dat rooster, zonder het kwijt te raken.

**Wat veranderd is:**

- `solver.verbeter_verder(data, toewijzingen, instellingen)`: rekent fase 2 opnieuw vanaf een bestaand geldig rooster. Dat rooster is de veilige versie: vindt de solver niets of iets slechters, dan komt het ongewijzigd terug. Een rooster dat niet bij de gegevens past, geeft een `ValueError`.
- `service.kan_verder` en `service.reken_verder` (onthoudt de vorige strafscore, berekend met de checker). Pagina Rooster: knop "Verder verbeteren" zolang het rooster geldig maar niet `optimaal` is, ook voor een bewaard rooster, met een melding "van X naar Y" of "geen beter rooster gevonden".
- **Gevonden fout in fase 2:** de hint bevatte alleen de x-variabelen ("solution hint is incomplete"), en op de grote variant ging de volledige presolve met alle 30 s lopen ("Stopped after presolve"). Fase 2 vond daar dus nooit iets en gaf altijd het rooster uit fase 1 terug (strafscore 2662 in de meting van S4.5). Opgelost met een volledige hint (`_vast_rooster` rekent alle hulpvariabelen voor het startrooster uit, `_zet_hint`) en een lichte presolve in `_los_op` (`max_presolve_iterations = 1`, geen probing, geen symmetrie).

**Bestanden:** `src/solver.py`, `src/service.py`, `pages/2_Rooster.py`, nieuw `tests/test_verder_rekenen.py`, `README.md`, `docs/DEMO.md`.

**Testresultaat:** `pytest`: 161 geslaagd, 0 overgeslagen (ongeveer 4 min).

**Gemeten** (standaardinstellingen, verbetertijd 30 s):

| Data | Vóór de fix | Na de fix |
| --- | --- | --- |
| voorbeeld | `optimaal`, 14,5–17,5 s, zoeken 3,3 s | `optimaal`, 13,5 s, zoeken 0,4 s |
| groot, berekenen | `geldig`, ongeveer 47 s, strafscore 2662 (fase 2 vond niets) | `geldig`, 39,8 s, strafscore 2202 |
| groot, verder verbeteren 1× / 2× | 2662 / 2662 | 1441 / 1307 |
| groot, alleen fase 1 | 23–25 s | 8 s |

**Open punten:**

- De knop is alleen headless getest (AppTest); het team moet hem één keer in de browser proberen.
- De veilige versie leeft in de sessie van de app. Wie hem ook na het afsluiten wil bewaren, klikt "Opslaan in database".

### Tijdtests meten de zoektijd (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`. Dit lost het open punt "2 tijdtests" uit "Rollen en inloggen" op.

**Bestanden:** `tests/test_solver.py`, `tests/test_h5_h6.py`. De solver is niet gewijzigd.

**Wat er veranderd is:** `test_voorbeelddata_binnen_30_seconden` en `test_voorbeelddata_met_h5_h6_blijft_oplosbaar` controleren nu `tijd_zoeken_s < 30` in plaats van `oplostijd_s < 30`. Fase 2 krijgt zelf al de tijdslimiet van 30 s, dus de totale tijd kon bijna nooit onder 30 s blijven. PLAN.md vraagt "binnen 30 seconden een geldig rooster", en dat is de tijd van fase 1.

**Testresultaat:** vóór de wijziging faalden beide tests (status `optimaal`, strafscore 0, zoeken 5,1 s, totaal 30,9 s). Na de wijziging: volledige suite 250 geslaagd in 8 minuten.

**Open punten:** de totale looptijd (zoeken plus verbeteren) wordt door geen enkele test begrensd.

### Duidelijkere weg van gegevens naar rooster (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`: alleen de UI duidelijker maken, verder niets veranderen.

**Bestanden:** `app.py`, `src/ui.py`, `pages/2_Rooster.py`, `pages/6_Importeren.py`, `tests/test_service.py`, `tests/test_conversie.py`.

**Wat er veranderd is:**

- De startpagina toont drie stappen (gegevens invoeren, rooster berekenen, rooster delen), met wat er al ingevoerd is en links naar de juiste pagina's. Een leraar ziet alleen een link naar Mijn rooster.
- De lege pagina Rooster verwijst nu ook naar Importeren. Zijn er fouten in de gegevens, dan staat er een link naar Gegevens.
- Na een import staat er een link "Volgende stap: rooster berekenen" en is de uploadzone weer leeg.
- `link_naar` in `src/ui.py` linkt alleen naar pagina's die de rol mag openen. `PAGINAS` staat nu in `src/ui.py` in plaats van `app.py`.

**Testresultaat:** volledige suite 253 geslaagd (3 nieuwe tests voor de startpagina, 1 uitgebreide importtest).

**Open punten:**

- Niet in de browser bekeken. In AppTest werken de links via `app.py`. Een los gestarte pagina toont in plaats daarvan "Ga in de zijbalk naar ...".
- Bewust niet veranderd: "Voorbeelddata laden" wist nog altijd alles zonder bevestiging, en het veld "Databasepad" staat nog in de zijbalk.

### Rol beheerder geschrapt (12 november 2026)

Teamkeuze, op branch `feature/conversie`: een beheerder valt buiten de scope van het project. Er blijven twee rollen over. De roostermaker neemt alles van de beheerder over: accounts, voorbeelddata, database leegmaken en het databasepad.

**Bestanden:** `src/models.py`, `src/auth.py`, `src/db.py`, `src/service.py`, `src/ui.py`, `pages/3_Mijn_rooster.py`, `data/schema.sql`, `README.md`, `tests/test_rollen.py`, `tests/test_service.py`, `tests/test_conversie.py`.

**Wat er veranderd is:**

- `Rol` is nu `roostermaker` of `leraar`. Het eerste account wordt een roostermaker (`maak_eerste_roostermaker`).
- De laatste roostermaker kan niet verwijderd of leraar gemaakt worden; vroeger gold dat voor de laatste beheerder.
- Datamodel: de CHECK op `gebruiker.rol` laat geen `beheerder` meer toe. `maak_schema` zet bestaande beheerders om naar roostermaker. In een oude database blijft de oude CHECK staan (SQLite wijzigt een bestaande tabel niet), maar de code schrijft de rol niet meer.
- `data/rooster.db`: het account `beheerder` is nu roostermaker; de naam is gebleven.

**Testresultaat:** volledige suite 254 geslaagd. Nieuw: `test_oude_beheerder_wordt_roostermaker`. Twee tests maken nu eerst een tweede roostermaker aan, omdat de laatste niet kan verdwijnen.

**Open punten:** elke roostermaker kan accounts beheren en de hele database leegmaken.

### Rol bovenaan, uitloggen verplaatst, minder labels (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`.

**Bestanden:** `src/ui.py`, `src/auth.py`, `src/seed.py`, `README.md`, `tests/test_rollen.py`, `tests/test_service.py`.

**Wat er veranderd is:**

- Bovenaan elke pagina staat links de rol in het groot en vet, met daaronder "Ingelogd als ...". De knop Uitloggen staat rechts op dezelfde regel, niet meer in de zijbalk.
- De roostermaker heeft geen pagina Mijn rooster meer (recht `eigen_rooster` weg). Alleen leraren zien die pagina.
- De namen in de voorbeelddata hebben geen "(voorbeeld)" meer. De data blijft als voorbeeld gelabeld: in de docstring van `src/seed.py` en met `LABEL` in de zijbalk onder de voorbeeldknoppen. In `data/rooster.db` is het label ook uit 10 leraarnamen en 7 lokaalnamen gehaald.

**Testresultaat:** volledige suite 255 geslaagd.

**Open punten:** niet in de browser bekeken. Teamafspraak om na te kijken: CLAUDE.md vraagt dat voorbeelddata "als voorbeeld gelabeld" is; de namen zelf dragen dat label niet meer.

### Rustigere zijbalk voor de database (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`.

**Bestanden:** `src/ui.py`, `README.md`, `tests/test_rollen.py`.

**Wat er veranderd is:**

- "Ingelogd als ..." staat niet meer onder de rol.
- De drie voorbeeldknoppen zijn één uitklapblok **Voorbeelddata**. Je kiest er Gewone school, Onmogelijk rooster of Grote school, met bij elk een korte uitleg, en klikt op **Voorbeeld laden**. Er staat bij dat het alle gegevens vervangt en de accounts laat staan; `LABEL` staat er ook.
- Databasepad en Database leegmaken staan in een ingeklapt blok **Geavanceerd**.
- Meldingen na laden of leegmaken verschijnen als toast.

**Testresultaat:** volledige suite 256 geslaagd. Nieuw: `test_roostermaker_laadt_een_gekozen_voorbeeld`.

**Open punten:** niet in de browser bekeken.

### AP-klassen als datasets (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`. De echte WebUntis-JSON van 3ITAI stond niet meer op de computer: `~/Downloads/webuntis_voorbeeld.json` is de verzonnen klas 4TEST. De lessen zijn daarom met de hand overgetikt uit vier WebUntis-screenshots (week van 7 december 2026).

**Bestanden:** `src/service.py` (`datasets`, `laad_dataset`), `src/ui.py`, `.gitignore`, `README.md`, `tests/test_service.py`. Lokaal en niet in git: `data/datasets/AP - 3ITAI.csv`, `AP - 1ITVTAI_TI.csv`, `AP - beide klassen.csv` en `LEESMIJ.md`.

**Wat er gebouwd is:** elk CSV-bestand in `data/datasets/` verschijnt onder **Voorbeelddata** in de zijbalk. Laden wist de gegevens (de accounts niet), maakt 5 × 8 tijdslots en gebruikt dezelfde import als de pagina Importeren.

**Testresultaat:** de drie datasets geven elk status `optimaal` met 0 schendingen: 3ITAI (24 lesuren) in 0,4 s met strafscore 15, 1ITVTAI_TI (30 lesuren) in 0,6 s met strafscore 0, beide klassen (54 lesuren) in ongeveer 3,5 s met strafscore 15. `data/rooster.db` bevat nu "AP - beide klassen". Twee nieuwe tests.

**Open punten:**

- 3ITAI mist de keuzeprojecten van maandag (namen afgekapt, 3 blokken verborgen). Project Maker telt 2 uur, maar loopt na 18:00 door.
- Gedeelde lessen (Trends in AI, AI and Society, AI for Business) staan bij "beide klassen" twee keer in het rooster, bij dezelfde docent.
- Labo en theorie zijn niet gescheiden; alle lessen staan in een gewoon lokaal.
- Echte docentcodes staan nu lokaal in `data/datasets/` en in `data/rooster.db`, niet in git.

### Regels onder Geavanceerd (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`. De verbetertijd en de gewichten van de zachte regels Z1-Z4 staan niet meer als losse groep "Instellingen" in de zijbalk. Op de pagina Rooster staan ze nu bovenaan in het blok **Geavanceerd**, boven de database. Op de andere pagina's bevat dat blok alleen de database.

**Bestanden:** `src/ui.py` (`zijbalk_met_regels` vervangt `instellingen_zijbalk`), `pages/2_Rooster.py`, `README.md`, `tests/test_service.py`.

**Testresultaat:** volledige suite 259 geslaagd; nieuw: `test_regels_staan_in_het_blok_geavanceerd`.

**Open punten:** de harde regels (H1-H7) zijn niet aan of uit te zetten in de app; dat kan alleen in de code (`uitgeschakeld`).

### Duidelijkere meldingen bij lege of onvolledige gegevens (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`.

**Bestanden:** `src/ui.py` (`lege_start`), `app.py`, `pages/2_Rooster.py`, `tests/test_service.py`.

**Wat er veranderd is:**

- Zonder lessen tonen Start en Rooster dezelfde uitleg, zonder rode foutmelding: "Welkom! Voeg eerst lessen toe, dan maakt de app er een weekrooster van.", met links naar Importeren en Gegevens, en voor de roostermaker een tip over Voorbeelddata.
- Zijn er wel lessen maar ontbreekt er iets, dan noemt de startpagina de fouten zelf in plaats van "De pagina Rooster toont welke".
- De pagina Rooster toont de uitleg nu zodra er geen lessen zijn, ook als er al tijdslots bestaan.

**Testresultaat:** volledige suite 260 geslaagd; daarna is alleen de welkomstzin aangepast en zijn `tests/test_service.py` en `tests/test_rollen.py` opnieuw gedraaid: 74 geslaagd. Nieuw: `test_startpagina_toont_welke_fouten_er_zijn`.

**Open punten:** niet in de browser bekeken.

### Ingelogd blijven na vernieuwen, kortere voorbeeldkeuze (12 november 2026)

Op verzoek van het team, op branch `feature/conversie`.

**Bestanden:** `src/auth.py` (`maak_sessiecode`, `lees_sessiecode`), `src/service.py`, `src/ui.py`, `.gitignore`, `README.md`, `tests/test_rollen.py`, `tests/test_service.py`.

**Wat er veranderd is:**

- Na het inloggen staat een met HMAC-SHA256 ondertekende sessiecode in de adresbalk (`?sessie=...`), 8 uur geldig. Vernieuwen houdt je ingelogd; uitloggen haalt de code weg. De rol wordt nog altijd bij elke klik uit de database gelezen, dus een verwijderd account komt er met een oude code niet meer in. De sleutel staat in `.sessiesleutel` naast de database (niet in git). Geen nieuw pakket, geen nieuwe tabel.
- Voorbeelddata is een keuzelijst in plaats van negen keuzerondjes met uitleg; alleen de uitleg van de gekozen optie staat eronder.
- De database werd niet leeggemaakt bij vernieuwen: alleen een berekend maar niet opgeslagen rooster verdwijnt, zoals PLAN.md (S3.3) het wil. Dat blijft zo (teamkeuze).

**Testresultaat:** volledige suite 264 geslaagd vóór de keuzelijst. Daarna `tests/test_service.py` en `tests/test_rollen.py` opnieuw: 77 geslaagd en 1 aangepast (`test_pagina_berekent_rooster` telt nu alleen de keuzelijsten in de pagina), die slaagt ook.

**Open punten:**

- Wie de link met `?sessie=` heeft, is tot de code verloopt ingelogd als die gebruiker. Een gewijzigd wachtwoord maakt oude codes niet ongeldig.
- `test_pagina_berekent_rooster` en de keuzelijst lezen de echte map `data/datasets/`; zonder die map werkt alles ook.

### MCP verwijderd (12 november 2026)

Teamkeuze, op branch `feature/conversie`: de pagina Importeren zet CSV, Excel, JSON en WebUntis-JSON zelf om, en PDF of foto's hoeven niet. De MCP-server voegt dan niets meer toe.

**Bestanden:** verwijderd: `mcp_server.py`, `.mcp.json`. Gewijzigd: `requirements.txt` (`mcp` weg), `src/conversie.py` (de melding bij een PDF verwijst niet meer naar MCP), `tests/test_conversie.py` (4 MCP-tests weg), `README.md` (hoofdstuk "Lessen importeren" in plaats van "Roosters omzetten (MCP)").

**Testresultaat:** volledige suite 260 geslaagd (264 min de 4 MCP-tests).

**Open punten:** het pakket `mcp` staat nog in `.venv`; het wordt niet meer gebruikt.

### Lokalen van de import krijgen een gewone naam (13 november 2026)

Op verzoek van het team, op branch `feature/conversie`. Lokalen die de import of een dataset zelf aanmaakt, heetten "Lokaal 1 (regulier, automatisch)" met id `AUTO-REGULIER-1`. Nu heten ze "Lokaal 1", "Labo 1" of "Sporthal 1" (id `LOKAAL-1`, ...). De melding na het importeren zegt "lokalen" in plaats van "automatische lokalen". In `data/rooster.db` zijn de twee bestaande lokalen hernoemd.

**Bestanden:** `src/beheer.py` (`LOKAALNAAM`), `pages/6_Importeren.py`, `README.md`.

**Testresultaat:** volledige suite 260 geslaagd.

**Open punten:** aan de naam is niet meer te zien dat een lokaal niet echt bestaat.

### Duidelijker roosterraster (13 november 2026)

Op verzoek van het team, op branch `feature/conversie`. Het rooster per klas, leraar en lokaal (en Mijn rooster) is geen platte tabel meer maar een HTML-raster: per les een blok in de kleur van het vak, met het vak vet en daaronder op aparte regels de twee andere gegevens (per klas: leraar en lokaal). Lege uren zijn lichte vakjes, dagen staan met een hoofdletter en de uren als "Uur 1". Op een smal scherm scrolt het raster horizontaal. Namen worden ge-escaped.

**Bestanden:** `src/views.py` (`rooster_html` vervangt `rooster_stijl`), `pages/2_Rooster.py`, `pages/3_Mijn_rooster.py`, `tests/test_views.py`, `tests/test_service.py`, `tests/test_rollen.py`, `tests/test_opslaan.py`.

**Testresultaat:** volledige suite 261 geslaagd.

**Open punten:** niet in de browser bekeken.

### Inloggen en account aanmaken als aparte schermen (13 november 2026)

Op verzoek van het team, op branch `feature/conversie`. Beide schermen staan smal in het midden. **Inloggen** ("Welkom terug", knop Inloggen over de hele breedte, tip bij een vergeten wachtwoord) verschilt nu duidelijk van **Account aanmaken** (alleen zonder accounts): eigen uitleg, wachtwoord twee keer invullen, minimumlengte als hint, en na het aanmaken meteen ingelogd.

**Bestanden:** `src/ui.py`, `tests/test_rollen.py`.

**Testresultaat:** volledige suite 263 geslaagd; nieuw: `test_verschillende_wachtwoorden_maken_geen_account`, `test_inlogscherm_verschilt_van_aanmaken`.

**Open punten:** geen.

### Map pages/ hernoemd naar paginas/ (13 november 2026)

Op verzoek van het team, op branch `feature/conversie`. Bij het laden toonde Streamlit ongeveer 1,6 seconden zijn eigen menu ("app, Gegevens, Rooster, Mijn rooster, ...") omdat de pagina's in een map met de speciale naam `pages/` stonden; pas daarna nam `st.navigation` het over. Met de map `paginas/` gebeurt dat niet meer. Gemeten in Chrome op een aparte kopie: zonder login meteen het inlogscherm, ingelogd meteen het eigen menu. De instelling `client.showSidebarNavigation = false` is geprobeerd en verworpen: die verbergt ook het eigen menu.

**Bestanden:** `pages/` → `paginas/`, `src/ui.py` (`PAGINAS`), `app.py` (commentaar), de paginapaden in `tests/`. `docs/PLAN.md` en `docs/SPRINTPLANNING.md` noemen nog `pages/`; die plannen zijn niet aangepast.

**Testresultaat:** volledige suite 263 geslaagd.

**Open punten:** geen.

### Accounts voor alle leraren in één keer (13 november 2026)

Op verzoek van het team, op branch `feature/conversie`. Op de pagina Gebruikers maakt **Accounts maken voor alle leraren** een account voor elke leraar zonder account: rol leraar, gekoppeld aan die leraar, de leraarcode in kleine letters als gebruikersnaam (bij een bezette naam met volgnummer) en een tijdelijk wachtwoord van 10 tekens zonder verwarrende tekens. Alles in één transactie; bestaande accounts blijven ongemoeid. De wachtwoorden staan eenmalig in een lijst met CSV-download en verdwijnen na "Klaar" of uitloggen; de database bevat alleen de hashes.

**Bestanden:** `src/auth.py` (`tijdelijk_wachtwoord`), `src/db.py` (`voeg_gebruikers_toe`), `src/service.py` (`maak_leraaraccounts`, `leraren_zonder_account`), `paginas/4_Gebruikers.py`, `README.md`, `tests/test_rollen.py`.

**Testresultaat:** volledige suite 265 geslaagd; nieuw: `test_accounts_voor_alle_leraren`, `test_knop_maakt_accounts_en_toont_de_lijst_een_keer`.

**Open punten:** een leraar kan het eigen wachtwoord niet wijzigen; een kwijtgeraakt wachtwoord zet de roostermaker opnieuw.

### Eén wachtwoord voor leraren, "docent" op Rooster, uurnummers (13 november 2026)

Op verzoek van het team, op branch `feature/conversie`.

- Voorlopig hebben alle leraren hetzelfde wachtwoord, `docent123` (`LERAAR_WACHTWOORD` in `src/auth.py`). **Accounts maken voor alle leraren** gebruikt het; er is geen lijst met willekeurige wachtwoorden meer. Bij een leraaraccount zet **Terugzetten naar docent123** het wachtwoord terug; zelf een wachtwoord kiezen kan nog. De bestaande leraaraccounts in `data/rooster.db` staan op `docent123`.
- "Docent" in plaats van "leraar" alleen op de pagina Rooster (aantallen, tabblad, keuzelijst, regel Z2) en als naam van de rol (`ROL_NAMEN` in `src/ui.py`: linksboven, Mijn rooster, rol in Gebruikers). Intern, in de meldingen van de onderliggende code en in het CSV-formaat blijft het `leraar`.
- In het rooster staan de uren als 1, 2, 3 in plaats van "Uur 1".
- Het voorbeeld op Importeren toonde de leraar als "None" na een tussentijdse wijziging van de kolomnaam; het voorbeeld neemt de kolommen nu op volgorde.

**Bestanden:** `src/auth.py`, `src/service.py`, `src/ui.py`, `src/views.py`, `paginas/2_Rooster.py`, `paginas/3_Mijn_rooster.py`, `paginas/4_Gebruikers.py`, `paginas/6_Importeren.py`, `README.md`, `tests/`.

**Testresultaat:** volledige suite 266 geslaagd.

**Open punten:** één gedeeld wachtwoord betekent dat wie de code van een collega kent, als die collega kan inloggen. Alleen voor het prototype.

### Reviewpunten B: solver en prestaties (13 november 2026)

Op verzoek van het team (reviewpunten 6 tot en met 11).

- **Lokalen apart (8):** het model heeft nog alleen `x[lesuur, tijdslot]` (grote variant: 512 × 40 in plaats van 512 × 40 × 11 variabelen). H2 en H5 worden samen "per tijdslot niet meer lesuren dan lokalen, en per type niet meer dan lokalen van dat type". Na het oplossen wijst `src/lokalen.py` de lokalen toe; dat lukt altijd (eerst de lesuren die hun eigen type nodig hebben, dan de rest), en een klas houdt waar het kan haar lokaal.
- **Symmetrie breken (7):** gebouwd (volgnummer n vroeger in de week dan n + 1), maar standaard **uit** (`symmetrie_breken = false` in `config.toml`): op de grote variant was de solver ermee trager. Vijf runs elk: zoeken 1,6 s met tegen 1,2 s zonder, strafscore na 30 s gemiddeld 753 met tegen 614 zonder. Waarschijnlijk omdat fase 2 vooral lesuren van plaats wisselt, en de volgorde precies die wissels blokkeert. Een bestaand rooster krijgt bij Verder verbeteren de volgnummers opnieuw in weekvolgorde (onschadelijk, want de lesuren zijn uitwisselbaar), zodat het ook met de optie aan past.
- **Vaste seed (6) en aantal werkers (10):** `random_seed` (standaard 0) en `num_workers` (standaard 0 = aantal kernen) in `config.toml` en `Instellingen`. Met meerdere zoekdraden blijft de uitkomst wat afhangen van de timing; met `num_workers = 1` is ze herhaalbaar (getest).
- **Uitleg (9):** niet meer één solve per kandidaat, maar één optimalisatie met een schakelaar per versoepelbare regel die zo weinig mogelijk regels uitzet; die set is ook minimaal. `SufficientAssumptionsForInfeasibility` is bewust niet gebruikt: dat geeft regels die samen botsen, terwijl de uitleg zegt "zonder X lukt het wel". De tijdslots die helpen zoekt ook één model. Alles samen blijft binnen één budget (in de app hoogstens 15 s); lukt het niet in die tijd, dan zegt de uitleg dat in plaats van "geen oorzaak".
- **Voortgang en stoppen (11):** `Voortgang` in `src/solver.py` krijgt elke betere oplossing door (`CpSolverSolutionCallback`) en kan de solver stoppen. De pagina Rooster rekent in een aparte draad, toont fase, tijd en beste strafscore, en heeft de knop **Stoppen en beste rooster houden**.

**Metingen** (grote variant, alle zachte regels op standaardgewicht, 30 s verbeteren): vóór de wijziging (twee runs) zoeken 10,3 en 10,7 s, strafscore 2464 en 2364; erna (drie runs, standaardinstellingen) zoeken 1,1 s, strafscore 560, 588 en 558. Met alleen Z1 is de grote variant nu in ongeveer 5 s optimaal. Uitleg op een onoplosbare grote school (drukste leraar één uur te weinig beschikbaar): eerst 17 s met een foute uitleg ("ook zonder versoepeling geen rooster", omdat de tijdslimiet afliep), nu 4,8 s met de juiste leraar. De stopknop is in de browser geprobeerd op een aparte kopie met de grote variant: de strafscore liep zichtbaar terug (2725 na 6 s, 1594 na 10 s), en na Stoppen stond binnen 1 s een geldig rooster met de melding dat het gestopt is.

**Bestanden:** `src/constraints.py`, `src/solver.py`, `src/lokalen.py` (nieuw), `src/uitleg.py`, `src/models.py`, `src/config.py`, `src/service.py`, `src/ui.py`, `paginas/2_Rooster.py`, `config.toml`, `README.md`, `tests/test_prestaties.py` (nieuw), `tests/test_twee_fases.py`, `tests/test_verder_rekenen.py`, `tests/test_zachte_regels.py` (de vervangers van `_los_op` nemen de extra argumenten door; de sleutels van `x` hebben geen lokaal meer).

**Testresultaat:** volledige suite 294 geslaagd in 96 s (was 281 in ongeveer 6 minuten); nieuw: `tests/test_prestaties.py` (13 tests).

**Open punten:** de stopknop heeft geen Streamlit-test (die kan niet klikken terwijl er gerekend wordt); de solverkant wel. Tijdens de uitleg werkt stoppen niet (die duurt hoogstens 15 s). Een lopende berekening rekent door als je naar een andere pagina gaat; bij terugkomen zie je de voortgang weer.

## Geblokkeerd

Niets.
