# Schoolrooster-solver: werkafspraken

## Alle stappen in één keer
- Een sessie mag meerdere of alle stappen uit docs/PLAN.md afwerken (S1.1, S1.2, ...), strikt in de volgorde van het sessieoverzicht.
- Lees bij de start: dit bestand, docs/PLAN.md en docs/STATUS.md. Begin bij de eerste stap die nog niet op "Klaar" staat.
- Controleer vóór elke stap dat de vorige klaar is (pytest slaagt, staat in STATUS.md). Zo niet: meld het en stop.
- Werk stap voor stap: rond elke stap volledig af (zie "Afsluiten") voordat je aan de volgende begint.
- Volg elke stap letterlijk: doe wat onder "Doen" staat, niets uit "Niet doen".
- Stop na de laatste stap, of eerder als een stap geblokkeerd is of een teamkeuze nodig heeft.

## Afsluiten (na elke stap)
1. Draai pytest en de controles uit "Klaar als".
2. Voeg een blok toe aan docs/STATUS.md: stap, datum, bestanden, testresultaat, open punten.
3. Zet de status van de stap in het sessieoverzicht van docs/PLAN.md op "Klaar". Verander verder niets aan PLAN.md.
4. Eén commit per stap met als boodschap: "<stap>: <korte omschrijving>".
5. Ga door naar de volgende stap. Na de laatste stap: meld kort wat klaar is en wat open staat.

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
