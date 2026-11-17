# Einstellungen

Alle Optionen stehen oben in `soundboard.py` im Abschnitt **Konfiguration**. Datei per Rechtsklick → **Öffnen mit** → **Editor** bearbeiten, speichern, Soundboard neu starten.

Gerätenamen anzeigen: `python soundboard.py --list` – bei Gerätenamen reicht immer ein Teil, Groß-/Kleinschreibung egal.

## Audio

| Option | Standard | Bedeutung |
|---|---|---|
| `CABLE_DEVICE` | `"CABLE Input"` | Name des VB-Cable-Wiedergabegeräts |
| `MIC_PASSTHROUGH` | `True` | Mikrofon mit ins Kabel mischen |
| `MIC_DEVICE` | `None` | Mikrofon; `None` = Windows-Standard, sonst z. B. `"QuadCast"` |
| `MIC_VOLUME` | `1.0` | Lautstärke des Mikrofons |
| `MONITOR` | `True` | Sounds selbst über das Headset mithören |
| `MONITOR_DEVICE` | `None` | Ausgabe zum Mithören; `None` = Windows-Standard |
| `MONITOR_VOLUME` | `0.4` | Lautstärke beim Mithören |

## Sounds

| Option | Standard | Bedeutung |
|---|---|---|
| `SOUND_VOLUME` | `0.7` | Startlautstärke (1.0 = 100 %) |
| `MAX_VOLUME` | `2.0` | Obergrenze des Reglers (200 %) |
| `NORMALIZE` | `True` | leise Sounds beim Laden anheben |
| `LIMIT_THRESHOLD` | `0.7` | ab hier rundet der Soft-Limiter Spitzen ab |
| `EXCLUSIVE` | `True` | neuer Sound beendet laufende Sounds |
| `MAX_SECONDS` | `90` | längere Sounds werden gekürzt |
| `KEEP_NUMLOCK` | `True` | NumLock nach Druck zurückschalten |
| `RECORD_MAX_SECONDS` | `30` | Aufnahmen enden spätestens nach dieser Zeit |

## Seiten und Sprachausgabe

| Option | Standard | Bedeutung |
|---|---|---|
| `PAGE_KEYS` | `True` | Bild ↑ / Bild ↓ wechseln die Seite |
| `ANNOUNCE_PAGES` | `True` | Seitenname beim Wechsel im eigenen Headset ansagen (ohne Windows-Stimme: kurze Töne) |
| `TTS_LANG` | `"de"` | Sprache der Windows-Stimme für Text-to-Speech und Ansagen |
| `TTS_RATE` | `0` | Sprechtempo von -10 (langsam) bis 10 (schnell) |

## Push-to-Talk

| Option | Standard | Bedeutung |
|---|---|---|
| `PTT_KEY` | `"k"` | Sprechtaste im Spiel; `None` = automatischen Tastendruck abschalten |
| `PTT_WINDOW` | `"WARDOGS"` | nur drücken, wenn ein Fenster mit diesem Titel aktiv ist; `None` = immer |
| `PTT_PREROLL` | `0.15` | Sekunden zwischen Tastendruck und Soundstart |
| `PTT_TAIL` | `0.25` | Sekunden, die die Taste nach Soundende gehalten wird |

## Weboberfläche

| Option | Standard | Bedeutung |
|---|---|---|
| `WEB_HOST` | `"127.0.0.1"` | `"0.0.0.0"` = auch vom Handy im Heimnetz erreichbar |
| `WEB_PORT` | `8765` | Port der Oberfläche |
| `OPEN_BROWSER` | `True` | Browser beim Start öffnen |

## Updates

| Option | Standard | Bedeutung |
|---|---|---|
| `CHECK_UPDATES` | `True` | beim Start und alle 12 Stunden bei GitHub nach einer neuen Version fragen |
| `UPDATE_INTERVAL` | `43200` | Sekunden zwischen zwei Prüfungen (12 Stunden) |

Gibt es eine neuere Version, erscheint oben in der Oberfläche ein grüner Hinweis mit Download-Link (pro Version ausblendbar), außerdem ein Eintrag im Einrichtungs-Check und in der Konsole. **Installiert wird nichts automatisch.**

## Desktopverknüpfung (`wardogs_start.pyw`)

| Option | Standard | Bedeutung |
|---|---|---|
| `OPEN_URLS` | Soundboard, n4lab, wardogs.zone | Seiten, die beim Start als Browser-Tabs geöffnet werden; `[]` = keine |
| `AUTO_QUIT` | `True` | Soundboard beenden, wenn WARDOGS geschlossen wird |
| `GONE_GRACE` | `20` | Sekunden, die das Spiel weg sein muss |
| `WAIT_FOR_GAME` | `900` | maximale Wartezeit auf den Spielstart (Steam-Updates) |
| `PORT` | `8765` | muss zu `WEB_PORT` passen |

## Befehlszeile

| Befehl | Wirkung |
|---|---|
| `python soundboard.py` | Soundboard starten |
| `python soundboard.py --list` | Audiogeräte auflisten |
| `python soundboard.py --no-browser` | ohne Browserfenster starten |
