"""
WARDOGS + Soundboard - Startskript
==================================
1. Startet das Soundboard (Konsole minimiert, ohne Browser), falls es nicht schon läuft
2. Öffnet die Webseiten aus OPEN_URLS im Browser (Soundboard-Oberfläche und Helfer-Seiten)
3. Startet WARDOGS über Steam (steam://rungameid/...), also mit Anti-Cheat und Updates wie gewohnt
4. Wartet, bis das Spiel läuft, und beendet das Soundboard, sobald das Spiel geschlossen wurde

Wird über die Desktopverknüpfung mit pythonw.exe gestartet (kein eigenes Fenster).
Die Verknüpfung legt verknuepfung_anlegen.py an.

Protokoll jedes Starts: launcher.log im selben Ordner.
"""

import ctypes
import os
import re
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

# ============================ Konfiguration ============================

APP_ID = "1867240"            # Steam-App-ID von WARDOGS
GAME_PREFIX = "wardogs"       # Prozesse, deren Name so beginnt, gelten als "Spiel läuft"
WAIT_FOR_GAME = 15 * 60       # so lange auf den Spielstart warten (Steam-Updates!), Sekunden
GONE_GRACE = 20               # Spiel muss so lange weg sein, bevor das Soundboard endet
AUTO_QUIT = True              # Soundboard beenden, wenn das Spiel geschlossen wird
PORT = 8765                   # muss zu WEB_PORT in soundboard.py passen
CONSOLE_TITLE = "WARDOGS Soundboard"

# Diese Seiten werden beim Start im Standard-Browser geöffnet (eine Zeile pro Seite,
# jeweils in Anführungszeichen und mit Komma). Leere Liste [] = nichts öffnen.
OPEN_URLS = [
    f"http://localhost:{PORT}",               # Soundboard-Oberfläche
    "https://wardogs.n4lab.dev",
    "https://wardogs.zone/loadouts/base",
]

# =======================================================================

BASE = Path(__file__).resolve().parent
LOG = BASE / "launcher.log"
NO_WINDOW = 0x08000000        # CREATE_NO_WINDOW
SHORTCUT_NAME = "WARDOGS + Soundboard.lnk"


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    if sys.stdout:            # unter pythonw gibt es keine Konsole
        try:
            print(line)
        except Exception:
            pass


# ----------------------------------------------------------------------
# Soundboard
# ----------------------------------------------------------------------

def soundboard_running() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/state", timeout=1).read()
        return True
    except Exception:
        return False


def python_exe() -> str:
    """python.exe neben dem laufenden Interpreter (wir laufen selbst unter pythonw.exe)."""
    exe = Path(sys.executable)
    cand = exe.with_name("python.exe")
    return str(cand if cand.exists() else exe)


def minimize_console():
    """Konsolenfenster per Titel suchen und minimieren (Windows Terminal ignoriert sonst den Startmodus)."""
    user32 = ctypes.windll.user32
    for _ in range(60):
        hwnd = user32.FindWindowW(None, CONSOLE_TITLE)
        if hwnd:
            user32.ShowWindow(hwnd, 6)          # SW_MINIMIZE
            return True
        time.sleep(0.25)
    return False


def start_soundboard() -> bool:
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7                           # SW_SHOWMINNOACTIVE
    subprocess.Popen([python_exe(), str(BASE / "soundboard.py"), "--no-browser"],
                     cwd=str(BASE), creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=si)
    if not minimize_console():
        log("Hinweis: Konsolenfenster nicht gefunden, konnte es nicht minimieren.")
    for _ in range(60):                          # bis zu 30 s auf die Weboberfläche warten
        if soundboard_running():
            return True
        time.sleep(0.5)
    return False


def quit_soundboard():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/quit", data=b"", method="POST")
        urllib.request.urlopen(req, timeout=3).read()
        log("Soundboard beendet.")
    except Exception as e:
        log(f"Soundboard konnte nicht beendet werden: {e}")


# ----------------------------------------------------------------------
# Spiel
# ----------------------------------------------------------------------

def game_processes():
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             creationflags=NO_WINDOW, timeout=10).stdout.decode("mbcs", "ignore")
    except Exception:
        return []
    names = set()
    for line in out.splitlines():
        if line.startswith('"'):
            name = line.split('","', 1)[0].strip('"')
            if name.lower().startswith(GAME_PREFIX):
                names.add(name)
    return sorted(names)


