# Schoolrooster-solver

Prototype dat een weekrooster voor een middelbare school berekent met OR-Tools (CP-SAT), SQLite en Streamlit. Het plan staat in [docs/PLAN.md](docs/PLAN.md), de voortgang in [docs/STATUS.md](docs/STATUS.md), een stappenplan voor de presentatie in [docs/DEMO.md](docs/DEMO.md) en een korte testhandleiding in [docs/TESTEN.md](docs/TESTEN.md).

De meegeleverde gegevens zijn **verzonnen voorbeelddata**, geen echte schooldata.

## Installatie

Vereist: Python 3.11 of hoger.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Opstarten

```bash
streamlit run app.py
```

De app opent in de browser. Bij de eerste start maak je een roostermaker aan. Open daarna in de zijbalk **Voorbeelddata**, kies een voorbeeld en klik op **Voorbeeld laden** (of vul zelf gegevens in op de pagina Gegevens) en ga naar de pagina **Rooster**. De database staat standaard in `data/rooster.db`; die wordt aangemaakt en zit niet in git.

Eigen datasets: elk CSV-bestand in `data/datasets/` (kolommen zoals bij **Importeren**) verschijnt als extra keuze onder **Voorbeelddata**. Laden wist de gegevens, maakt 5 dagen van 8 lesuren en leest de lessen in; accounts blijven. Die map zit niet in git, omdat er echte schoolgegevens in kunnen staan.

Streamlit is standaard ook bereikbaar vanaf andere toestellen op hetzelfde netwerk, en wie de app als eerste opent op een database zonder accounts wordt roostermaker. Gebruik daarom `streamlit run app.py --server.address localhost` als alleen jij erbij hoeft.

### Met Docker

```bash
docker compose up -d --build
```

De app draait dan op poort 8501 (`http://<server>:8501`); een andere poort kies je met `PORT=80 docker compose up -d`. De database staat in het volume `rooster-data` en blijft bewaard bij herstarten. Na een codewijziging opnieuw `docker compose up -d --build`.

Zonder browser kan het ook in de terminal:

```bash
python -m src.cli seed                      # voorbeelddata in data/rooster.db (--variant onmogelijk of --variant groot)
python -m src.cli solve                     # rooster berekenen en per klas afdrukken
python -m src.cli check                     # berekenen en onafhankelijk controleren op H1-H7
python -m src.cli bench                     # de solver meten op de voorbeelddata (zie "Resultaat op de voorbeelddata")
```

## Rollen

| | Roostermaker | Leraar |
| --- | --- | --- |
| Accounts beheren | ja | nee |
| Voorbeelddata laden, database leegmaken, databasepad | ja | nee |
| Gegevens aanpassen en importeren | ja | nee |
| Rooster berekenen, opslaan en volledig bekijken | ja | nee |
| Eigen rooster bekijken (als er een leraar gekoppeld is) | nee | ja |

Een aparte rol beheerder valt buiten dit project. Accounts met de oude rol beheerder worden bij het openen van de database roostermaker.

De navigatie toont alleen de pagina's van je rol, en elke pagina controleert de rol opnieuw. De rol wordt bij elke klik uit de database gelezen, dus een wijziging geldt meteen. Wachtwoorden staan alleen als scrypt-hash in de tabel `gebruiker`. Accounts blijven staan bij "Database leegmaken" (onder **Geavanceerd** in de zijbalk) en bij het laden van voorbeelddata, maar de koppeling met een leraar valt dan weg en moet je opnieuw leggen op de pagina **Gebruikers**.

## De pagina's

