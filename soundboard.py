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

Tasten (egal ob NumLock an oder aus):
  Numpad 0-9 , / * - + NumLock   je ein Sound (16 Plätze)
  Gleiche Taste nochmal          laufenden Sound stoppen
  Numpad Enter                   alle Sounds stoppen
  Strg+C                         Beenden (im Konsolenfenster)
  Lautstärke und Neuladen gibt es in der Weboberfläche.
  NumLock wird nach dem Drücken automatisch zurückgeschaltet.

Einrichtung:
  Beim Start prüft das Tool VB-Cable, Mikrofon, Ausgabe und Hotkeys. Fehlt etwas,
  öffnet sich die Weboberfläche mit der Anleitung (Menüpunkt "Anleitung").

Platzbelegung:
  Dateien mit Präfix landen fest auf diesem Platz, z. B. "3_leeroy.mp3",
  "0_...", "komma_...", "geteilt_...", "mal_...", "minus_...", "plus_...", "num_...".
  Dateien ohne Präfix füllen freie Plätze alphabetisch.
  Ersetzte Sounds werden nicht gelöscht, sondern nach sounds/_alt verschoben.

Bilder und Emojis:
  Jede Taste kann ein Bild (als Kachelhintergrund) oder ein Emoji bekommen. Es hängt am
  Sound und wird beim Austausch zurückgesetzt. Alle Bilder bleiben in sounds/images und
  lassen sich im Dialog aus der Bibliothek wiederverwenden.

Titel:
  Automatisch aus Myinstants-Seitentitel, Datei-Metadaten oder Dateinamen.
  Eigene Titel stehen in sounds/labels.json und verfallen, wenn die Datei getauscht wird.

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
import json
import re
import shutil
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
SOUND_DIR = BASE_DIR / "sounds"
OLD_DIR = SOUND_DIR / "_alt"
LABELS_FILE = SOUND_DIR / "labels.json"
ART_FILE = SOUND_DIR / "art.json"          # Bild/Emoji je Sound
IMG_DIR = SOUND_DIR / "images"             # Bildbibliothek (bleibt erhalten)
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

PTT_KEY = "k"                  # Push-to-Talk-Taste im Spiel, None = abschalten
PTT_WINDOW = "WARDOGS"         # nur drücken, wenn dieses Fenster aktiv ist (None = immer)
PTT_PREROLL = 0.15             # Sekunden zwischen Tastendruck und Soundstart
PTT_TAIL = 0.25                # Sekunden, die die Taste nach Soundende noch gehalten wird

CONSOLE_TITLE = "WARDOGS Soundboard"   # Fenstertitel (wird vom Startskript zum Minimieren gesucht)

WEB_HOST = "127.0.0.1"         # "0.0.0.0" = auch vom Handy im Heimnetz erreichbar
WEB_PORT = 8765
OPEN_BROWSER = True

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

    def play(self, data, slot):
        with self.lock:
            if EXCLUSIVE:
                self.voices.clear()
            self.voices.append([data, 0, slot])

    def stop(self):
        with self.lock:
            self.voices.clear()

    def active_slots(self):
        with self.lock:
            return sorted({v[2] for v in self.voices})

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
    ORDER = ["python", "packages", "cable", "monitor", "mic", "audio", "hotkeys", "sounds"]

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
    n = sum(1 for s in board.slots if s)
    if n:
        setup.set("sounds", "ok", f"{n} von {NSLOTS} Tasten belegt")
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
# Soundboard-Logik (von Hotkeys und Weboberfläche gemeinsam genutzt)
# ----------------------------------------------------------------------

