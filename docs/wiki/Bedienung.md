# Bedienung

## Tasten

| Taste | Funktion |
|---|---|
| Numpad **0–9** | Sound abspielen |
| Numpad `,` `/` `*` `-` `+` | Sound abspielen (weitere Plätze) |
| **NumLock** | Sound abspielen – NumLock schaltet danach automatisch zurück |
| **gleiche Taste nochmal** | laufenden Sound stoppen |
| Numpad **Enter** | alle Sounds stoppen |
| **Bild ↑ / Bild ↓** | vorherige / nächste Seite (Ansage im eigenen Headset) |

Die Tasten funktionieren unabhängig davon, ob NumLock an oder aus ist.

> Das Soundboard fängt die Tasten **nicht ab** – WARDOGS bekommt sie auch. Ist eine Numpad-Taste im Spiel belegt, löst sie dort zusätzlich ihre Aktion aus.

## Weboberfläche

`http://localhost:8765` – am besten als Lesezeichen. Ein Doppelklick auf `web.html` leitet ebenfalls dorthin weiter, wenn das Soundboard läuft.

- **Klick** auf eine Kachel spielt ab, **nochmal klicken** stoppt.
- **Stopp** und **Lautstärke** oben, darunter die **Reiter der Seiten** mit **＋** (neue Seite) und **⚙** (Seite bearbeiten) – siehe [Seiten und Kommandos](Seiten-und-Kommandos).
- **Anleitung**: Einrichtungs-Check, Testton, Schritt-für-Schritt-Anleitung.

Beim Klicken im Browser ist der Browser das aktive Fenster – die automatische Sprechtaste greift dann nicht. Im Spiel also das **Numpad** nutzen oder vom **Handy** aus bedienen.

## Vom Handy bedienen

1. In `soundboard.py` `WEB_HOST = "0.0.0.0"` setzen und das Soundboard neu starten.
2. Die IP-Adresse des PCs herausfinden (PowerShell: `ipconfig` → IPv4-Adresse).
3. Am Handy im selben WLAN `http://<PC-IP>:8765` öffnen.

Gegebenenfalls fragt die Windows-Firewall beim ersten Start nach – für **private Netzwerke** erlauben.
