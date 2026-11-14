# FAQ

### Ist das ein Cheat? Kann ich gebannt werden?
Das Soundboard verändert das Spiel nicht: keine Spieldateien, kein Speicherzugriff, keine Injektion. Für WARDOGS ist es ein normales Mikrofon (VB-Cable).
Die **automatische Sprechtaste** ist allerdings ein simulierter Tastendruck (wie bei Makro-Software). Das Tool ist **inoffiziell** und **nicht von Bulkhead geprüft** – eine Garantie gibt es nicht. Wer ganz sicher gehen will: `PTT_KEY = None` setzen und im Spiel Sprachaktivierung nutzen.

### Mein Virenscanner warnt – ist das gefährlich?
Das Tool hört global auf Tastendrücke (für die Numpad-Hotkeys) und drückt selbst eine Taste. Für Heuristiken sieht das ähnlich aus wie ein Keylogger. Ausgewertet werden aber nur die Numpad-Tasten, es wird nichts gespeichert oder verschickt – der komplette Quellcode liegt offen in diesem Repository.

### Welche Verbindungen ins Internet gibt es?
Nur wenn du einen Link einfügst: Dann lädt das Tool diese eine Seite bzw. Datei (z. B. von Myinstants). Die Weboberfläche läuft lokal auf deinem PC.

### Warum Python und keine .exe?
Eine selbst gebaute, unsignierte .exe wird von Smart App Control und vielen Virenscannern häufig blockiert. `python.exe` ist dagegen vom Herausgeber (Python Software Foundation) digital signiert und weit verbreitet – der Weg ist robuster.

### Warum braucht es VB-Cable? Geht das nicht ohne?
Nur ein Treiber kann Windows ein zusätzliches Mikrofon bereitstellen. Ein eigener Treiber müsste von Microsoft signiert werden und könnte mit dem Kernel-Anti-Cheat kollidieren. VB-Cable ist erprobt und kostenlos.

### Sind Sounds dabei?
Nein. Viele Meme-Clips stammen aus Filmen, Serien oder Musik. Für den privaten Spaß im Voice-Chat okay – zum Weiterverbreiten oder Streamen nicht ohne Weiteres.

### Gibt es das auf Englisch?
Die Oberfläche ist derzeit deutsch. Eine Kurzanleitung auf Englisch gibt es unter [English](English).