def open_pages():
    for url in OPEN_URLS:
        try:
            webbrowser.open_new_tab(url)
            log(f"Geöffnet: {url}")
            time.sleep(0.4)                      # Reihenfolge der Tabs beibehalten
        except Exception as e:
            log(f"Konnte {url} nicht öffnen: {e}")


def start_game():
    os.startfile(f"steam://rungameid/{APP_ID}")


def wait_for_game():
    t0 = time.time()
    while time.time() - t0 < WAIT_FOR_GAME:
        procs = game_processes()
        if procs:
            return procs
        time.sleep(2)
    return []


def wait_until_game_closed():
    gone_since = None
    seen = set()
    while True:
        time.sleep(3)
        procs = game_processes()
        if procs:
            new = set(procs) - seen
            if new:
                log(f"Spielprozesse: {', '.join(sorted(seen | new))}")
                seen |= new
            gone_since = None
        else:
            gone_since = gone_since or time.time()
            if time.time() - gone_since >= GONE_GRACE:
                return


# ----------------------------------------------------------------------
# Desktopverknüpfung
# ----------------------------------------------------------------------

def desktop_dir() -> Path:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)   # CSIDL_DESKTOPDIRECTORY
    return Path(buf.value)


def steam_libraries():
    libs = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
        libs.append(steam)
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
                libs.append(Path(m.group(1).replace("\\\\", "\\")))
    except Exception:
        pass
    return libs


def find_game_dir():
    for lib in steam_libraries():
        acf = lib / "steamapps" / f"appmanifest_{APP_ID}.acf"
        if acf.exists():
            m = re.search(r'"installdir"\s+"([^"]+)"', acf.read_text(encoding="utf-8", errors="ignore"))
            if m:
                d = lib / "steamapps" / "common" / m.group(1)
                if d.exists():
                    return d
    return None


def find_icon():
    game = find_game_dir()
    if game:
        exes = sorted(game.glob("*.exe")) + sorted(game.glob("*/Binaries/Win64/*.exe"))
        for e in exes:
            if e.name.lower().startswith(GAME_PREFIX):
                return e
        if exes:
            return exes[0]
    for lib in steam_libraries()[:1]:
        if (lib / "steam.exe").exists():
            return lib / "steam.exe"
    return None


def install_shortcut():
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        raise SystemExit(f"pythonw.exe nicht gefunden neben {sys.executable}")
    target = desktop_dir() / SHORTCUT_NAME
    icon = find_icon()

    def q(v):                                    # PowerShell-String in einfachen Anführungszeichen
        return "'" + str(v).replace("'", "''") + "'"

    cmds = [
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({q(target)})",
        f"$s.TargetPath = {q(pythonw)}",
        f"$s.Arguments = {q(chr(34) + str(BASE / 'wardogs_start.pyw') + chr(34))}",
        f"$s.WorkingDirectory = {q(BASE)}",
        "$s.Description = 'WARDOGS mit Soundboard starten'",
    ]
    if icon:
        cmds.append(f"$s.IconLocation = {q(str(icon) + ',0')}")
    cmds.append("$s.Save()")
    ps = "; ".join(cmds)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0 or not target.exists():
        raise SystemExit(f"Verknüpfung konnte nicht angelegt werden:\n{r.stderr.strip()}")
    print(f"Verknüpfung angelegt: {target}")
    print(f"Symbol: {icon or 'Standard (WARDOGS-Ordner nicht gefunden)'}")


# ----------------------------------------------------------------------

def main():
    if "--install" in sys.argv:
        install_shortcut()
        return

    try:
        LOG.write_text("", encoding="utf-8")     # Protokoll pro Start neu
    except Exception:
        pass
    log("Start")

    if soundboard_running():
        log("Soundboard läuft bereits.")
    elif start_soundboard():
        log("Soundboard gestartet (minimiert).")
    else:
        log("Soundboard startet nicht - Spiel wird trotzdem gestartet. "
            "Zum Prüfen soundboard.py einmal direkt starten.")

    open_pages()
    log("Starte WARDOGS über Steam ...")
    start_game()

    if not AUTO_QUIT:
        return
    procs = wait_for_game()
    if not procs:
        log("WARDOGS wurde nicht gestartet - Soundboard bleibt offen.")
        return
    log(f"WARDOGS läuft ({', '.join(procs)}).")
    wait_until_game_closed()
    log("WARDOGS geschlossen.")
    quit_soundboard()


if __name__ == "__main__":
    main()
