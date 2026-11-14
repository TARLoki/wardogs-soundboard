"""
WARDOGS Soundboard
==================
Spielt Sounddateien per Numpad-Hotkey oder Weboberfläche in ein virtuelles
Audiokabel (VB-Cable). Das eigene Mikrofon wird mit durchgeschleift.
Im Spiel wird "CABLE Output" als Mikrofon gewählt.

Das Spiel selbst wird nicht verändert: kein Dateizugriff, kein Prozesszugriff.

Weboberfläche:  http://localhost:8765
  - 16 Knöpfe wie auf dem Numpad abspielen, Stopp, Lautstärke
  - Myinstants-Link (oder direkter MP3-Link) einfügen -> wird heruntergeladen
    und auf den gewählten Platz gelegt
  - Eigene Datei per Drag & Drop auf einen Platz ziehen

Push-to-Talk:
  Beim Abspielen wird die Spieltaste (PTT_KEY, Standard "k") automatisch gehalten,
  bis der Sound zu Ende ist - aber nur, wenn das WARDOGS-Fenster aktiv ist.

Seiten:
  Beliebig viele Seiten (z. B. „Kommandos“, „Eigene“) mit je 16 Tasten. Jede Seite
  liegt in einem eigenen Unterordner von sounds/. Neue Seiten können mit der Vorlage
  „Kommandos“ (Text-to-Speech mit Funk-Effekt) angelegt werden.

Tasten (egal ob NumLock an oder aus):
  Numpad 0-9 , / * - + NumLock   je ein Sound (16 Plätze pro Seite)
  Gleiche Taste nochmal          laufenden Sound stoppen
  Numpad Enter                   alle Sounds stoppen
  Bild ↑ / Bild ↓                vorherige / nächste Seite (Ansage im eigenen Headset)
  Strg+C                         Beenden (im Konsolenfenster)
  Lautstärke und Neuladen gibt es in der Weboberfläche.
  NumLock wird nach dem Drücken automatisch zurückgeschaltet.

Einrichtung:
  Beim Start prüft das Tool VB-Cable, Mikrofon, Ausgabe und Hotkeys. Fehlt etwas,
  öffnet sich die Weboberfläche mit der Anleitung (Menüpunkt "Anleitung").

Updates:
  Beim Start und alle 12 Stunden fragt das Tool bei GitHub die neueste Version ab und
  zeigt einen Hinweis mit Download-Link. Installiert wird nichts automatisch.
  Abschalten: CHECK_UPDATES = False.

Platzbelegung:
  Dateien mit Präfix landen fest auf diesem Platz, z. B. "3_leeroy.mp3",
  "0_...", "komma_...", "geteilt_...", "mal_...", "minus_...", "plus_...", "num_...".
  Dateien ohne Präfix füllen freie Plätze alphabetisch.
  Ersetzte Sounds werden nicht gelöscht, sondern nach sounds/<Seite>/_alt verschoben.

Quellen für Sounds:
  Myinstants-/MP3-Link, eigene Datei, Aufnahme übers Mikrofon oder Text → Sprache
  (Windows-Stimme). Optional mit Funk-Effekt.

Bilder und Emojis:
  Jede Taste kann ein Bild (als Kachelhintergrund) oder ein Emoji bekommen. Es hängt am
  Sound und wird beim Austausch zurückgesetzt. Alle Bilder bleiben in sounds/images und
  lassen sich im Dialog aus der Bibliothek wiederverwenden.

Titel:
  Automatisch aus Myinstants-Seitentitel, Datei-Metadaten oder Dateinamen.
  Eigene Titel stehen in sounds/<Seite>/labels.json und verfallen, wenn die Datei getauscht wird.

Aufruf:
  python soundboard.py               Soundboard starten
  python soundboard.py --list        Audiogeräte auflisten
  python soundboard.py --no-browser  ohne Browserfenster starten

Desktopverknüpfung:
  verknuepfung_anlegen.py doppelklicken -> "WARDOGS + Soundboard" auf dem Desktop.
  Startet das Soundboard minimiert, dann WARDOGS über Steam, und beendet das
  Soundboard, sobald das Spiel geschlossen wird (siehe wardogs_start.pyw).
"""

import collections
import hashlib
import html as htmllib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import keyboard
import numpy as np
import sounddevice as sd
import soundfile as sf

VERSION = "2.0"

# ============================ Konfiguration ============================

BASE_DIR = Path(__file__).parent
SOUND_DIR = BASE_DIR / "sounds"            # je Seite ein Unterordner, z. B. sounds/Kommandos
PAGES_FILE = SOUND_DIR / "pages.json"      # Reihenfolge und Namen der Seiten
IMG_DIR = SOUND_DIR / "images"             # Bildbibliothek (bleibt erhalten)
CACHE_DIR = SOUND_DIR / ".cache"           # Seitenansagen (Text-to-Speech)
TRASH_DIR = SOUND_DIR / "_geloeschte_Seiten"
MAX_IMAGE_BYTES = 3 * 1024 * 1024
EXTENSIONS = {".wav", ".ogg", ".flac", ".mp3"}

CABLE_DEVICE = "CABLE Input"   # Namensteil des VB-Cable-Wiedergabegeräts

MIC_PASSTHROUGH = True         # eigenes Mikrofon mit ins Kabel mischen
MIC_DEVICE = None              # None = Windows-Standardmikrofon, sonst Namensteil, z. B. "QuadCast"
MIC_VOLUME = 1.0

MONITOR = True                 # Sounds selbst mithören
MONITOR_DEVICE = None          # None = Windows-Standardausgabe, sonst Namensteil
MONITOR_VOLUME = 0.4

SOUND_VOLUME = 0.7             # Startlautstärke der Sounds (0.0 - 2.0, 1.0 = 100 %)
MAX_VOLUME = 2.0               # Obergrenze des Reglers (2.0 = 200 %)
NORMALIZE = True               # leise Sounds beim Laden auf vollen Pegel anheben
NORMALIZE_PEAK = 0.89          # Zielpegel der Spitzen (0.89 = -1 dBFS)
LIMIT_THRESHOLD = 0.7          # ab hier rundet der Soft-Limiter Spitzen weich ab
EXCLUSIVE = True               # True = neuer Sound beendet laufende Sounds
MAX_SECONDS = 90               # längere Sounds werden abgeschnitten (Schutz vor ganzen Liedern)

KEEP_NUMLOCK = True            # NumLock nach Druck auf die NumLock-Taste zurückschalten

PAGE_KEYS = True               # Bild ↑ / Bild ↓ wechseln die Seite
ANNOUNCE_PAGES = True          # beim Wechsel den Seitennamen im eigenen Headset ansagen
TTS_LANG = "de"                # Sprache der Windows-Stimme für Text-to-Speech und Ansagen
TTS_RATE = 0                   # Sprechtempo -10 (langsam) bis 10 (schnell)
RECORD_MAX_SECONDS = 30        # Aufnahmen enden spätestens nach dieser Zeit

PTT_KEY = "k"                  # Push-to-Talk-Taste im Spiel, None = abschalten
PTT_WINDOW = "WARDOGS"         # nur drücken, wenn dieses Fenster aktiv ist (None = immer)
PTT_PREROLL = 0.15             # Sekunden zwischen Tastendruck und Soundstart
PTT_TAIL = 0.25                # Sekunden, die die Taste nach Soundende noch gehalten wird

CONSOLE_TITLE = "WARDOGS Soundboard"   # Fenstertitel (wird vom Startskript zum Minimieren gesucht)

WEB_HOST = "127.0.0.1"         # "0.0.0.0" = auch vom Handy im Heimnetz erreichbar
WEB_PORT = 8765
OPEN_BROWSER = True

CHECK_UPDATES = True           # bei GitHub nachsehen, ob es eine neuere Version gibt
UPDATE_REPO = "TARLoki/wardogs-soundboard"
UPDATE_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_INTERVAL = 12 * 3600    # Sekunden zwischen zwei Prüfungen

SAMPLE_RATE = 48000
BLOCK = 480                    # 10 ms

# =======================================================================

# Plätze: (Tastenbeschriftung, Dateipräfix, Scan-Code der Numpad-Taste)
# Scan-Codes sind unabhängig von NumLock und Tastaturlayout.
SLOTS = [
    ("1", "1", 79), ("2", "2", 80), ("3", "3", 81),
    ("4", "4", 75), ("5", "5", 76), ("6", "6", 77),
    ("7", "7", 71), ("8", "8", 72), ("9", "9", 73),
    ("0", "0", 82), (",", "komma", 83),
    ("/", "geteilt", 53), ("*", "mal", 55), ("-", "minus", 74), ("+", "plus", 78),
    ("Num", "num", 69),
]
NSLOTS = len(SLOTS)
SCAN_TO_SLOT = {sc: i for i, (_, _, sc) in enumerate(SLOTS)}
PREFIX_TO_SLOT = {pre: i for i, (_, pre, _) in enumerate(SLOTS)}
STOP_SCAN = 28                 # Numpad Enter
NUMLOCK_SCAN = 69
PAGE_UP_SCAN, PAGE_DOWN_SCAN = 73, 81   # eigene Bild-Tasten (nicht Numpad 9/3)
RESERVED_DIRS = {"images", "_alt", ".cache", "_geloeschte_Seiten"}

