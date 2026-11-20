# De applicatie uitproberen

Een korte rondleiding langs alles wat de schoolrooster-solver kan. Volg de stappen in volgorde; samen duren ze ongeveer 15 minuten. Je hebt alleen **Docker** nodig.

---

## 1. Starten

Open een terminal in de projectmap en voer uit:

```bash
docker compose up -d
```

Open daarna <http://localhost:8501> in je browser.

> De eerste keer bouwt Docker de app, dat duurt even. Is de code gewijzigd, gebruik dan `docker compose up -d --build`.

## 2. Account aanmaken

Bij de eerste start vraagt de app om een account. Kies een gebruikersnaam en een wachtwoord (minstens 8 tekens).
Je bent nu **roostermaker** en ziet links de pagina's Start, Gegevens, Rooster, Gebruikers en Importeren.

## 3. Voorbeelddata laden

Open in de zijbalk **Voorbeelddata**, kies **Gewone school** en klik **Voorbeeld laden**.
Op de startpagina zie je nu: 6 klassen, 10 leraren en 144 lesuren per week.

## 4. De gegevens bekijken

Ga naar **Gegevens**. Hier staat alles waarmee het rooster gemaakt wordt:

- **Dagen en uren per dag**: hoeveel lesuren elke dag heeft.
- **Leraren**: met het maximum aantal uren per dag.
- **Lokalen**: gewone lokalen, labo's en een turnzaal.
- **Onbeschikbaar**: uren waarop een leraar niet kan.
- **Lessen**: welke klas welk vak krijgt, van wie en hoeveel uur per week.

Pas gerust iets aan (bv. het maximum van een leraar) en klik **Opslaan**.

## 5. Een rooster berekenen

Ga naar **Rooster** en klik **Rooster berekenen**. Je ziet live wat de solver doet.
Na ongeveer 15 seconden verschijnt het rooster met:

- **Schendingen 0**: alle harde regels zijn gehaald (niemand staat dubbel, elke les in het juiste lokaal, ...).
- **Strafscore**: hoeveel zachte regels nog geschonden zijn, zoals tussenuren. Bij dit voorbeeld is dat 0.

Bekijk het rooster in de drie tabbladen:

- **Per klas**: het weekrooster van één klas.
- **Per docent**: het weekrooster van één leraar.
- **Per lokaal**: welke les wanneer in een lokaal zit.

Klik daarna **Opslaan in database** (dan zien de leraren het) en **Download als CSV** (om het in Excel te openen).

## 6. Met de instellingen spelen

Open in de zijbalk **Geavanceerd**. Hier stel je in hoe lang de solver mag verbeteren en hoe zwaar elke zachte regel weegt:

| Regel | Betekenis |
| --- | --- |
| Z1 | Geen tussenuren voor klassen |
| Z2 | Geen tussenuren voor leraren |
| Z3 | Hetzelfde vak niet twee keer op een dag |
| Z4 | Zware vakken (wiskunde) niet in het laatste uur |

Probeer: zet **Z2** op 0 en bereken opnieuw. Bij **Per docent** zie je nu gaten in het rooster van de leraren. Zet Z2 terug op 5 en bereken nog eens: de gaten verdwijnen.

## 7. Een grote school

Laad via **Voorbeelddata** de **Grote school** (16 klassen, 512 lesuren) en klik **Rooster berekenen**.

- Wil je niet wachten, klik dan na een tiental seconden **Stoppen en beste rooster houden**. Je krijgt meteen het beste rooster tot dan toe.
- Klik daarna **Verder verbeteren**: de solver rekent verder vanaf dit rooster en maakt het alleen beter, nooit slechter.

## 8. Een onmogelijk rooster

Laad via **Voorbeelddata** het **Onmogelijk rooster** en ga naar **Rooster**.
De app legt uit waarom er geen rooster kan bestaan (klas 1A heeft meer lesuren dan er tijdslots zijn) en schakelt de rekenknop uit.

## 9. Eigen lessen importeren

Maak een bestand `lessen.csv` met deze inhoud:

```csv
klas,vak,leraar,uren_per_week,soort_lokaal
1A,wiskunde,Peeters,4,regulier
1A,chemie,Janssens,2,lab
1A,LO,Claes,2,gym
1B,wiskunde,Peeters,4,regulier
1B,Frans,Maes,3,regulier
```

1. Zijbalk › **Geavanceerd**: vink "Ik weet zeker dat ik alles wil wissen" aan en klik **Database leegmaken**. Je account blijft bestaan.
2. Ga naar **Importeren**, sleep `lessen.csv` in het vak, bekijk het voorbeeld en klik **Lessen toevoegen**.
3. Ga naar **Rooster** en bereken. De app heeft zelf leraren, lokalen en tijdslots aangemaakt.

Ook Excel-, JSON- en WebUntis-bestanden worden ingelezen.

## 10. Het rooster als leraar bekijken

1. Laad opnieuw de **Gewone school**, bereken het rooster en klik **Opslaan in database**.
2. Ga naar **Gebruikers** en klik **Accounts maken voor alle leraren**. Elke leraar krijgt een account met zijn leraarcode als gebruikersnaam.
3. Klik rechtsboven **Uitloggen** en log in met een leraarcode en wachtwoord `docent123`.
4. Als leraar zie je alleen **Mijn rooster**: je eigen weekrooster, zonder iets te kunnen wijzigen.

Log daarna weer in als roostermaker. Op **Gebruikers** kun je ook zelf accounts aanmaken, een rol of gekoppelde leraar wijzigen en wachtwoorden instellen.

---

## Stoppen

```bash
docker compose down      # stoppen; accounts en rooster blijven bewaard
docker compose down -v   # stoppen en alles wissen
```

Lukt het starten niet? `docker compose logs app` toont wat er misgaat.