- **Gebruikers** (roostermaker): accounts aanmaken, rol en leraar wijzigen, een nieuw wachtwoord instellen en accounts verwijderen. De laatste roostermaker kan niet verdwijnen. Met **Accounts maken voor alle leraren** krijgt elke leraar zonder account in één keer een account, gekoppeld aan die leraar, met de leraarcode als gebruikersnaam. Voorlopig hebben alle leraren hetzelfde wachtwoord, `docent123` (`LERAAR_WACHTWOORD` in `src/auth.py`); bij een leraaraccount zet **Terugzetten naar docent123** het wachtwoord terug. Dat is alleen bedoeld voor het prototype.
- **Mijn rooster**: het eigen rooster van een leraar, alleen om te bekijken. Dit is het rooster dat met "Opslaan in database" is bewaard.
- **Gegevens**: dagen en uren per dag instellen, en leraren, lokalen, onbeschikbaarheid en lessen invullen of aanpassen; daaronder de capaciteit van lokalen, blokuren en het aantal leerlingen per les. Bij het opslaan wordt alleen gewijzigd wat de gebruiker echt aanpast; foute invoer geeft een melding en laat de database ongewijzigd. Tijdslots opnieuw aanmaken wist de onbeschikbaarheid en het bewaarde rooster (de app waarschuwt eerst).
- **Rooster**: toont de aantallen en de meldingen van de validatie, berekent het rooster en toont status, oplostijd, schendingen, strafscore en per zachte regel het aantal (tussenuren klassen, tussenuren leraren, dubbele vakuren, zware vakken in het laatste uur). Het rooster is te bekijken per klas, per leraar en per lokaal, op te slaan in de database en te downloaden als CSV. Harde regels (moeten altijd kloppen) en zachte regels (voorkeuren met strafpunten) staan apart. Onder **Waar komen de strafpunten vandaan?** staat per zachte regel het gewicht, het aantal overtredingen en de strafpunten (samen precies de strafscore), en elke overtreding met dag, uren, klassen, leraren en lokalen; die lijst komt van de onafhankelijke checker. Na **Verder verbeteren** toont de strafscore het verschil met het vorige rooster en staat onder **Geschiedenis van de strafscore** elke run met de score ervoor en erna. Het beste geldige rooster van de sessie blijft bewaard: is een latere berekening slechter, dan kun je het terugzetten. Is er geen rooster mogelijk, dan staat er een uitleg bij. De tijd om te verbeteren en de gewichten van de zachte regels stel je in de zijbalk in onder **Geavanceerd** (standaardwaarden in `config.toml`).

## Regels

**Harde regels** worden nooit geschonden. Een onafhankelijke controle (`src/checker.py`, zonder OR-Tools) kijkt het rooster na.

| Nr | Regel |
| --- | --- |
| H1 | Elk lesuur staat precies één keer ingepland |
| H2 | Een lokaal heeft per tijdslot hoogstens één les |
| H3 | Een leraar geeft per tijdslot hoogstens één les |
| H4 | Een klas heeft per tijdslot hoogstens één les |
| H5 | Een les gebruikt alleen een lokaal van het gevraagde type (regulier, lab of gym) |
| H6 | Een leraar staat niet ingepland op een onbeschikbaar tijdslot |
| H7 | Een leraar geeft per dag niet meer dan zijn maximum |
| H8 | Een les komt nooit in een te klein lokaal (als capaciteit en aantal leerlingen ingevuld zijn) |
| H9 | Een blokles staat per twee lesuren direct na elkaar op dezelfde dag, niet over de middagpauze (`pauze_na_uur` in `config.toml`, standaard na uur 4) |

H8 en H9 gelden alleen voor lessen en lokalen waarvoor je dat op de pagina **Gegevens** invult, onder **Capaciteit, blokuren en groepsgrootte**. Die gegevens staan in aparte tabellen (`lokaal_capaciteit`, `les_eigenschap`), zodat bestaande databases en imports gewoon blijven werken. Net als bij de lokaaltypes zitten lokalen niet in het model: per tijdslot eist het model genoeg lokalen per type en grootte, en daarna krijgen de grootste groepen eerst een lokaal dat past. Een blokles houdt waar het kan voor beide uren hetzelfde lokaal; dat is een voorkeur, geen harde regel. Een blokles met een oneven aantal uren of een groep die in geen enkel lokaal past, geeft vooraf een foutmelding.

**Herplannen bij afwezigheid.** Op de pagina **Rooster** meld je onder **Herplannen bij afwezigheid** een docent afwezig voor een of meer dagen (of uren). De solver past het rooster dan aan in twee stappen: eerst zo weinig mogelijk lesuren verplaatsen (de lessen van de afwezige docent schuiven naar een ander moment in de week), daarna met dat aantal zo weinig mogelijk strafpunten. Lokalen blijven waar het kan. De app toont elke wijziging (van, naar) en de checker kijkt het nieuwe rooster na, met de afwezige uren als onbeschikbaar. Het bewaarde rooster verandert pas als je opslaat. Vervangers en lessen laten vervallen zitten er niet in.