# Vorlage für eine neue Seite „Kommandos“ (Taste, Text) – per Text-to-Speech mit Funk-Effekt
COMMAND_TEMPLATE = [
    ("7", "Feind links!"), ("8", "Feind voraus!"), ("9", "Feind rechts!"),
    ("4", "Deckung!"), ("5", "Position halten!"), ("6", "Granate!"),
    ("1", "Mir nach!"), ("2", "Feind hinter uns!"), ("3", "Brauche Sanitäter!"),
    ("0", "Verstanden!"), (",", "Negativ!"),
    ("/", "Nachladen!"), ("*", "Brauche Munition!"), ("-", "Rückzug!"), ("+", "Freund, nicht schießen!"),
    ("Num", "Scharfschütze!"),
]
PREFIX = re.compile(r"^(" + "|".join(PREFIX_TO_SLOT) + r")[_\- ]", re.I)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WARDOGS-Soundboard"


# ----------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------

def match_device(name: str, output: bool):
    """Gerät per Namensteil suchen, MME bevorzugen (resampelt automatisch). None = nicht gefunden."""
    key = "max_output_channels" if output else "max_input_channels"
    apis = sd.query_hostapis()
    hits = []
    for i, d in enumerate(sd.query_devices()):
        if d[key] > 0 and name.lower() in d["name"].lower():
            hits.append((apis[d["hostapi"]]["name"] != "MME", i))
    return sorted(hits)[0][1] if hits else None


def device_name(idx, output: bool):
    """Name des Geräts idx bzw. des Windows-Standardgeräts (idx=None). None = keins vorhanden."""
    try:
        if idx is None:
            return sd.query_devices(kind="output" if output else "input")["name"]
        return sd.query_devices(idx)["name"]
    except Exception:
        return None


