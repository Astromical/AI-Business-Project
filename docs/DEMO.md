# Demo: stappenplan van 5 minuten

Doel: laten zien dat het prototype een geldig rooster berekent, hoe je het bekijkt en wat er gebeurt bij een onmogelijke opdracht.

**Voorbereiding (voor de presentatie):** installeer het project volgens de README en start de app met `streamlit run app.py`. Laat het browservenster open staan op de startpagina.

| Tijd | Stap | Wat je doet | Wat je zegt of laat zien |
| --- | --- | --- | --- |
| 0:00 | 1. Database leegmaken | Log in als beheerder (bij de eerste start maak je die aan). Zijbalk: vink "Ik weet zeker dat ik alles wil wissen" aan en klik "Database leegmaken". | Er is nu geen data. De knop vraagt eerst om bevestiging. |
| 0:30 | 2. Voorbeelddata laden | Klik "Voorbeelddata laden", ga naar de pagina **Rooster**. | 6 klassen, 10 leraren, 7 lokalen, 30 tijdslots, 144 lesuren. Het zijn verzonnen voorbeeldgegevens. Er staan geen foutmeldingen. |
| 1:00 | 3. Rooster berekenen | Klik "Rooster berekenen". | Na ongeveer 15 seconden: status `optimaal`, schendingen 0 (onafhankelijke controle), strafscore 0. De tweede rij toont voor elke zachte regel 0: geen tussenuren voor klassen of leraren, geen vak twee keer op een dag, geen wiskunde in het laatste uur. |
| 2:00 | 4. Weergaven tonen | Open de tabs "Per klas", "Per leraar" en "Per lokaal" en kies telkens een andere klas, leraar of lokaal. | Elk vak heeft een vaste kleur. Lessen staan in het juiste type lokaal en niemand staat dubbel. |
| 3:00 | 5. Instelling tonen (optioneel) | Zet in de zijbalk het gewicht van Z1 op 0 en bereken opnieuw. | Het rooster is nog steeds geldig, maar heeft nu tussenuren voor klassen: het gewicht stuurt de oplossing. Zet het gewicht daarna terug op 10. |
| 3:15 | 5b. Leraren tonen (optioneel) | Zet in de zijbalk het gewicht van Z2 op 0, bereken opnieuw en open "Per leraar". | "Tussenuren leraren" is nu meestal groter dan 0 (in onze metingen 40 à 50) en je ziet gaten in het rooster van een leraar. Zet Z2 terug op 5 en bereken opnieuw: de gaten verdwijnen. |
| 3:25 | 5c. Verder verbeteren (optioneel) | Laad "Groot voorbeeld laden (traag)", bereken (ongeveer 40 s) en klik daarna "Verder verbeteren". | Het rooster is `geldig` maar heeft nog strafpunten. Verder verbeteren vertrekt van dit rooster en geeft nooit een slechter rooster terug: de app meldt de strafscore van voor en na. Laad daarna weer de gewone voorbeelddata. |
| 3:30 | 6. Opslaan en exporteren | Klik "Opslaan in database" en "Download CSV". | Het rooster blijft bewaard en is te openen in een spreadsheet. |
| 4:00 | 7. Onmogelijk voorbeeld | Klik in de zijbalk "Onmogelijk voorbeeld laden" en ga terug naar **Rooster**. | Er staat een duidelijke melding: "Klas 1A heeft 32 lesuren, maar er zijn maar 30 tijdslots." De knop "Rooster berekenen" is uitgeschakeld. Geen crash. |
| 4:15 | 7b. Rollen tonen (optioneel) | Maak op de pagina **Gebruikers** een leraar-account met een gekoppelde leraar en log daarmee in. Dit vraagt een bewaard rooster, dus laad eerst weer de voorbeelddata, bereken en sla op. | De leraar ziet alleen "Start" en "Mijn rooster", zonder knoppen om iets te wijzigen. |
| 4:30 | 8. Afsluiten | Klik "Voorbeelddata laden" om terug te gaan naar de werkende situatie. | Via de pagina **Gegevens** kan een school de eigen leraren, lokalen en lessen invullen. |

## Terugvaloptie zonder browser

```bash
python -m src.cli seed
python -m src.cli check                      # rooster berekenen en controleren: "Schendingen van H1-H7: 0"
python -m src.cli seed --variant onmogelijk
python -m src.cli solve                      # toont de melding over klas 1A
python -m src.cli seed                       # terug naar de werkende situatie
```

## Als er iets misgaat

- **De app start niet:** controleer of de virtuele omgeving actief is en `pip install -r requirements.txt` gelukt is.
- **Het rekenen duurt langer dan verwacht:** de solver zoekt eerst een geldig rooster (hoogstens 5 minuten) en verbetert het daarna nog 30 seconden; daarna toont de app het beste rooster dat gevonden is.
- **Een leeg scherm op de pagina Rooster:** laad eerst de voorbeelddata in de zijbalk.