**Zachte regels** (de solver minimaliseert de som van gewicht × aantal):

| Nr | Regel | Wat telt als 1 strafpunt × gewicht | Standaardgewicht |
| --- | --- | --- | --- |
| Z1 | Geen tussenuren voor klassen | een vrij uur van een klas met eerder en later die dag nog een les | 10 |
| Z2 | Geen tussenuren voor leraren | hetzelfde, voor een leraar | 5 |
| Z3 | Hetzelfde vak niet twee keer op één dag | elk tweede, derde, ... lesuur van een vak voor een klas op dezelfde dag | 5 |
| Z4 | Zware vakken liever niet in het laatste uur | een lesuur van een zwaar vak in het laatste uur van die dag | 2 |

Gewicht 0 schakelt een regel uit. Welke vakken "zwaar" zijn, staat in `config.toml` onder `zware_vakken` (standaard alleen wiskunde; hoofdletters tellen niet). Het laatste uur is per dag het hoogste uur, dus een kortere dag heeft een eigen laatste uur. De checker telt elke zachte regel opnieuw na, zonder OR-Tools, en komt op dezelfde strafpunten uit als de solver.

## Resultaat op de voorbeelddata

De meting is te herhalen met:

```bash
python -m src.cli bench                     # 3 runs op de voorbeelddata, met hardware en instellingen
python -m src.cli bench --werkers 1         # met één zoekdraad: trager, maar elke run geeft hetzelfde rooster
```

**Dataset:** variant `voorbeeld` uit `src/seed.py` (verzonnen): 6 klassen, 10 leraren, 7 lokalen, 30 tijdslots, 144 lesuren.
**Configuratie:** `config.toml` zoals in de repo: verbetertijd 30 s, `random_seed = 0`, `num_workers = 0` (zoveel zoekdraden als logische kernen), gewichten Z1 = 10, Z2 = 5, Z3 = 5, Z4 = 2, zware vakken: wiskunde.
**Hardware en software:** AMD Ryzen AI 7 350 (8 kernen, 16 logische kernen), Windows 11, Python 3.12, OR-Tools 9.15 (27 november 2026).

| Zoekdraden | Status | Tijd (zoeken + verbeteren) | Strafscore |
| --- | --- | --- | --- |
| 16 (standaard op deze laptop) | `optimaal` | 4 tot 5,4 s | 0 |
| 8 | `optimaal` | 2 tot 4,2 s | 0 |
| 4 | `optimaal` | 2,2 s | 0 |
| 2 | `optimaal` | 13 tot 15 s | 0 |
| 1 | `geldig` | 30,6 s (tijdslimiet) | 626, bij elke run dezelfde |