class Board:
    def __init__(self):
        self.volume = SOUND_VOLUME
        self.slots = [None] * NSLOTS       # (Name, Datei, ndarray) oder None
        self.cable = Player()
        self.monitor = Player() if MONITOR else None
        self.ptt = PushToTalk(PTT_KEY) if PTT_KEY else None
        self.file_lock = threading.Lock()
        self.gen = 0
        self.audio_ready = False
        self.setup = Setup()
        self.labels = self._load_labels()
        self.art = read_json(ART_FILE)

    # ---- Bilder und Emojis ----
    def add_image(self, data: bytes) -> str:
        """Bild in die Bibliothek aufnehmen (gleiche Bilder werden nur einmal gespeichert)."""
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Bild ist zu groß (max. 3 MB)")
        kind = image_type(data)
        if not kind:
            raise ValueError("Keine Bilddatei (PNG, JPG, GIF oder WebP)")
        name = f"{hashlib.sha256(data).hexdigest()[:16]}.{kind}"
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        path = IMG_DIR / name
        if not path.exists():
            path.write_bytes(data)
        return name

    def list_images(self):
        if not IMG_DIR.exists():
            return []
        files = [p for p in IMG_DIR.iterdir() if IMAGE_NAME.match(p.name)]
        return [p.name for p in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)]

    def set_art(self, idx, image=None, emoji=None):
        """Bild (Name aus der Bibliothek) oder Emoji setzen; beides leer = entfernen."""
        s = self.slots[idx] if 0 <= idx < NSLOTS else None
        if not s:
            raise ValueError("Auf dieser Taste liegt kein Sound")
        if image:
            if not IMAGE_NAME.match(image) or not (IMG_DIR / image).exists():
                raise ValueError("Bild nicht in der Bibliothek gefunden")
            (IMG_DIR / image).touch()                       # zuletzt benutzt -> vorne
            entry = {"image": image}
        elif emoji:
            e = clean_emoji(emoji)
            if not e:
                raise ValueError("Ungültiges Emoji")
            entry = {"emoji": e}
        else:
            entry = None
        with self.file_lock:
            if entry:
                self.art[s[1].name] = entry
            else:
                self.art.pop(s[1].name, None)
            write_json(ART_FILE, self.art)

    # ---- eigene Titel ----
    def _load_labels(self):
        try:
            data = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items() if str(v).strip()}
        except Exception:
            return {}

    def _save_labels(self):
        try:
            SOUND_DIR.mkdir(exist_ok=True)
            LABELS_FILE.write_text(json.dumps(self.labels, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"  ! labels.json konnte nicht gespeichert werden: {e}")

    def set_label(self, idx, label):
        """Eigenen Titel setzen; leer = automatischer Titel."""
        s = self.slots[idx] if 0 <= idx < NSLOTS else None
        if not s:
            raise ValueError("Auf dieser Taste liegt kein Sound")
        label = (label or "").strip()[:60]
        with self.file_lock:
            if label:
                self.labels[s[1].name] = label
            else:
                self.labels.pop(s[1].name, None)
            self._save_labels()
        self.reload(quiet=True)

    # ---- Sounds laden ----
    def reload(self, quiet=False):
        with self.file_lock:
            SOUND_DIR.mkdir(exist_ok=True)
            files = sorted(p for p in SOUND_DIR.iterdir()
                           if p.is_file() and p.suffix.lower() in EXTENSIONS)
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
                    auto = display_name(p)
                    custom = self.labels.get(p.name)
                    data = load_sound(p)
                    try:
                        full = sf.info(str(p)).duration
                    except Exception:
                        full = 0.0
                    cut = full > MAX_SECONDS + 0.05
                    if cut:
                        print(f"  ! {p.name}: {full:.0f} s lang, gekürzt auf {MAX_SECONDS} s (MAX_SECONDS)")
                    slots[i] = (custom or auto, p, data, auto, bool(custom), round(full) if cut else None)
                except Exception as e:
                    print(f"  ! {p.name} konnte nicht geladen werden: {e}")
            self.slots = slots
            present = {p.name for p in files}
            stale = [k for k in self.labels if k not in present]
            if stale:                       # Datei weg/umbenannt -> Titel verfällt
                for k in stale:
                    del self.labels[k]
                self._save_labels()
            stale_art = [k for k, v in self.art.items()
                         if k not in present or not isinstance(v, dict)
                         or ("image" in v and not (IMG_DIR / str(v["image"])).exists())]
            if stale_art:                   # Bild/Emoji gehört zu keinem Sound mehr
                for k in stale_art:
                    del self.art[k]
                write_json(ART_FILE, self.art)
        check_static(self.setup, self)

        if not quiet:
            print(f"\nSounds aus {SOUND_DIR}:")
            for i, s in enumerate(self.slots, 1):
                if s:
                    print(f"  {SLOTS[i - 1][0]:>3}: {s[0]}  ({len(s[2]) / SAMPLE_RATE:.1f} s)")
            print()

    # ---- Wiedergabe ----
    def play(self, idx):
        s = self.slots[idx] if 0 <= idx < NSLOTS else None
        if not s:
            return False
        if not self.audio_ready:
            print("! Audio läuft nicht - siehe Anleitung in der Weboberfläche.")
            return False
        self.gen += 1
        gen = self.gen
        pre = self.ptt.begin(len(s[2]) / SAMPLE_RATE) if self.ptt else 0.0

        def start():
            if EXCLUSIVE and gen != self.gen:      # inzwischen anderer Sound/Stopp
                return
            self.cable.play(s[2], idx)
            if self.monitor:
                self.monitor.play(s[2], idx)

        if pre > 0:
            t = threading.Timer(pre, start)
            t.daemon = True
            t.start()
        else:
            start()
        print(f"> {s[0]}")
        return True

    def test_tone(self):
        """Kurzer Piepton ins Kabel (ohne Push-to-Talk) - zum Prüfen des Pegels."""
        if not self.audio_ready:
            return False
        t = np.arange(int(SAMPLE_RATE * 0.8)) / SAMPLE_RATE
        freq = np.where(t < 0.4, 660.0, 880.0)
        tone = 0.5 * np.sin(2 * np.pi * freq * t)
        fade = np.minimum(1.0, np.minimum(t, t[-1] - t) / 0.02)
        tone = np.repeat((tone * fade)[:, None], 2, axis=1).astype(np.float32)
        self.gen += 1
        self.cable.play(tone, -1)
        if self.monitor:
            self.monitor.play(tone, -1)
        return True

    def toggle(self, idx):
        """Läuft der Sound dieses Platzes gerade, stoppen - sonst abspielen."""
        if idx in self.cable.active_slots():
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

    # ---- Platz neu belegen ----
    def store(self, idx, filename, data: bytes, label=None, use_meta=False):
        """Datei auf Platz idx legen; bisherige Datei des Platzes nach _alt verschieben."""
        ext = Path(filename).suffix.lower()
        if ext not in EXTENSIONS:
            raise ValueError(f"Dateityp {ext or '?'} wird nicht unterstützt")
        # erst prüfen, ob die Datei lesbar ist
        tmp = SOUND_DIR / f".tmp_{int(time.time() * 1000)}{ext}"
        SOUND_DIR.mkdir(exist_ok=True)
        tmp.write_bytes(data)
        try:
            load_sound(tmp)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise ValueError("Datei ist keine lesbare Audiodatei (WAV, MP3, OGG, FLAC)")

        # Dateiname = automatischer Titel (Seitentitel / Metadaten / ursprünglicher Name)
        title = (meta_title(tmp) if use_meta else None) or Path(filename).stem
        title = re.sub(r"^[0-9][_\- ]", "", title)            # alte Ziffern-Präfixe entfernen
        base = re.sub(r"[^\w\-]+", "_", title).strip("_")[:60] or "sound"
        target = SOUND_DIR / f"{SLOTS[idx][1]}_{base}{ext}"

        with self.file_lock:
            current = self.slots[idx]
            if current and current[1].exists():
                OLD_DIR.mkdir(exist_ok=True)
                dest = OLD_DIR / current[1].name
                if dest.exists():
                    dest = OLD_DIR / f"{current[1].stem}_{int(time.time())}{current[1].suffix}"
                shutil.move(str(current[1]), str(dest))
            if target.exists():
                target.unlink()
            tmp.rename(target)
            # neuer Sound -> alter eigener Titel verfällt; ggf. neuen setzen
            if current:
                self.labels.pop(current[1].name, None)
            self.labels.pop(target.name, None)
            if current:                       # neuer Sound -> Bild/Emoji zurücksetzen
                self.art.pop(current[1].name, None)
            self.art.pop(target.name, None)
            write_json(ART_FILE, self.art)
            if label and label.strip():
                self.labels[target.name] = label.strip()[:60]
            self._save_labels()
        self.reload(quiet=True)
        print(f"Platz {SLOTS[idx][0]}: {display_name(target)}")

    def _art_state(self, s):
        a = self.art.get(s[1].name, {}) if s else {}
        img = a.get("image")
        return {"image": f"/images/{img}" if img else None, "emoji": a.get("emoji")}

    def state(self):
        return {
            "version": VERSION,
            "audio": self.audio_ready,
            "setup_issues": self.setup.issues(),
            "volume": self.volume,
            "max_volume": MAX_VOLUME,
            "playing": self.cable.active_slots(),
            "slots": [
                {"slot": i + 1,
                 "key": SLOTS[i][0],
                 "name": s[0] if s else None,
                 "auto_name": s[3] if s else None,
                 "custom": s[4] if s else False,
                 "file": s[1].name if s else None,
                 "seconds": round(len(s[2]) / SAMPLE_RATE, 1) if s else None,
                 "full_seconds": s[5] if s else None,
                 **self._art_state(s)}
                for i, s in enumerate(self.slots)
            ],
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


class WebServer(ThreadingHTTPServer):
    # Windows erlaubt mit SO_REUSEADDR mehrere Programme auf demselben Port -> abschalten,
    # sonst läuft unbemerkt ein zweites Soundboard und jeder Sound kommt doppelt.
    allow_reuse_address = False
    daemon_threads = True


def already_running() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{WEB_PORT}/api/state", timeout=1).read()
        return True
    except Exception:
        return False


def make_handler(board: Board, engine=None):
    page = (BASE_DIR / "web.html").read_bytes()

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

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send(200, page, "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self.send(200, board.state())
            elif self.path == "/api/setup":
                self.send(200, setup_info(board))
            elif self.path == "/api/images":
                self.send(200, {"images": board.list_images()})
            elif self.path.startswith("/images/"):
                name = self.path[len("/images/"):].split("?", 1)[0]
                path = IMG_DIR / name
                if not IMAGE_NAME.match(name) or not path.exists():
                    return self.send(404, {"error": "nicht gefunden"})
                data = path.read_bytes()
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

            parts = self.path.strip("/").split("/")
            try:
                if parts[:2] == ["api", "play"] and len(parts) == 3:
                    ok = board.toggle(int(parts[2]) - 1)
                    return self.send(200 if ok else 404, board.state())
                if parts == ["api", "setup", "check"]:
                    devs = check_devices(board.setup, refresh=not board.audio_ready)
                    if not board.audio_ready and engine is not None:
                        engine.start(devs)
                    board.setup.print()
                    return self.send(200, setup_info(board))
                if parts == ["api", "quit"]:
                    self.send(200, {"ok": True})
                    print("\nBeenden angefordert (Spiel geschlossen).")
                    QUIT.set()
                    return
                if parts == ["api", "test"]:
                    if not board.test_tone():
                        raise ValueError("Audio läuft nicht – siehe Einrichtungs-Check")
                    return self.send(200, setup_info(board))
                if parts == ["api", "stop"]:
                    board.stop()
                    return self.send(200, board.state())
                if parts == ["api", "reload"]:
                    board.reload()
                    return self.send(200, board.state())
                if parts == ["api", "volume"]:
                    board.set_volume(json.loads(self.body())["value"])
                    return self.send(200, board.state())
                if parts == ["api", "import"]:
                    req = json.loads(self.body())
                    idx = int(req["slot"]) - 1
                    if not 0 <= idx < NSLOTS:
                        raise ValueError("Ungültiger Platz")
                    name, data = download_sound(req["url"])
                    board.store(idx, name, data, req.get("label"))
                    return self.send(200, board.state())
                if parts == ["api", "label"]:
                    req = json.loads(self.body())
                    board.set_label(int(req["slot"]) - 1, req.get("label", ""))
                    return self.send(200, board.state())
                if parts[:2] == ["api", "image"] and len(parts) == 3:
                    idx = int(parts[2]) - 1
                    if not 0 <= idx < NSLOTS:
                        raise ValueError("Ungültiger Platz")
                    name = board.add_image(self.body())
                    board.set_art(idx, image=name)
                    return self.send(200, board.state())
                if parts == ["api", "art"]:
                    req = json.loads(self.body())
                    board.set_art(int(req["slot"]) - 1, image=req.get("image"), emoji=req.get("emoji"))
                    return self.send(200, board.state())
                if parts == ["api", "fetchimage"]:
                    # Bild von einem Link holen; verkleinert wird danach im Browser
                    url = json.loads(self.body())["url"].strip()
                    if not re.match(r"^https?://", url):
                        url = "https://" + url
                    data, _ = fetch(url, limit=8 * 1024 * 1024)
                    kind = image_type(data)
                    if not kind:
                        raise ValueError("Der Link zeigt nicht direkt auf ein Bild (PNG, JPG, GIF, WebP)")
                    return self.send(200, data, IMAGE_TYPES[kind])
                if parts[:2] == ["api", "upload"] and len(parts) == 3:
                    idx = int(parts[2]) - 1
                    if not 0 <= idx < NSLOTS:
                        raise ValueError("Ungültiger Platz")
                    name = urllib.parse.unquote(self.headers.get("X-Filename", "sound.wav"))
                    board.store(idx, name, self.body(), use_meta=True)
                    return self.send(200, board.state())
                self.send(404, {"error": "nicht gefunden"})
            except Exception as e:
                self.send(400, {"error": str(e)})

    return Handler


def setup_info(board):
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
    board.reload()
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
        if not e.is_keypad:
            return
        sc = e.scan_code
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
