# Desktopverknüpfung

Startet Soundboard und WARDOGS mit einem Doppelklick.

## Anlegen

Im Soundboard-Ordner auf `verknuepfung_anlegen.py` doppelklicken. Auf dem Desktop erscheint **„WARDOGS + Soundboard“** mit dem WARDOGS-Symbol.

## Was passiert beim Start

1. Das Soundboard startet **minimiert** in der Taskleiste, ohne Browser. Läuft es schon, wird es nicht doppelt gestartet.
2. WARDOGS startet **über Steam** (`steam://rungameid/1867240`) – mit Launcher, Anti-Cheat und Updates wie gewohnt.
3. Wird WARDOGS geschlossen, beendet sich das Soundboard nach etwa **20 Sekunden** von selbst.

Die Oberfläche erreichst du über dein Lesezeichen `http://localhost:8765`.

> ⚠️ **Nicht die Spieldatei direkt starten.** Verknüpfungen auf `WardogsClient-Win64-Shipping.exe` umgehen Launcher und Anti-Cheat – das Spiel startet dann meist nicht.

## Protokoll

Jeder Start schreibt `launcher.log` in den Soundboard-Ordner: ob das Soundboard gestartet wurde, welche WARDOGS-Prozesse erkannt wurden und wann beendet wurde. Wurde der Ordner verschoben, die Verknüpfung neu anlegen.

Einstellungen dazu stehen oben in `wardogs_start.pyw` (siehe [Einstellungen](Einstellungen)).