Het zoeken naar een eerste geldig rooster duurt altijd minder dan 1 s. **De uitvoeringstijd hangt vooral af van het aantal zoekdraden**, dus van de processor: CP-SAT laat elke draad een andere zoekstrategie proberen, en met weinig draden ontbreken de strategieën die het optimum snel vinden. Met 4 of meer draden is strafscore 0 binnen enkele seconden gevonden en bewezen (`optimaal`). Met 1 of 2 draden (een oude laptop, een container met weinig CPU, of veel andere programma's tegelijk) loopt de verbetertijd van 30 s helemaal op en blijft het rooster `geldig` met nog strafpunten. Een meting van ongeveer 30 s met status `geldig` betekent dus: de tijdslimiet is bereikt voor het optimum gevonden was. Meer verbetertijd of **Verder verbeteren** helpt dan.

Met meer dan één zoekdraad hangt de uitkomst ook wat af van de timing tussen de draden, ondanks de vaste seed; met `num_workers = 1` is elke run gelijk.

Verder op de voorbeelddata:

- strafscore 0 betekent: geen tussenuren voor klassen of leraren, geen vak twee keer op een dag en geen wiskunde in het laatste uur
- ter vergelijking: zonder Z1 heeft een willekeurig geldig rooster ongeveer 20 tussenuren voor klassen, en met alleen Z1 hebben de leraren samen ongeveer 40 tussenuren
- schendingen volgens de checker: 0

## Hoe de solver rekent: twee fases

1. **Fase 1 (zoeken)** zoekt alleen een rooster dat alle harde regels H1–H7 haalt, zonder naar tussenuren te kijken. Dat duurt zo lang als nodig, tot hoogstens `max_tijd_zoeken_s` (standaard 300 seconden, in `config.toml`).
2. **Fase 2 (verbeteren)** begint pas als er een geldig rooster is, vertrekt van dat rooster en vermindert de strafpunten van de zachte regels Z1–Z4. De tijdslimiet uit de zijbalk, onder **Geavanceerd** (`tijdslimiet_s`, standaard 30 seconden) geldt alleen voor deze fase.

Zo is er altijd een werkbaar rooster zodra fase 1 er één vindt; fase 2 kan het alleen beter maken. Krijgt fase 2 niets beters, dan blijft het rooster uit fase 1 staan (status `geldig`). Alleen als fase 1 binnen de zoekgrens niets vindt, is er geen rooster. De app toont hoe lang zoeken en verbeteren elk duurden. De totale rekentijd is dus zoeken plus verbeteren en kan langer zijn dan de tijdslimiet.

Fase 2 krijgt het startrooster als volledige hint mee, ook de hulpvariabelen van de zachte regels, zodat CP-SAT meteen een oplossing heeft en alleen nog moet verbeteren. De solver doet een lichte presolve (voorbereiding van het model): met de volledige presolve ging op de grote variant alle tijd van fase 2 naar de voorbereiding, en werd er nooit gezocht.

Het model kiest alleen tijdslots, geen lokalen. Lokalen van hetzelfde type zijn uitwisselbaar, dus het model eist per tijdslot en per lokaaltype niet meer lesuren dan er lokalen zijn (H2 en H5). Na het oplossen krijgt elk lesuur een lokaal van zijn type; dat lukt altijd, en een klas houdt waar het kan hetzelfde lokaal. Dat maakt het model ongeveer elf keer kleiner en de solver veel sneller. Symmetrie breken (de lesuren van één les in weekvolgorde leggen) is ook geprobeerd, maar maakte de solver op de grote variant trager; het staat daarom uit (`symmetrie_breken` in `config.toml`).

In `config.toml` staan ook `random_seed` (vaste startwaarde, standaard 0) en `num_workers` (aantal zoekdraden; 0 is zoveel als de computer kernen heeft). Met meerdere zoekdraden hangt de uitkomst toch nog wat af van de timing; met `num_workers = 1` is ze herhaalbaar, maar trager.

Tijdens het rekenen toont de pagina **Rooster** wat de solver doet en, bij het verbeteren, de beste strafscore tot nu toe. Met **Stoppen en beste rooster houden** stopt het rekenen meteen; je houdt het beste rooster tot dat moment.

## Verder verbeteren (veilige versie)

Is het rooster nog niet `optimaal`, dan staat op de pagina **Rooster** de knop **Verder verbeteren**. Die rekent verder vanaf het rooster dat je ziet (ook een rooster dat in de database bewaard is), met de verbetertijd en de gewichten uit de zijbalk. Dat rooster is de veilige versie: de solver vertrekt ervan en geeft nooit een slechter rooster terug. Vindt hij niets beters, dan blijft het rooster staan en meldt de app dat. Zo kun je op een moeilijke dataset meerdere keren 30 seconden bijrekenen, zonder het werkbare rooster kwijt te raken. Sla het rooster op in de database om de veilige versie ook na het afsluiten te bewaren.

## Grote variant

`--variant groot` (in de app: **Voorbeelddata** › **Grote school**) maakt een veel krappere school: 16 klassen, 28 leraren, 16 lokalen, 40 tijdslots en 512 lesuren, met 84% bezetting van de gewone lokalen. Gemeten met alle zachte regels op hun standaardgewicht (13 november 2026, drie runs): zoeken naar een geldig rooster duurt ongeveer 1,1 seconden; daarna verbetert de solver 30 seconden. Het resultaat is een werkbaar rooster met status `geldig` en nog strafpunten (558 tot 588; het verschilt per run). Vóór het aparte toewijzen van lokalen was dat ongeveer 10,5 seconden zoeken en een strafscore rond 2400. Met alleen Z1 is het rooster nu in ongeveer 5 seconden optimaal (0 tussenuren). Met **Verder verbeteren** of meer verbetertijd in de zijbalk worden de strafpunten minder. Handig om te laten zien wat de verbetertijd doet.

## Lessen importeren

Op de pagina **Importeren** zet de app CSV, TSV, Excel (.xlsx), JSON en WebUntis-JSON om naar één vast formaat: `klas, vak, leraar, uren_per_week, soort_lokaal`. Kolomnamen als "docent", "groep" of "lesuren" worden vanzelf herkend. Het tijdstip van een les vervalt, want dat kiest de solver. Het aantal uren komt uit een urenkolom of wordt opgeteld uit de start- en eindtijden. Wat niet past, zoals gedeelde lessen of overlappende blokken, wordt gemeld en niet stilletjes aangepast. PDF en foto's worden niet gelezen.

Parallelle vakken uit een WebUntis-rooster komen in aparte groepen, bijvoorbeeld `3ITAI` en `3ITAI-2`, omdat een klas in het model maar één les tegelijk volgt. De solver houdt daarna niet tegen dat een vak uit `3ITAI-2` samenvalt met een vak uit `3ITAI` dat dezelfde studenten ook volgen.

Op de pagina **Importeren** (roostermaker) kan het ook zonder AI: sleep een CSV-, Excel-, JSON- of WebUntis-bestand in de app, bekijk de lessen en meldingen, en klik op **Lessen toevoegen**. Leraren worden op naam herkend of aangemaakt met maximaal 8 uur per dag; een les met dezelfde klas, vak en leraar krijgt de nieuwe uren. Ontbreken er tijdslots of lokalen, dan vult de import die aan, zonder iets te wissen: tot 8 uur per dag en lokalen met een gewone naam (Lokaal 1, Labo 1, ...) die je daarna kunt hernoemen. Upload op een lege database is dus genoeg om een rooster te berekenen. Is de omzetting onvolledig, dan moet je dat eerst bevestigen.

## Tests

```bash
pytest
```

De volledige testsuite duurt ongeveer vier à vijf minuten, omdat een deel van de tests de solver op de voorbeelddata en de grote variant draait.

## Bekende beperkingen

- Een lesuur is altijd één uur; er zijn geen lessen van twee uur.
- Geen keuzevakken over meerdere klassen. Lokaalcapaciteit, blokuren en herplannen na ziekte zitten er wel in (H8, H9, zie Regels), maar herplannen kent geen vervangers: de lessen schuiven alleen naar een ander moment. Capaciteit en blokuren zijn niet in te lezen via Importeren; vul ze in op de pagina Gegevens.
- Geen serverdatabase: het is één SQLite-bestand, bedoeld voor kleinschalig gebruik.
- De rollen zijn bedoeld voor het prototype, niet voor echte schoolgegevens op internet: er is geen HTTPS, geen blokkering na foute inlogpogingen en geen herstel via e-mail. Na het inloggen staat een ondertekende sessiecode in de adresbalk (`?sessie=...`), zodat je na het vernieuwen 8 uur ingelogd blijft; uitloggen haalt de code weg. Deel die link dus niet: wie hem heeft, is tot de code verloopt als jou ingelogd. De sleutel staat in `data/.sessiesleutel` (niet in git); dat bestand verwijderen logt iedereen uit.
- Er is geen concept of publicatie: elk rooster dat wordt opgeslagen is meteen zichtbaar voor leraren.
- Ben je het wachtwoord van de enige roostermaker kwijt, dan is er geen herstelfunctie in de app.
- De lijst zware vakken (Z4) staat alleen in `config.toml`; de app toont ze, maar je kunt ze daar niet wijzigen.
- De uitleg bij een onoplosbaar rooster kan versoepeling van H5, H6 en H7 per leraar of lokaaltype aanwijzen; een oorzaak in H1 tot en met H4 (te veel lessen tegelijk) krijgt alleen een algemene tekst. De analyse is één optimalisatie (zo weinig mogelijk regels versoepelen) en duurt in totaal hoogstens 15 seconden; lukt het niet binnen die tijd, dan zegt de uitleg dat.
- De gegevens in `src/seed.py` zijn verzonnen voorbeelddata.
