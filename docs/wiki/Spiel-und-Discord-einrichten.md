# Spiel und Discord einrichten

## WARDOGS

Im Spiel unter **Einstellungen → Audio** (bzw. Sprachchat):

| Einstellung | Wert |
|---|---|
| Mikrofon / Eingabegerät | **CABLE Output (VB-Audio Virtual Cable)** |
| Ausgabegerät | dein Headset (unverändert) |
| Sprachmodus | Push-to-Talk mit **K** oder Sprachaktivierung |
| Mikrofon-Lautstärke | nicht auf 0 – ruhig 100 % |

### Push-to-Talk

Du musst beim Abspielen nichts drücken: Das Soundboard hält die Sprechtaste (Standard **K**) automatisch, solange ein Sound läuft – **nur wenn das WARDOGS-Fenster im Vordergrund ist**.

- Andere Sprechtaste? In `soundboard.py` bei `PTT_KEY` eintragen, siehe [Einstellungen](Einstellungen).
- Meldet die Konsole *„PTT übersprungen, aktives Fenster: …“*, den angezeigten Titel bei `PTT_WINDOW` eintragen.
- Ohne automatischen Tastendruck: `PTT_KEY = None` und im Spiel Sprachaktivierung nutzen.

### Mikrofontest im Spiel

Beim Mikrofontest von WARDOGS hörst du Sounds **doppelt** – einmal sofort (Mithören über das Soundboard) und etwa eine Sekunde später (Rückspielung des Spiels). Das ist richtig so: Der zweite ist das, was deine Mitspieler hören.

## Discord (optional)

Damit Discord nur deine Stimme und nicht die Sounds überträgt:

**Benutzereinstellungen → Sprache & Video → Eingabegerät** ausdrücklich auf dein **Mikrofon** stellen – **nicht** „Default“ und **nicht** CABLE Output.

Weiter mit **[Sounds verwalten](Sounds-verwalten)**.