def load_sound(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    data = data[: int(sr * MAX_SECONDS)]
    data = np.repeat(data, 2, axis=1) if data.shape[1] == 1 else data[:, :2]
    if sr != SAMPLE_RATE:
        n = int(round(len(data) * SAMPLE_RATE / sr))
        old = np.linspace(0, 1, len(data), endpoint=False)
        new = np.linspace(0, 1, n, endpoint=False)
        data = np.stack([np.interp(new, old, data[:, c]) for c in range(2)], axis=1)
    if NORMALIZE:
        peak = float(np.max(np.abs(data))) if len(data) else 0.0
        if peak > 1e-4:
            data = data * (NORMALIZE_PEAK / peak)
    return np.ascontiguousarray(data, dtype=np.float32)


def soft_limit(x: np.ndarray, t: float = LIMIT_THRESHOLD) -> np.ndarray:
    """Weiche Begrenzung: unter t unverändert, darüber sanft gegen 1.0 abgerundet (kein hartes Kratzen)."""
    a = np.abs(x)
    over = a > t
    if over.any():
        x = x.copy()
        x[over] = np.sign(x[over]) * (t + (1 - t) * np.tanh((a[over] - t) / (1 - t)))
    return x


def meta_title(path: Path):
    """Titel aus den Datei-Metadaten (WAV/OGG/FLAC, je nach libsndfile auch MP3)."""
    try:
        with sf.SoundFile(str(path)) as f:
            t = (getattr(f, "title", "") or "").strip()
    except Exception:
        return None
    return t if 0 < len(t) <= 60 else None


def display_name(path: Path) -> str:
    stem = PREFIX.sub("", path.stem)
    return stem.replace("_", " ").replace("-", " ").strip() or path.stem


class Player:
    """Mischt laufende Sounds blockweise zusammen."""

    def __init__(self):
        self.voices = []
        self.lock = threading.Lock()

    def play(self, data, slot, exclusive=None):
        with self.lock:
            if EXCLUSIVE if exclusive is None else exclusive:
                self.voices.clear()
            self.voices.append([data, 0, slot])

    def stop(self):
        with self.lock:
            self.voices.clear()

    def active_slots(self):
        with self.lock:
            return [k for k in {v[2] for v in self.voices} if k is not None]

    def mix(self, frames: int) -> np.ndarray:
        out = np.zeros((frames, 2), np.float32)
        with self.lock:
            alive = []
            for v in self.voices:
                data, pos, _ = v
                chunk = data[pos:pos + frames]
                out[:len(chunk)] += chunk
                v[1] = pos + len(chunk)
                if v[1] < len(data):
                    alive.append(v)
            self.voices = alive
        return out


class MicBuffer:
    """Kleiner FIFO zwischen Mikrofon- und Kabel-Stream."""

    def __init__(self, max_frames: int):
        self.buf = collections.deque()
        self.count = 0
        self.max = max_frames
        self.lock = threading.Lock()

    def push(self, block: np.ndarray):
        with self.lock:
            self.buf.append(block.copy())
            self.count += len(block)
            while self.count > self.max:          # Latenz begrenzen
                self.count -= len(self.buf.popleft())

    def pull(self, frames: int) -> np.ndarray:
        out = np.zeros(frames, np.float32)
        filled = 0
        with self.lock:
            while filled < frames and self.buf:
                blk = self.buf[0]
                take = min(len(blk), frames - filled)
                out[filled:filled + take] = blk[:take]
                filled += take
                self.count -= take
                if take == len(blk):
                    self.buf.popleft()
                else:
                    self.buf[0] = blk[take:]
        return out


# ----------------------------------------------------------------------
# Push-to-Talk: Spieltaste automatisch halten, solange ein Sound läuft
# ----------------------------------------------------------------------

def foreground_title() -> str:
    if sys.platform != "win32":
        return ""
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


class PushToTalk:
    def __init__(self, key: str):
        self.key = key
        self.lock = threading.Lock()
        self.held = False          # Taste wird gerade von uns gehalten
        self.release_at = 0.0
        self.timer = None

    def begin(self, seconds: float) -> float:
        """Taste drücken (falls nötig). Gibt die Vorlaufzeit zurück, um die der Sound warten soll."""
        if PTT_WINDOW:
            title = foreground_title()
            if PTT_WINDOW.lower() not in title.lower():
                print(f"  (PTT übersprungen, aktives Fenster: \"{title}\")")
                return 0.0
        with self.lock:
            pre = 0.0
            if not self.held:
                if keyboard.is_pressed(self.key):     # du hältst die Taste gerade selbst
                    return 0.0
                keyboard.press(self.key)
                self.held = True
                pre = PTT_PREROLL
            end = time.monotonic() + pre + seconds + PTT_TAIL
            self.release_at = end if EXCLUSIVE else max(self.release_at, end)
            self._arm()
            return pre

    def _arm(self):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(max(0.0, self.release_at - time.monotonic()), self._check)
        self.timer.daemon = True
        self.timer.start()

    def _check(self):
        with self.lock:
            if self.held and time.monotonic() >= self.release_at - 0.02:
                keyboard.release(self.key)
                self.held = False

    def release_now(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            if self.held:
                keyboard.release(self.key)
                self.held = False


# ----------------------------------------------------------------------
# Einrichtungs-Check
# ----------------------------------------------------------------------

class Setup:
    """Sammelt die Prüfergebnisse. status: ok | warn | error | info"""
    ORDER = ["python", "packages", "cable", "monitor", "mic", "audio", "hotkeys", "tts", "sounds", "update"]

    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()

    def set(self, cid, status, label, detail=""):
        with self.lock:
            self.items[cid] = {"id": cid, "status": status, "label": label, "detail": detail}

    def list(self):
        with self.lock:
            return [self.items[c] for c in self.ORDER if c in self.items]

    def issues(self):
        return sum(1 for i in self.list() if i["status"] in ("warn", "error"))

    def print(self):
        mark = {"ok": "[OK]", "warn": "[ ! ]", "error": "[ X ]", "info": "[ i ]"}
        print("\nEinrichtungs-Check:")
        for i in self.list():
            print(f"  {mark[i['status']]:6} {i['label']}")
            if i["status"] in ("warn", "error") and i["detail"]:
                print(f"         {i['detail']}")
        print()


def check_devices(setup: Setup, refresh=False) -> dict:
    """Prüft Audiogeräte und liefert die zu verwendenden Geräte-Indizes."""
    if refresh:                                    # Geräteliste neu einlesen
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass
    devs = {"cable": None, "mic": None, "mic_ok": False, "monitor": None, "monitor_ok": False}

    # --- VB-Cable ---
    cab_out = match_device(CABLE_DEVICE, output=True)
    cab_in = match_device("CABLE Output", output=False)
    devs["cable"] = cab_out
    if cab_out is None:
        setup.set("cable", "error", "VB-Cable nicht gefunden",
                  "Das Wiedergabegerät „CABLE Input“ fehlt. VB-Cable installieren und den Rechner neu starten (Schritt 3).")
    elif cab_in is None:
        setup.set("cable", "warn", "VB-Cable unvollständig",
                  "„CABLE Output“ fehlt als Aufnahmegerät – in mmsys.cpl → Aufnahme prüfen, ob es deaktiviert ist.")
    else:
        setup.set("cable", "ok", "VB-Cable gefunden", device_name(cab_out, True))

    # --- Ausgabe zum Mithören ---
    if not MONITOR:
        setup.set("monitor", "info", "Mithören ist ausgeschaltet", "MONITOR = False")
    else:
        idx = match_device(MONITOR_DEVICE, output=True) if MONITOR_DEVICE else None
        name = device_name(idx, True)
        if MONITOR_DEVICE and idx is None:
            setup.set("monitor", "warn", f"Ausgabe „{MONITOR_DEVICE}“ nicht gefunden",
                      f"Verwende Windows-Standardausgabe: {name}")
        if name is None:
            setup.set("monitor", "error", "Keine Audioausgabe gefunden", "Headset anschließen bzw. in mmsys.cpl aktivieren.")
        elif "cable" in name.lower():
            setup.set("monitor", "error", "Windows-Standardausgabe ist das VB-Cable",
                      "Dann landet der ganze PC-Ton im Mikrofon. In mmsys.cpl → Wiedergabe das Headset als Standard festlegen (Schritt 4).")
        elif not (MONITOR_DEVICE and idx is None):
            setup.set("monitor", "ok", "Mithören über Headset/Lautsprecher", name)
        devs["monitor"] = idx
        devs["monitor_ok"] = name is not None and "cable" not in name.lower()

    # --- Mikrofon ---
    if not MIC_PASSTHROUGH:
        setup.set("mic", "info", "Mikrofon-Durchleitung ist ausgeschaltet", "MIC_PASSTHROUGH = False")
    else:
        idx = match_device(MIC_DEVICE, output=False) if MIC_DEVICE else None
        name = device_name(idx, False)
        devs["mic"] = idx
        if name is None:
            setup.set("mic", "error", "Kein Mikrofon gefunden", "Mikrofon anschließen und Soundboard neu starten.")
        elif "cable" in name.lower():
            setup.set("mic", "error", "Mikrofon ist das VB-Cable (Rückkopplung)",
                      (f"„{MIC_DEVICE}“ wurde nicht gefunden und das " if MIC_DEVICE else "Das ")
                      + "Windows-Standardmikrofon ist CABLE Output. In mmsys.cpl → Aufnahme dein Mikrofon "
                      "als Standard festlegen oder MIC_DEVICE in soundboard.py eintragen (Schritt 4/5).")
        elif MIC_DEVICE and idx is None:
            devs["mic_ok"] = True
            setup.set("mic", "warn", f"Mikrofon „{MIC_DEVICE}“ nicht gefunden",
                      f"Verwende Windows-Standardmikrofon: {name}. MIC_DEVICE anpassen (Schritt 5).")
        else:
            devs["mic_ok"] = True
            setup.set("mic", "ok", "Mikrofon gefunden", name)
    return devs


class AudioEngine:
    """Öffnet die Audio-Streams: Kabel (Sounds + Mikrofon), Mikrofon, Mithören."""

    def __init__(self, board):
        self.board = board
        self.mic = MicBuffer(BLOCK * 6) if MIC_PASSTHROUGH else None
        self.mic_active = False
        self.streams = []

    def _cable_cb(self, outdata, frames, _t, _status):
        mix = soft_limit(self.board.cable.mix(frames) * self.board.volume)
        if self.mic_active:
            mix += (self.mic.pull(frames) * MIC_VOLUME)[:, None]
        np.clip(mix, -1.0, 1.0, out=mix)
        outdata[:] = mix

    def _monitor_cb(self, outdata, frames, _t, _status):
        mix = soft_limit(self.board.monitor.mix(frames) * self.board.volume) * MONITOR_VOLUME
        np.clip(mix, -1.0, 1.0, out=mix)
        outdata[:] = mix

    def _mic_cb(self, indata, _frames, _t, _status):
        self.mic.push(indata[:, 0])
        self.board.rec_push(indata[:, 0])

    def start(self, devs) -> bool:
        setup = self.board.setup
        if devs["cable"] is None:
            setup.set("audio", "error", "Audio nicht gestartet",
                      "Ohne VB-Cable kann das Soundboard nichts ins Spiel schicken.")
            return False
        streams = []
        try:
            streams.append(sd.OutputStream(device=devs["cable"], samplerate=SAMPLE_RATE, channels=2,
                                           blocksize=BLOCK, dtype="float32", callback=self._cable_cb))
            if self.mic and devs["mic_ok"]:
                streams.append(sd.InputStream(device=devs["mic"], samplerate=SAMPLE_RATE, channels=1,
                                              blocksize=BLOCK, dtype="float32", callback=self._mic_cb))
            if self.board.monitor and devs["monitor_ok"]:
                streams.append(sd.OutputStream(device=devs["monitor"], samplerate=SAMPLE_RATE, channels=2,
                                               blocksize=BLOCK, dtype="float32", callback=self._monitor_cb))
            for st in streams:
                st.start()
        except Exception as e:
            for st in streams:
                try:
                    st.close()
                except Exception:
                    pass
            setup.set("audio", "error", "Audio konnte nicht gestartet werden", str(e))
            return False
        self.streams = streams
        self.mic_active = bool(self.mic and devs["mic_ok"])
        self.board.mic_ready = self.mic_active
        self.board.audio_ready = True
        detail = "Sounds" + (" + Mikrofon" if self.mic_active else " (ohne Mikrofon!)") + " → VB-Cable"
        setup.set("audio", "ok" if self.mic_active or not MIC_PASSTHROUGH else "warn", "Audio läuft", detail)
        return True

    def stop(self):
        for st in self.streams:
            try:
                st.stop()
                st.close()
            except Exception:
                pass
        self.streams = []
        self.board.audio_ready = False


def check_static(setup: Setup, board):
    setup.set("python", "ok", f"Python {sys.version.split()[0]}", sys.executable)
    setup.set("packages", "ok", "Python-Pakete installiert", "numpy, sounddevice, soundfile, keyboard")
    n = sum(1 for p in board.pages for s in p.slots if s)
    if n:
        setup.set("sounds", "ok", f"{n} Sound(s) auf {len(board.pages)} Seite(n)")
    else:
        setup.set("sounds", "warn", "Noch keine Sounds belegt",
                  "Über ✎ einen Myinstants-Link einfügen oder eine Datei auf eine Kachel ziehen (Schritt 9).")


# ----------------------------------------------------------------------
# Bilder
# ----------------------------------------------------------------------

IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
IMAGE_NAME = re.compile(r"^[0-9a-f]{16}\.(png|jpg|gif|webp)$")


def image_type(data: bytes):
    """Bildformat anhand der Dateisignatur erkennen (nicht anhand des Namens)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, data: dict):
    try:
        path.parent.mkdir(exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        print(f"  ! {path.name} konnte nicht gespeichert werden: {e}")


def clean_emoji(text: str):
    text = (text or "").strip()
    if not text or len(text) > 16 or any(c in text for c in "<>&\"'"):
        return None
    return text


# ----------------------------------------------------------------------
# Sprachausgabe (Windows) und Funk-Effekt
# ----------------------------------------------------------------------

TTS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$items = $env:SB_ITEMS | ConvertFrom-Json
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like ($env:SB_LANG + '*') } | Select-Object -First 1
if ($voice) { $s.SelectVoice($voice.VoiceInfo.Name) }
$s.Rate = [int]$env:SB_RATE
foreach ($it in $items) {
  $s.SetOutputToWaveFile($it.out)
  $s.Speak($it.text)
}
$s.SetOutputToNull()
$s.Dispose()
"""

TTS_VOICES_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo.Culture.Name + '|' + $_.VoiceInfo.Name }
$s.Dispose()
"""

NO_WINDOW = 0x08000000


def tts_available() -> bool:
    return sys.platform == "win32"


def _powershell(script, env_extra, timeout):
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                           "-Command", script], env=env, capture_output=True, timeout=timeout,
                          creationflags=NO_WINDOW if sys.platform == "win32" else 0)


def tts_batch(items):
    """items = [(text, Path)] -> erzeugt WAV-Dateien mit der Windows-Sprachausgabe."""
    if not tts_available():
        raise ValueError("Text-to-Speech gibt es nur unter Windows")
    payload = json.dumps([{"text": t, "out": str(p)} for t, p in items])
    r = _powershell(TTS_SCRIPT, {"SB_ITEMS": payload, "SB_LANG": TTS_LANG, "SB_RATE": str(TTS_RATE)},
                    timeout=20 + 6 * len(items))
    missing = [str(p) for _, p in items if not Path(p).exists() or Path(p).stat().st_size < 1000]
    if missing:
        err = r.stderr.decode("utf-8", "ignore").strip().splitlines()
        raise ValueError("Text-to-Speech fehlgeschlagen" + (f": {err[-1]}" if err else ""))


def tts_voices():
    """[(Kultur, Name)] der installierten Windows-Stimmen."""
    if not tts_available():
        return []
    r = _powershell(TTS_VOICES_SCRIPT, {}, timeout=20)
    out = r.stdout.decode("utf-8", "ignore")
    return [tuple(line.split("|", 1)) for line in out.splitlines() if "|" in line]


def check_tts(setup):
    if not tts_available():
        setup.set("tts", "info", "Text-to-Speech nur unter Windows verfügbar")
        return
    try:
        voices = tts_voices()
    except Exception as e:
        setup.set("tts", "warn", "Sprachausgabe nicht verfügbar", str(e))
        return
    lang = [v for v in voices if v[0].lower().startswith(TTS_LANG.lower())]
    if lang:
        setup.set("tts", "ok", "Sprachausgabe bereit", lang[0][1])
    elif voices:
        setup.set("tts", "warn", f"Keine Stimme für „{TTS_LANG}“ installiert",
                  f"Verwendet wird {voices[0][1]}. Weitere Stimmen: Windows-Einstellungen → Zeit und Sprache → Sprache.")
    else:
        setup.set("tts", "warn", "Keine Windows-Stimme gefunden", "Text-to-Speech und Seitenansage sind nicht möglich.")


def _bandpass(x, lo, hi):
    n = len(x)
    if n < 16:
        return x
    spec = np.fft.rfft(x)
    f = np.maximum(np.fft.rfftfreq(n, 1 / SAMPLE_RATE), 1.0)
    gain = 1 / (1 + (lo / f) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(spec * gain, n)


def radio_effect(data: np.ndarray) -> np.ndarray:
    """Klang wie über Funk: Bandpass, leichte Sättigung, Rauschen, Klick am Anfang, „Ksch“ am Ende."""
    x = data.mean(axis=1).astype(np.float64)
    x = _bandpass(x, 350.0, 3200.0)
    peak = float(np.max(np.abs(x))) or 1.0
    x = np.tanh(x / peak * 2.4) / np.tanh(2.4)
    rng = np.random.default_rng(7)
    x = x + _bandpass(rng.normal(0, 0.03, len(x)), 500.0, 3000.0)
    click = np.zeros(int(0.05 * SAMPLE_RATE))
    click[:int(0.008 * SAMPLE_RATE)] = _bandpass(rng.normal(0, 0.6, int(0.008 * SAMPLE_RATE)), 800, 4000)
    tail_n = int(0.16 * SAMPLE_RATE)
    tail = _bandpass(rng.normal(0, 0.35, tail_n), 600.0, 4500.0) * np.linspace(1, 0, tail_n) ** 1.5
    y = np.concatenate([click, x, tail])
    y = y / (float(np.max(np.abs(y))) or 1.0) * NORMALIZE_PEAK
    return np.ascontiguousarray(np.repeat(y[:, None], 2, axis=1), dtype=np.float32)


def wav_bytes(mono: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, mono.astype(np.float32), SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def trim_silence(mono: np.ndarray) -> np.ndarray:
    a = np.abs(mono)
    if not len(a):
        raise ValueError("Nichts aufgenommen")
    thr = max(0.015, float(a.max()) * 0.08)
    idx = np.nonzero(a > thr)[0]
    if not len(idx):
        raise ValueError("Nichts aufgenommen – war das Mikrofon zu leise?")
    start = max(0, idx[0] - int(0.08 * SAMPLE_RATE))
    end = min(len(mono), idx[-1] + int(0.15 * SAMPLE_RATE))
    return mono[start:end]


def beeps(n: int) -> np.ndarray:
    """n kurze Töne (Rückfall für die Seitenansage)."""
    t = np.arange(int(0.09 * SAMPLE_RATE)) / SAMPLE_RATE
    tone = 0.4 * np.sin(2 * np.pi * 990 * t) * np.minimum(1, np.minimum(t, t[-1] - t) / 0.01)
    gap = np.zeros(int(0.08 * SAMPLE_RATE))
    y = np.concatenate([np.concatenate([tone, gap]) for _ in range(max(1, min(n, 6)))])
    return np.ascontiguousarray(np.repeat(y[:, None], 2, axis=1), dtype=np.float32)


# ----------------------------------------------------------------------
# Seiten: je Seite 16 Tasten mit eigenen Sounds, Titeln, Bildern, Effekten
# ----------------------------------------------------------------------

def slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name.strip()).strip("_")[:40]
    return s or "Seite"


class Page:
    def __init__(self, board, pid, name, template=None, filled=False):
        self.board = board
        self.id = pid
        self.name = name
        self.template = template
        self.filled = filled
        self.dir = SOUND_DIR / pid
        self.slots = [None] * NSLOTS
        self.dir.mkdir(parents=True, exist_ok=True)
        self.labels = {str(k): str(v) for k, v in read_json(self.dir / "labels.json").items() if str(v).strip()}
        self.art = read_json(self.dir / "art.json")
        self.fx = read_json(self.dir / "fx.json")

    def meta(self):
        return {"id": self.id, "name": self.name, "template": self.template, "filled": self.filled}

    def _save(self):
        write_json(self.dir / "labels.json", self.labels)
        write_json(self.dir / "art.json", self.art)
        write_json(self.dir / "fx.json", self.fx)

    def slot(self, idx):
        s = self.slots[idx] if 0 <= idx < NSLOTS else None
        if not s:
            raise ValueError("Auf dieser Taste liegt kein Sound")
        return s

    # ---- laden ----
    def reload(self, quiet=True):
        with self.board.file_lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            files = sorted(p for p in self.dir.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
            assign = [None] * NSLOTS
            loose = []
            for p in files:
                m = PREFIX.match(p.name)
                idx = PREFIX_TO_SLOT[m.group(1).lower()] if m else None
                if idx is not None and assign[idx] is None:
                    assign[idx] = p
                else:
                    loose.append(p)
            for p in loose:
                if None in assign:
                    assign[assign.index(None)] = p
            slots = [None] * NSLOTS
            for i, p in enumerate(assign):
                if p is None:
                    continue
                try:
                    data = load_sound(p)
                    radio = bool(self.fx.get(p.name, {}).get("radio"))
                    if radio:
                        data = radio_effect(data)
                    try:
                        full = sf.info(str(p)).duration
                    except Exception:
                        full = 0.0
                    cut = full > MAX_SECONDS + 0.05
                    if cut and not quiet:
                        print(f"  ! {p.name}: {full:.0f} s lang, gekürzt auf {MAX_SECONDS} s (MAX_SECONDS)")
                    auto = display_name(p)
                    custom = self.labels.get(p.name)
                    slots[i] = {"name": custom or auto, "path": p, "data": data, "auto": auto,
                                "custom": bool(custom), "full": round(full) if cut else None, "radio": radio}
                except Exception as e:
                    print(f"  ! {p.name} konnte nicht geladen werden: {e}")
            self.slots = slots
            present = {p.name for p in files}
            changed = False
            for store in (self.labels, self.fx):
                for k in [k for k in store if k not in present]:
                    del store[k]
                    changed = True
            for k in [k for k, v in self.art.items() if k not in present or not isinstance(v, dict)
                      or ("image" in v and not (IMG_DIR / str(v["image"])).exists())]:
                del self.art[k]
                changed = True
            if changed:
                self._save()
        if not quiet:
            n = sum(1 for s in self.slots if s)
            print(f"  Seite „{self.name}“: {n} Sound(s)")

    # ---- ändern ----
    def set_label(self, idx, label):
        s = self.slot(idx)
        label = (label or "").strip()[:60]
        with self.board.file_lock:
            if label:
                self.labels[s["path"].name] = label
            else:
                self.labels.pop(s["path"].name, None)
            self._save()
        self.reload()

    def set_art(self, idx, image=None, emoji=None):
        s = self.slot(idx)
        if image:
            if not IMAGE_NAME.match(image) or not (IMG_DIR / image).exists():
                raise ValueError("Bild nicht in der Bibliothek gefunden")
            (IMG_DIR / image).touch()
            entry = {"image": image}
        elif emoji:
            e = clean_emoji(emoji)
            if not e:
                raise ValueError("Ungültiges Emoji")
            entry = {"emoji": e}
        else:
            entry = None
        with self.board.file_lock:
            if entry:
                self.art[s["path"].name] = entry
            else:
                self.art.pop(s["path"].name, None)
            self._save()

    def set_radio(self, idx, on):
        s = self.slot(idx)
        with self.board.file_lock:
            if on:
                self.fx[s["path"].name] = {"radio": True}
            else:
                self.fx.pop(s["path"].name, None)
            self._save()
        self.reload()

    def store(self, idx, filename, data: bytes, label=None, use_meta=False, radio=False):
        """Datei auf Taste idx legen; bisherige Datei nach _alt verschieben; Titel/Bild/Effekt neu."""
        if not 0 <= idx < NSLOTS:
            raise ValueError("Ungültiger Platz")
        ext = Path(filename).suffix.lower()
        if ext not in EXTENSIONS:
            raise ValueError(f"Dateityp {ext or '?'} wird nicht unterstützt")
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f".tmp_{int(time.time() * 1000)}{ext}"
        tmp.write_bytes(data)
        try:
            load_sound(tmp)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise ValueError("Datei ist keine lesbare Audiodatei (WAV, MP3, OGG, FLAC)")
        title = (meta_title(tmp) if use_meta else None) or Path(filename).stem
        title = re.sub(r"^[0-9][_\- ]", "", title)
        base = re.sub(r"[^\w\-]+", "_", title).strip("_")[:60] or "sound"
        target = self.dir / f"{SLOTS[idx][1]}_{base}{ext}"
        with self.board.file_lock:
            current = self.slots[idx]
            if current and current["path"].exists():
                old = self.dir / "_alt"
                old.mkdir(exist_ok=True)
                dest = old / current["path"].name
                if dest.exists():
                    dest = old / f"{current['path'].stem}_{int(time.time())}{current['path'].suffix}"
                shutil.move(str(current["path"]), str(dest))
            if target.exists():
                target.unlink()
            tmp.rename(target)
            for store in (self.labels, self.art, self.fx):
                if current:
                    store.pop(current["path"].name, None)
                store.pop(target.name, None)
            if label and label.strip():
                self.labels[target.name] = label.strip()[:60]
            if radio:
                self.fx[target.name] = {"radio": True}
            self._save()
        self.reload()
        print(f"Seite „{self.name}“, Taste {SLOTS[idx][0]}: {display_name(target)}")

    def slot_state(self, i):
        s = self.slots[i]
        a = self.art.get(s["path"].name, {}) if s else {}
        img = a.get("image")
        return {"slot": i + 1, "key": SLOTS[i][0],
                "name": s["name"] if s else None,
                "auto_name": s["auto"] if s else None,
                "custom": s["custom"] if s else False,
                "file": s["path"].name if s else None,
                "seconds": round(len(s["data"]) / SAMPLE_RATE, 1) if s else None,
                "full_seconds": s["full"] if s else None,
                "radio": s["radio"] if s else False,
                "image": f"/images/{img}" if img else None,
                "emoji": a.get("emoji")}


# ----------------------------------------------------------------------
# Soundboard-Logik (von Hotkeys und Weboberfläche gemeinsam genutzt)
# ----------------------------------------------------------------------

class Board:
    def __init__(self):
        self.volume = SOUND_VOLUME
        self.cable = Player()
        self.monitor = Player() if MONITOR else None
        self.ptt = PushToTalk(PTT_KEY) if PTT_KEY else None
        self.file_lock = threading.RLock()
        self.gen = 0
        self.audio_ready = False
        self.mic_ready = False
        self.setup = Setup()
        self.pages = []
        self.current = 0
        self.rec = None              # laufende Aufnahme (Liste von Blöcken) oder None
        self.rec_started = 0.0
        self.pending_rec = None      # fertige Aufnahme (mono) bis zum Speichern
        self.busy = set()            # Seiten, die gerade per Vorlage befüllt werden

    # ---- Seiten verwalten ----
    @property
    def page_obj(self):
        return self.pages[self.current]

    @property
    def slots(self):
        return self.page_obj.slots

    def page(self, pid=None):
        if not pid:
            return self.page_obj
        for p in self.pages:
            if p.id == pid:
                return p
        raise ValueError("Seite nicht gefunden")

    def _save_pages(self):
        write_json(PAGES_FILE, {"pages": [p.meta() for p in self.pages], "current": self.page_obj.id})

    def load_pages(self):
        SOUND_DIR.mkdir(exist_ok=True)
        first_run = not PAGES_FILE.exists()
        migrated = self._migrate()
        cfg = read_json(PAGES_FILE)
        known = []
        for m in cfg.get("pages", []):
            pid = str(m.get("id", ""))
            if pid and pid not in RESERVED_DIRS and (SOUND_DIR / pid).is_dir() and pid not in [k["id"] for k in known]:
                known.append({"id": pid, "name": str(m.get("name") or pid)[:30],
                              "template": m.get("template"), "filled": bool(m.get("filled"))})
        # Ordner, die (noch) nicht in pages.json stehen – z. B. mitgeliefertes Kommando-Paket
        extra = sorted(d.name for d in SOUND_DIR.iterdir()
                       if d.is_dir() and d.name not in RESERVED_DIRS and not d.name.startswith((".", "_"))
                       and d.name not in [k["id"] for k in known])
        extra.sort(key=lambda n: (n != "Kommandos", n != "Eigene", n.lower()))
        for name in extra:
            has_sounds = any(p.suffix.lower() in EXTENSIONS for p in (SOUND_DIR / name).iterdir())
            known.append({"id": name, "name": name, "template": "kommandos" if name == "Kommandos" else None,
                          "filled": has_sounds})
        if first_run:                                   # Erststart: Standardseiten sicherstellen
            ids = [k["id"] for k in known]
            if "Kommandos" not in ids:
                known.insert(0, {"id": "Kommandos", "name": "Kommandos", "template": "kommandos", "filled": False})
            if "Eigene" not in ids:
                known.append({"id": "Eigene", "name": "Eigene", "template": None, "filled": False})
        if not known:
            known = [{"id": "Eigene", "name": "Eigene", "template": None, "filled": False}]
        self.pages = [Page(self, k["id"], k["name"], k["template"], k["filled"]) for k in known]
        cur = cfg.get("current") or ("Eigene" if migrated else None)
        ids = [p.id for p in self.pages]
        self.current = ids.index(cur) if cur in ids else 0
        for p in self.pages:
            p.reload(quiet=False)
        self._save_pages()

    def _migrate(self):
        """Bis 2.0 lagen alle Sounds direkt in sounds/ – einmalig in die Seite „Eigene“ verschieben."""
        top = [p for p in SOUND_DIR.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS]
        if not top or PAGES_FILE.exists():
            return False
        dest = SOUND_DIR / "Eigene"
        dest.mkdir(exist_ok=True)
        for p in top:
            shutil.move(str(p), str(dest / p.name))
        for name in ("labels.json", "art.json"):
            if (SOUND_DIR / name).exists() and not (dest / name).exists():
                shutil.move(str(SOUND_DIR / name), str(dest / name))
        if (SOUND_DIR / "_alt").is_dir() and not (dest / "_alt").exists():
            shutil.move(str(SOUND_DIR / "_alt"), str(dest / "_alt"))
        print(f"Hinweis: {len(top)} vorhandene Sound(s) wurden in die Seite „Eigene“ übernommen.")
        return True

    def switch_page(self, pid=None, delta=0, announce=False):
        if not self.pages:
            return
        if pid:
            self.current = [p.id for p in self.pages].index(self.page(pid).id)
        else:
            self.current = (self.current + delta) % len(self.pages)
        self._save_pages()
        print(f"Seite: {self.page_obj.name}")
        if announce:
            threading.Thread(target=self.announce, args=(self.page_obj,), daemon=True).start()

    def add_page(self, name, template=None):
        name = (name or "").strip()[:30]
        if not name:
            raise ValueError("Bitte einen Namen eingeben")
        pid, n = slug(name), 2
        while pid in RESERVED_DIRS or (SOUND_DIR / pid).exists() or pid in [p.id for p in self.pages]:
            pid, n = f"{slug(name)}_{n}", n + 1
        page = Page(self, pid, name, template if template == "kommandos" else None, False)
        page.reload()
        self.pages.append(page)
        self.current = len(self.pages) - 1
        self._save_pages()
        if page.template:
            self.fill_template_async(page)
        threading.Thread(target=self.ensure_announcement, args=(page,), daemon=True).start()
        return page

    def rename_page(self, pid, name):
        name = (name or "").strip()[:30]
        if not name:
            raise ValueError("Bitte einen Namen eingeben")
        self.page(pid).name = name
        self._save_pages()
        threading.Thread(target=self.ensure_announcement, args=(self.page(pid),), daemon=True).start()

    def move_page(self, pid, delta):
        page = self.page(pid)
        i = self.pages.index(page)
        j = max(0, min(len(self.pages) - 1, i + int(delta)))
        cur = self.page_obj
        self.pages.insert(j, self.pages.pop(i))
        self.current = self.pages.index(cur)
        self._save_pages()

    def delete_page(self, pid):
        if len(self.pages) <= 1:
            raise ValueError("Die letzte Seite kann nicht gelöscht werden")
        page = self.page(pid)
        self.stop()
        with self.file_lock:
            TRASH_DIR.mkdir(exist_ok=True)
            dest = TRASH_DIR / f"{page.id}_{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.move(str(page.dir), str(dest))
        cur = self.page_obj
        self.pages.remove(page)
        self.current = self.pages.index(cur) if cur in self.pages else 0
        self._save_pages()
        print(f"Seite „{page.name}“ gelöscht (verschoben nach {dest}).")

    # ---- Vorlage „Kommandos“ ----
    def fill_template_async(self, page):
        if page.id in self.busy or not tts_available():
            return
        self.busy.add(page.id)

        def work():
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                todo = []
                for key, text in COMMAND_TEMPLATE:
                    idx = [s[0] for s in SLOTS].index(key)
                    if page.slots[idx] is None:
                        todo.append((idx, text, CACHE_DIR / f"tpl_{page.id}_{idx}.wav"))
                if todo:
                    tts_batch([(t, p) for _, t, p in todo])
                    for idx, text, p in todo:
                        page.store(idx, f"{text}.wav", p.read_bytes(), radio=True)
                        p.unlink(missing_ok=True)
                page.filled = True
                self._save_pages()
                print(f"Seite „{page.name}“: Kommando-Vorlage erstellt.")
            except Exception as e:
                print(f"! Kommando-Vorlage für „{page.name}“ fehlgeschlagen: {e}")
            finally:
                self.busy.discard(page.id)

        threading.Thread(target=work, daemon=True).start()

    # ---- Seitenansage (nur im eigenen Headset) ----
    def _announce_file(self, page):
        h = hashlib.sha1(f"{page.name}|{TTS_LANG}|{TTS_RATE}".encode()).hexdigest()[:12]
        return CACHE_DIR / f"seite_{h}.wav"

    def ensure_announcement(self, page):
        if not (ANNOUNCE_PAGES and tts_available()):
            return None
        f = self._announce_file(page)
        if not f.exists():
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tts_batch([(page.name, f)])
            except Exception:
                return None
        return f

    def announce(self, page):
        if not (ANNOUNCE_PAGES and self.monitor and self.audio_ready):
            return
        data = None
        f = self.ensure_announcement(page)
        if f:
            try:
                data = load_sound(f)
            except Exception:
                data = None
        if data is None:
            data = beeps(self.pages.index(page) + 1 if page in self.pages else 1)
        self.monitor.play(data, None, exclusive=False)

    # ---- Bilder ----
    def add_image(self, data: bytes) -> str:
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Bild ist zu groß (max. 3 MB)")
        kind = image_type(data)
        if not kind:
            raise ValueError("Keine Bilddatei (PNG, JPG, GIF oder WebP)")
        name = f"{hashlib.sha256(data).hexdigest()[:16]}.{kind}"
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        if not (IMG_DIR / name).exists():
            (IMG_DIR / name).write_bytes(data)
        return name

    def list_images(self):
        if not IMG_DIR.exists():
            return []
        files = [p for p in IMG_DIR.iterdir() if IMAGE_NAME.match(p.name)]
        return [p.name for p in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)]

    # ---- Aufnahme ----
    def rec_start(self):
        if not (self.audio_ready and self.mic_ready):
            raise ValueError("Aufnahme nicht möglich: Mikrofon läuft nicht (siehe Einrichtungs-Check)")
        self.pending_rec = None
        self.rec_started = time.time()
        self.rec = []
        started = self.rec_started

        def auto_stop():
            if self.rec is not None and self.rec_started == started:
                try:
                    self.rec_stop()
                except Exception:
                    pass

        t = threading.Timer(RECORD_MAX_SECONDS, auto_stop)
        t.daemon = True
        t.start()

    def rec_push(self, block):
        rec = self.rec
        if rec is not None:
            rec.append(block.copy())

    def rec_stop(self):
        if self.rec is None:
            if self.pending_rec is not None:
                return len(self.pending_rec) / SAMPLE_RATE
            raise ValueError("Es läuft keine Aufnahme")
        blocks, self.rec = self.rec, None
        mono = np.concatenate(blocks) if blocks else np.zeros(0, np.float32)
        self.pending_rec = trim_silence(mono)
        return len(self.pending_rec) / SAMPLE_RATE

    def rec_preview(self, radio=False):
        if self.pending_rec is None:
            raise ValueError("Keine Aufnahme vorhanden")
        if not (self.monitor and self.audio_ready):
            raise ValueError("Mithören ist ausgeschaltet")
        data = np.repeat(self.pending_rec[:, None], 2, axis=1).astype(np.float32)
        peak = float(np.max(np.abs(data))) or 1.0
        data = data / peak * NORMALIZE_PEAK
        if radio:
            data = radio_effect(data)
        self.monitor.play(data, None)

    def rec_save(self, page, idx, label=None, radio=False):
        if self.pending_rec is None:
            raise ValueError("Keine Aufnahme vorhanden")
        title = (label or "").strip() or f"Aufnahme {time.strftime('%H-%M-%S')}"
        page.store(idx, f"{title}.wav", wav_bytes(self.pending_rec), label=None, radio=radio)
        self.pending_rec = None

    # ---- Text → Sprache ----
    def tts_save(self, page, idx, text, label=None, radio=False):
        text = (text or "").strip()
        if not text or len(text) > 200:
            raise ValueError("Bitte einen Text mit höchstens 200 Zeichen eingeben")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_DIR / f"tts_{int(time.time() * 1000)}.wav"
        try:
            tts_batch([(text, tmp)])
            page.store(idx, f"{text[:60]}.wav", tmp.read_bytes(), label=label, radio=radio)
        finally:
            tmp.unlink(missing_ok=True)

    # ---- Wiedergabe ----
    def play(self, idx):
        page = self.page_obj
        s = page.slots[idx] if 0 <= idx < NSLOTS else None
        if not s:
            return False
        if not self.audio_ready:
            print("! Audio läuft nicht - siehe Anleitung in der Weboberfläche.")
            return False
        if self.rec is not None:
            return False                       # während einer Aufnahme nichts abspielen
        self.gen += 1
        gen = self.gen
        data = s["data"]
        pre = self.ptt.begin(len(data) / SAMPLE_RATE) if self.ptt else 0.0
        key = (page.id, idx)

        def start():
            if EXCLUSIVE and gen != self.gen:
                return
            self.cable.play(data, key)
            if self.monitor:
                self.monitor.play(data, key)

        if pre > 0:
            t = threading.Timer(pre, start)
            t.daemon = True
            t.start()
        else:
            start()
        print(f"> {s['name']}")
        return True

    def test_tone(self):
        if not self.audio_ready:
            return False
        t = np.arange(int(SAMPLE_RATE * 0.8)) / SAMPLE_RATE
        freq = np.where(t < 0.4, 660.0, 880.0)
        tone = 0.5 * np.sin(2 * np.pi * freq * t)
        fade = np.minimum(1.0, np.minimum(t, t[-1] - t) / 0.02)
        tone = np.repeat((tone * fade)[:, None], 2, axis=1).astype(np.float32)
        self.gen += 1
        self.cable.play(tone, None)
        if self.monitor:
            self.monitor.play(tone, None)
        return True

    def toggle(self, idx):
        if (self.page_obj.id, idx) in self.cable.active_slots():
            self.stop()
            return True
        return self.play(idx)

    def stop(self):
        self.gen += 1
        self.cable.stop()
        if self.monitor:
            self.monitor.stop()
        if self.ptt:
            self.ptt.release_now()

    def set_volume(self, v):
        self.volume = min(MAX_VOLUME, max(0.0, float(v)))

    def reload(self, quiet=False):
        for p in self.pages:
            p.reload(quiet=quiet)
        check_static(self.setup, self)

    def state(self):
        page = self.page_obj
        active = self.cable.active_slots()
        return {
            "version": VERSION,
            "audio": self.audio_ready,
            "setup_issues": self.setup.issues(),
            "volume": self.volume,
            "max_volume": MAX_VOLUME,
            "update": update_state(),
            "tts": tts_available(),
            "mic": self.audio_ready and self.mic_ready,
            "recording": self.rec is not None,
            "rec_seconds": round(time.time() - self.rec_started, 1) if self.rec is not None else None,
            "pending_rec": round(len(self.pending_rec) / SAMPLE_RATE, 1) if self.pending_rec is not None else None,
            "pages": [{"id": p.id, "name": p.name, "count": sum(1 for s in p.slots if s),
                       "busy": p.id in self.busy} for p in self.pages],
            "page": page.id,
            "playing": [k[1] for k in active if isinstance(k, tuple) and k[0] == page.id],
            "slots": [page.slot_state(i) for i in range(NSLOTS)],
        }


# ----------------------------------------------------------------------
# Download von Myinstants / direkten Links
# ----------------------------------------------------------------------

def fetch(url, limit=15 * 1024 * 1024):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Datei ist zu groß")
        return data, r.geturl()


def download_sound(url: str):
    """Liefert (Dateiname, Bytes). Akzeptiert Myinstants-Seiten, Embed-Links und MP3-Links."""
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    path = urllib.parse.urlparse(url).path

    if Path(path).suffix.lower() in EXTENSIONS:
        data, _ = fetch(url)
        return Path(path).name, data

    html, final = fetch(url, limit=3 * 1024 * 1024)
    text = html.decode("utf-8", "ignore")
    m = re.search(r"""(/media/sounds/[^'"\s<>]+?\.(?:mp3|wav|ogg))""", text, re.I)
    if not m:
        raise ValueError("Keine Sounddatei auf der Seite gefunden. "
                         "Tipp: auf Myinstants den Download-Link (MP3) kopieren.")
    mp3_url = urllib.parse.urljoin(final, m.group(1))
    data, _ = fetch(mp3_url)

    # Name: Seitentitel, sonst Pfad (…/instant/<slug>/…), sonst Dateiname
    title = None
    for pat in (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                r"<h1[^>]*>([^<]+)</h1>", r"<title>([^<]+)</title>"):
        t = re.search(pat, text, re.I)
        if t:
            title = htmllib.unescape(t.group(1))
            title = re.sub(r"\s*[-|–]\s*(Myinstants|Instant Sound Button).*$", "", title, flags=re.I).strip()
            if title:
                break
    slug = re.search(r"/instant/([^/]+)", path)
    base = title or (urllib.parse.unquote(slug.group(1)) if slug else Path(m.group(1)).stem)
    return base + Path(m.group(1)).suffix, data


# ----------------------------------------------------------------------
# Weboberfläche
# ----------------------------------------------------------------------

QUIT = threading.Event()


# ----------------------------------------------------------------------
# Update-Prüfung (nur Hinweis, es wird nichts automatisch installiert)
# ----------------------------------------------------------------------

UPDATE = {"latest": None, "url": None, "checked": None, "error": None}


def version_tuple(v: str):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:4]) if nums else ()


def check_update(setup=None):
    """Neueste Version bei GitHub abfragen. Gibt True zurück, wenn eine neuere existiert."""
    try:
        req = urllib.request.Request(UPDATE_URL, headers={
            "User-Agent": f"WARDOGS-Soundboard/{VERSION}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read(512 * 1024).decode("utf-8"))
        tag = str(data.get("tag_name") or "")
        url = str(data.get("html_url") or f"https://github.com/{UPDATE_REPO}/releases/latest")
        if not url.startswith("https://github.com/"):
            url = f"https://github.com/{UPDATE_REPO}/releases/latest"
        UPDATE.update(latest=tag.lstrip("vV") or None, url=url, checked=time.time(), error=None)
    except Exception as e:
        UPDATE.update(checked=time.time(), error=str(e))
        if setup:
            setup.set("update", "info", "Update-Prüfung nicht möglich",
                      "GitHub war nicht erreichbar – das Soundboard funktioniert trotzdem.")
        return False
    newer = bool(UPDATE["latest"]) and version_tuple(UPDATE["latest"]) > version_tuple(VERSION)
    if setup:
        if newer:
            setup.set("update", "info", f"Neue Version {UPDATE['latest']} verfügbar",
                      f"Installiert ist {VERSION}. Download: {UPDATE['url']}")
        else:
            setup.set("update", "ok", f"Version {VERSION} ist aktuell")
    return newer


def update_state():
    newer = bool(UPDATE["latest"]) and version_tuple(UPDATE["latest"]) > version_tuple(VERSION)
    return {"version": UPDATE["latest"], "url": UPDATE["url"]} if newer else None


def update_loop(setup):
    while True:
        if check_update(setup):
            print(f"\n*** Neue Version {UPDATE['latest']} verfügbar (installiert: {VERSION}) ***")
            print(f"    Download: {UPDATE['url']}\n")
        if QUIT.wait(UPDATE_INTERVAL):
            return


class WebServer(ThreadingHTTPServer):
    # Windows erlaubt mit SO_REUSEADDR mehrere Programme auf demselben Port -> abschalten,
    # sonst läuft unbemerkt ein zweites Soundboard und jeder Sound kommt doppelt.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


def already_running() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{WEB_PORT}/api/state", timeout=1).read()
        return True
    except Exception:
        return False


def make_handler(board: Board, engine=None):
    page_html = (BASE_DIR / "web.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 20 * 1024 * 1024:
                raise ValueError("Datei ist zu groß")
            return self.rfile.read(n)

        def json(self):
            raw = self.body()
            return json.loads(raw) if raw else {}

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path in ("/", "/index.html"):
                self.send(200, page_html, "text/html; charset=utf-8")
            elif path == "/api/state":
                self.send(200, board.state())
            elif path == "/api/setup":
                self.send(200, setup_info(board))
            elif path == "/api/images":
                self.send(200, {"images": board.list_images()})
            elif path.startswith("/images/"):
                name = path[len("/images/"):]
                file = IMG_DIR / name
                if not IMAGE_NAME.match(name) or not file.exists():
                    return self.send(404, {"error": "nicht gefunden"})
                data = file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", IMAGE_TYPES[name.rsplit(".", 1)[1]])
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=31536000, immutable")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send(404, {"error": "nicht gefunden"})

        def do_POST(self):
            # Schutz gegen fremde Webseiten, die Anfragen an localhost schicken
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            if origin and urllib.parse.urlparse(origin).netloc != host:
                return self.send(403, {"error": "fremder Ursprung"})

            url = urllib.parse.urlparse(self.path)
            parts = url.path.strip("/").split("/")
            pid = urllib.parse.parse_qs(url.query).get("p", [None])[0]
            ok = lambda: self.send(200, board.state())          # noqa: E731

            def slot_idx(v):
                i = int(v) - 1
                if not 0 <= i < NSLOTS:
                    raise ValueError("Ungültiger Platz")
                return i

            try:
                # ---- Wiedergabe ----
                if parts[:2] == ["api", "play"] and len(parts) == 3:
                    played = board.toggle(slot_idx(parts[2]))
                    return self.send(200 if played else 404, board.state())
                if parts == ["api", "stop"]:
                    board.stop()
                    return ok()
                if parts == ["api", "volume"]:
                    board.set_volume(self.json()["value"])
                    return ok()
                if parts == ["api", "reload"]:
                    board.reload()
                    return ok()

                # ---- Seiten ----
                if parts == ["api", "page", "switch"]:
                    req = self.json()
                    board.switch_page(pid=req.get("id"), delta=int(req.get("delta", 0)))
                    return ok()
                if parts == ["api", "page", "add"]:
                    req = self.json()
                    board.add_page(req.get("name"), req.get("template"))
                    return ok()
                if parts == ["api", "page", "rename"]:
                    req = self.json()
                    board.rename_page(req.get("id"), req.get("name"))
                    return ok()
                if parts == ["api", "page", "move"]:
                    req = self.json()
                    board.move_page(req.get("id"), req.get("delta", 0))
                    return ok()
                if parts == ["api", "page", "delete"]:
                    board.delete_page(self.json().get("id"))
                    return ok()
                if parts == ["api", "page", "fill"]:
                    page = board.page(self.json().get("id"))
                    if not tts_available():
                        raise ValueError("Text-to-Speech gibt es nur unter Windows")
                    board.fill_template_async(page)
                    return ok()

                # ---- Tasten belegen (Seite über ?p=…) ----
                page = board.page(pid)
                if parts == ["api", "import"]:
                    req = self.json()
                    name, data = download_sound(req["url"])
                    page.store(slot_idx(req["slot"]), name, data, req.get("label"), radio=bool(req.get("radio")))
                    return ok()
                if parts[:2] == ["api", "upload"] and len(parts) == 3:
                    name = urllib.parse.unquote(self.headers.get("X-Filename", "sound.wav"))
                    radio = self.headers.get("X-Radio") == "1"
                    page.store(slot_idx(parts[2]), name, self.body(), use_meta=True, radio=radio)
                    return ok()
                if parts == ["api", "tts"]:
                    req = self.json()
                    board.tts_save(page, slot_idx(req["slot"]), req.get("text"), req.get("label"),
                                   radio=bool(req.get("radio")))
                    return ok()
                if parts == ["api", "label"]:
                    req = self.json()
                    page.set_label(slot_idx(req["slot"]), req.get("label", ""))
                    return ok()
                if parts == ["api", "radio"]:
                    req = self.json()
                    page.set_radio(slot_idx(req["slot"]), bool(req.get("on")))
                    return ok()
                if parts[:2] == ["api", "image"] and len(parts) == 3:
                    name = board.add_image(self.body())
                    page.set_art(slot_idx(parts[2]), image=name)
                    return ok()
                if parts == ["api", "art"]:
                    req = self.json()
                    page.set_art(slot_idx(req["slot"]), image=req.get("image"), emoji=req.get("emoji"))
                    return ok()
                if parts == ["api", "fetchimage"]:
                    src = self.json()["url"].strip()
                    if not re.match(r"^https?://", src):
                        src = "https://" + src
                    data, _ = fetch(src, limit=8 * 1024 * 1024)
                    kind = image_type(data)
                    if not kind:
                        raise ValueError("Der Link zeigt nicht direkt auf ein Bild (PNG, JPG, GIF, WebP)")
                    return self.send(200, data, IMAGE_TYPES[kind])

                # ---- Aufnahme ----
                if parts == ["api", "record", "start"]:
                    board.rec_start()
                    return ok()
                if parts == ["api", "record", "stop"]:
                    board.rec_stop()
                    return ok()
                if parts == ["api", "record", "preview"]:
                    board.rec_preview(radio=bool(self.json().get("radio")))
                    return ok()
                if parts == ["api", "record", "discard"]:
                    board.rec, board.pending_rec = None, None
                    return ok()
                if parts == ["api", "record", "save"]:
                    req = self.json()
                    board.rec_save(page, slot_idx(req["slot"]), req.get("label"), radio=bool(req.get("radio")))
                    return ok()

                # ---- Einrichtung / Sonstiges ----
                if parts == ["api", "setup", "check"]:
                    devs = check_devices(board.setup, refresh=not board.audio_ready)
                    if not board.audio_ready and engine is not None:
                        engine.start(devs)
                    board.setup.print()
                    return self.send(200, setup_info(board))
                if parts == ["api", "test"]:
                    if not board.test_tone():
                        raise ValueError("Audio läuft nicht – siehe Einrichtungs-Check")
                    return self.send(200, setup_info(board))
                if parts == ["api", "quit"]:
                    self.send(200, {"ok": True})
                    print("\nBeenden angefordert (Spiel geschlossen).")
                    QUIT.set()
                    return
                self.send(404, {"error": "nicht gefunden"})
            except Exception as e:
                self.send(400, {"error": str(e)})

    return Handler


def setup_info(board):
    check_static(board.setup, board)
    return {
        "version": VERSION,
        "audio": board.audio_ready,
        "items": board.setup.list(),
        "config": {
            "folder": str(BASE_DIR),
            "mic_device": MIC_DEVICE or "Windows-Standardmikrofon",
            "ptt_key": PTT_KEY,
            "ptt_window": PTT_WINDOW,
            "cable_device": CABLE_DEVICE,
        },
    }


# ----------------------------------------------------------------------
# Start
# ----------------------------------------------------------------------

def main():
    if "--list" in sys.argv:
        print(sd.query_devices())
        return

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(CONSOLE_TITLE)
        except Exception:
            pass
    print(f"WARDOGS Soundboard v{VERSION}")
    if already_running():
        print(f"\n! Das Soundboard läuft bereits (http://localhost:{WEB_PORT}).")
        print("  Ein zweites würde jeden Sound doppelt abspielen - dieses Fenster wird nicht gebraucht.")
        if OPEN_BROWSER and "--no-browser" not in sys.argv:
            webbrowser.open(f"http://localhost:{WEB_PORT}")
        time.sleep(6)
        return
    board = Board()
    print("\nSeiten:")
    board.load_pages()
    check_static(board.setup, board)

    # ---------- Geräte prüfen, Audio starten ----------
    devs = check_devices(board.setup)
    engine = AudioEngine(board)
    engine.start(devs)
    if devs["cable"] is not None:
        print(f"Kabel:    {device_name(devs['cable'], True)}")
    if engine.mic_active:
        print(f"Mikrofon: {device_name(devs['mic'], False)}")
    if engine.board.monitor and devs["monitor_ok"]:
        print(f"Monitor:  {device_name(devs['monitor'], True)}")

    # ---------- Hotkeys ----------
    held = set()
    numlock_echo = [0]            # eigene NumLock-Rückschaltung ignorieren

    def restore_numlock():
        """NumLock wieder umschalten (simulierter Druck, wie in der MS-Doku)."""
        import ctypes
        ext, up = 0x1, 0x2
        numlock_echo[0] = 2
        ctypes.windll.user32.keybd_event(0x90, 0x45, ext, 0)
        ctypes.windll.user32.keybd_event(0x90, 0x45, ext | up, 0)

    def on_event(e):
        sc = e.scan_code
        if not e.is_keypad:
            # eigene Bild ↑ / Bild ↓ -> Seite wechseln (Numpad 9/3 bleiben Sound-Tasten)
            if PAGE_KEYS and sc in (PAGE_UP_SCAN, PAGE_DOWN_SCAN):
                if e.event_type == keyboard.KEY_UP:
                    held.discard(("page", sc))
                elif ("page", sc) not in held:
                    held.add(("page", sc))
                    board.switch_page(delta=-1 if sc == PAGE_UP_SCAN else 1, announce=True)
            return
        if sc == NUMLOCK_SCAN and numlock_echo[0] > 0:
            numlock_echo[0] -= 1
            return
        if e.event_type == keyboard.KEY_UP:
            held.discard(sc)
            if sc == NUMLOCK_SCAN and KEEP_NUMLOCK and sys.platform == "win32":
                restore_numlock()
            return
        if sc in held:                     # Tastenwiederholung ignorieren
            return
        held.add(sc)

        if sc == STOP_SCAN:
            board.stop()
        elif sc in SCAN_TO_SLOT:
            board.toggle(SCAN_TO_SLOT[sc])

    try:
        keyboard.hook(on_event)
        board.setup.set("hotkeys", "ok", "Numpad-Hotkeys aktiv",
                        "Reagieren sie im Spiel nicht, das Soundboard als Administrator starten.")
    except Exception as e:
        board.setup.set("hotkeys", "error", "Hotkeys konnten nicht aktiviert werden", str(e))
    board.setup.print()

    # ---------- Weboberfläche ----------
    try:
        server = WebServer((WEB_HOST, WEB_PORT), make_handler(board, engine))
    except OSError as e:
        print(f"\n! Port {WEB_PORT} ist belegt ({e}). Läuft das Soundboard schon in einem anderen Fenster?")
        keyboard.unhook_all()
        engine.stop()
        time.sleep(6)
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://localhost:{WEB_PORT}"
    print(f"Weboberfläche: {url}")
    def background():
        check_tts(board.setup)
        for p in board.pages:                    # Kommando-Vorlage beim ersten Start füllen
            if p.template == "kommandos" and not p.filled and not any(p.slots):
                board.fill_template_async(p)
        for p in board.pages:                    # Seitenansagen vorbereiten
            board.ensure_announcement(p)

    threading.Thread(target=background, daemon=True).start()
    if CHECK_UPDATES:
        threading.Thread(target=update_loop, args=(board.setup,), daemon=True).start()
    else:
        board.setup.set("update", "info", "Update-Prüfung ist ausgeschaltet", "CHECK_UPDATES = False")
    if OPEN_BROWSER and "--no-browser" not in sys.argv:
        webbrowser.open(url + ("#anleitung" if board.setup.issues() and not board.audio_ready else ""))

    if board.audio_ready:
        print("\nSoundboard läuft. Beenden mit Strg+C.\n")
    else:
        print("\n! Einrichtung unvollständig - Anleitung im Browser beachten. Beenden mit Strg+C.\n")
    try:
        while not QUIT.wait(1):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        if board.ptt:
            board.ptt.release_now()
        keyboard.unhook_all()
        server.shutdown()
        engine.stop()


if __name__ == "__main__":
    main()
