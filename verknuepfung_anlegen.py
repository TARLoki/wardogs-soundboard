"""
Legt auf dem Desktop die Verknüpfung "WARDOGS + Soundboard" an.
Einfach doppelklicken (oder: python verknuepfung_anlegen.py).
"""
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--install"]
    try:
        runpy.run_path(str(Path(__file__).with_name("wardogs_start.pyw")), run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            print(e.code)
    except Exception as e:
        print(f"Fehler: {e}")
    input("\nEnter drücken zum Schließen ...")
