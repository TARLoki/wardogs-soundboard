# English quick guide

> The interface and the detailed guide are currently **German only**. This page covers the essentials.

**WARDOGS Soundboard** plays meme sounds in the WARDOGS proximity voice chat via your numpad. The game is **not modified**: the soundboard mixes your microphone with the sounds and feeds both into the game through the free virtual audio cable **VB-Cable**.

## Setup

1. Download the latest `WARDOGS-Soundboard-v….zip` from **[Releases](https://github.com/TARLoki/wardogs-soundboard/releases/latest)**. Right-click → Properties → **Unblock** → extract to e.g. `C:\Games\WARDOGS-Soundboard` (**not** `C:\Program Files`).
2. Install **[Python 3.14](https://www.python.org/downloads/)** – tick **"Add python.exe to PATH"**.
3. In PowerShell inside that folder: `python -m pip install -r requirements.txt`
4. Install **[VB-Cable](https://vb-audio.com/Cable/)** (run setup as administrator) and **reboot**.
5. `Win + R` → `mmsys.cpl`: set your **headset** (Playback) and **microphone** (Recording) as default – **not** CABLE.
6. Run `start.bat`. The browser opens `http://localhost:8765`; under **Anleitung** (guide) the setup check should be all green.
7. In WARDOGS select **CABLE Output (VB-Audio Virtual Cable)** as microphone.
8. In Discord select your **microphone** explicitly (not "Default"), so Discord doesn't transmit the sounds.

## Usage

| Key | Action |
|---|---|
| Numpad 0–9, `,` `/` `*` `-` `+`, NumLock | play sound (16 slots) |
| same key again | stop that sound |
| Numpad Enter | stop all |

- Add sounds: click a tile → paste a [Myinstants](https://www.myinstants.com) page link into **Sound** → **Speichern** (save). Or drag an audio file onto a tile.
- **Titel** = custom title (leave empty for automatic).
- **Bild oder Emoji** = image or emoji as tile background: file, Ctrl+V, image link, library or emoji picker – or drop an image onto a tile. It is tied to the sound and reset when the sound is replaced; images stay in the library (`sounds\images`).
- Push-to-talk: while a sound plays, the soundboard holds **K** – only when WARDOGS is the active window. Change with `PTT_KEY` in `soundboard.py`, or `PTT_KEY = None` to disable.
- Keep the console window open while playing – your voice runs through the soundboard.
- When a new release is published, a green notice with a download link appears at the top (checked via GitHub every 12 hours; `CHECK_UPDATES = False` disables it). Update by copying the program files – keep your `sounds` folder.

## Notes

Unofficial tool, not affiliated with Bulkhead – use at your own risk. No sounds included. Play fair: spamming gets you muted.
