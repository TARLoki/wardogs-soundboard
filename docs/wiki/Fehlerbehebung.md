# Fehlerbehebung

Erste Anlaufstelle: der **Einrichtungs-Check** unter **Anleitung** in der Oberfläche und die Meldungen im Konsolenfenster.

| Problem | Lösung |
|---|---|
| „Python wurde nicht gefunden“ | Python mit Häkchen **„Add python.exe to PATH“** installieren, danach **neues** PowerShell-Fenster. |
| „No module named …“ | Pakete fehlen: im Soundboard-Ordner `python -m pip install -r requirements.txt`. |
| „Smart App Control hat eine Datei blockiert“ | ZIP → Eigenschaften → **„Zulassen“**, neu entpacken. Oder `python soundboard.py` in der PowerShell starten. |
| PowerShell: `cd /d` funktioniert nicht | In der PowerShell heißt es nur `cd "Pfad"` (ohne `/d`). |
| Browser zeigt „Tool nicht erreichbar“ | Soundboard läuft nicht, oder `web.html` wurde ohne laufendes Soundboard geöffnet. Starten und `http://localhost:8765` öffnen. |
| Im Spiel hört niemand die Sounds | Mikrofon im Spiel muss **CABLE Output** sein. Testton abspielen und in `mmsys.cpl` → Aufnahme den Pegel bei CABLE Output prüfen. |
| Konsole meldet „PTT übersprungen“ | WARDOGS war nicht das aktive Fenster. Angezeigten Titel bei `PTT_WINDOW` eintragen – oder Sprachaktivierung nutzen. |
| Numpad reagiert im Spiel nicht | Soundboard als Administrator starten (Rechtsklick auf `start.bat`). |
| Im Spiel hört mich niemand mehr | Das Soundboard muss laufen. Im Einrichtungs-Check muss „Mikrofon gefunden“ grün sein. |
| Discord überträgt die Sounds mit | In Discord ausdrücklich das Mikrofon wählen, nicht „Default“ und nicht CABLE Output. |
| Echo, Pfeifen, ganzer PC-Ton im Mikrofon | `mmsys.cpl`: CABLE darf weder Standard-Wiedergabe- noch Standard-Aufnahmegerät sein. |
| Sounds werden doppelt abgespielt | Beim Mikrofontest im Spiel normal. Sonst prüfen, ob zwei Soundboard-Fenster offen sind (ab 1.8 verhindert). |
| Langer Sound wird abgeschnitten | Grenze ist 90 Sekunden – `MAX_SECONDS` erhöhen. |
| Desktopverknüpfung startet das Soundboard nicht | `launcher.log` ansehen (Zeilen „Fehler“ und „Tipp“, Details in `soundboard_fehler.log`); `python soundboard.py` einmal direkt starten. Wurde der Ordner verschoben, Verknüpfung neu anlegen. |
| Bild-Link: „zeigt nicht direkt auf ein Bild“ | Rechtsklick auf das Bild → „Bildadresse kopieren“ und diese verwenden – oder das Bild kopieren und im Dialog mit Strg+V einfügen. |
| Bild ↑/↓ löst im Spiel etwas aus | Tasten in WARDOGS neu belegen oder `PAGE_KEYS = False` setzen und die Seite in der Oberfläche wechseln. |
| „Aufnahme nicht möglich: Mikrofon läuft nicht“ | Im Einrichtungs-Check muss „Mikrofon gefunden“ grün sein (Schritt 5). |
| „Text-to-Speech fehlgeschlagen“ / keine deutsche Stimme | Einrichtungs-Check → „Sprachausgabe“ ansehen. Deutsche Stimme über Windows-Einstellungen → Zeit und Sprache → Sprache nachinstallieren. |
| Seite „Kommandos“ bleibt leer | Die Vorlage braucht die Windows-Stimme. Danach über ⚙ → „Freie Tasten mit Kommandos füllen“. |
| Meine alten Sounds sind weg | Ab Version 2.0 liegen sie auf der Seite **Eigene** (Ordner `sounds\Eigene`). |
| Myinstants-Link lädt nicht | Auf der Myinstants-Seite den direkten MP3-Link (Download) kopieren und den verwenden. |

Problem nicht dabei? Gerne ein **[Issue](https://github.com/TARLoki/wardogs-soundboard/issues)** anlegen – mit Screenshot des Konsolenfensters.
