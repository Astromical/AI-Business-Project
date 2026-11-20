# De applicatie testen

Je hebt alleen Docker nodig. Voer de commando's uit in de projectmap.

## 1. Starten

```bash
docker compose up -d --build
```

Open daarna <http://localhost:8501>. Gebruik `--build` na elke codewijziging, anders draait de oude code.

## 2. Automatische tests

```bash
docker compose exec -w /app app python -m pytest -q -p no:cacheprovider
```

Verwacht: `294 passed`. In Git Bash zet je `MSYS_NO_PATHCONV=1` voor het commando.

## 3. In de browser

1. **Account:** maak een gebruikersnaam en wachtwoord aan. Je bent nu roostermaker.
2. **Voorbeelddata:** in de zijbalk **Voorbeelddata** › **Gewone school** › **Voorbeeld laden**.
3. **Rekenen:** ga naar **Rooster** en klik **Rooster berekenen**. Verwacht: **Schendingen 0**.
4. **Bekijken:** kijk de tabbladen **Per klas**, **Per docent** en **Per lokaal** na. Niemand staat twee keer in hetzelfde uur.
5. **Stoppen:** laad de **Grote school**, klik **Rooster berekenen** en na ongeveer 10 s **Stoppen en beste rooster houden**. Verwacht: meteen een rooster met 0 schendingen.
6. **Onmogelijk:** laad **Onmogelijk rooster**. Verwacht: een foutmelding over klas 1A en de rekenknop is uitgeschakeld.
7. **Docent:** laad de **Gewone school**, bereken en klik **Opslaan in database**. Ga naar **Gebruikers** › **Accounts maken voor alle leraren**. Log in met een leraarcode en `docent123`. Verwacht: alleen **Mijn rooster**.

## 4. Stoppen

```bash
docker compose down      # data blijft bewaard
docker compose down -v   # alles wissen, ook accounts
```
