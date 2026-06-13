<div align="center">

# Tith Worker

**Record · Automate · Repeat**

A lightweight Windows desktop app for recording your mouse and keyboard
actions and replaying them — with human-like timing, scheduling, idle
auto-start and built-in safety stops.

[Features](#features) · [Requirements](#minimum-requirements) · [Installation](#installation) · [User Manual](#user-manual) · [Safety](#safety--emergency-stops) · [Troubleshooting](#troubleshooting)

</div>

---

## Overview

Tith Worker captures every mouse move, click, scroll and keystroke into a
named **macro**, then plays it back on demand, on a schedule, or when your
computer goes idle. An optional *human-like* mode adds small timing
variations and micro-pauses so playback looks less robotic.

It is built with Python and Tkinter and runs as a single windowed app that
can be minimized to the system tray.

---

## Features

| Category | What it does |
| --- | --- |
| 🎬 **Recording** | Capture mouse moves, clicks, scrolls and keystrokes into a named macro. Clicks on the app's own window are filtered out automatically. |
| ▶️ **Playback** | Play a single macro, all macros in order, or all macros in random order. Loop a fixed number of times or infinitely. |
| 🧠 **Human-like mode** | Adds 10–20% timing jitter, natural mouse-move durations and occasional micro-pauses. |
| 🗂️ **Macro manager** | Rename, delete, clean and inspect saved macros from a dedicated tab. |
| 🕒 **Scheduler** | Automatically run macros within a daily time window on selected weekdays. |
| 💤 **Idle auto-start** | Start playback after the computer has been idle for a configurable number of minutes. Any keypress stops it. |
| 📊 **Stats & logs** | Tracks total runs, total active time and last run, plus a live activity log. |
| 🛟 **Safety stops** | `F9`, `F10`, top-left corner emergency stop, and a configurable playback hotkey. |
| 🖥️ **System tray** | Minimize to tray and restore from the tray menu. |

---

## Minimum Requirements

| Requirement | Minimum |
| --- | --- |
| **Operating system** | Windows 10 (64-bit) or Windows 11 or any Windows|
| **Python** | 3.10 or newer (3.12 recommended) |
| **RAM** | 256 MB free |
| **Disk** | ~50 MB (including dependencies) |
| **Permissions** | Standard user account (no admin required for normal use) |

> **Note:** Tith Worker uses global mouse/keyboard hooks. Some security
> software may ask you to allow this the first time you run it.

---

## Installation

### 1. Install Python

Download and install **Python 3.10+** from
[python.org/downloads](https://www.python.org/downloads/).
During setup, tick **"Add Python to PATH"**.

Verify the installation:

```powershell
python --version
```

### 2. Get the project

Clone the repository (or download the ZIP and extract it):

```powershell
git clone https://github.com/ponir57/Tith-worker.git
cd Tith-worker
```

### 3. Create a virtual environment (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If PowerShell blocks the activation script, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then retry.

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

### 5. Run the app

```powershell
python main.py
```

The Tith Worker window should appear. You're ready to record.

---

## User Manual

The interface is organized into four tabs: **Record**, **Macros**,
**Scheduler**, and **Stats & Log**. A status bar at the bottom always shows
the current state (Idle / Recording / Countdown / Playing) and the safety
shortcuts.

### 1. Record a macro

1. Open the **Record** tab.
2. Type a name in the **Macro Name** field (e.g. `login_sequence`).
3. Click **⏺ Start Recording**. The status bar turns red.
4. Perform the mouse and keyboard actions you want to capture.
5. Press **`F9`** (or click **⏹ Stop & Save**) to finish.
   The macro is cleaned automatically and saved to the `macros/` folder.

> `F9` is reserved as the global *Stop Recording* key and is never recorded.

### 2. Play a macro

**From the Record tab** — play the macro you just recorded with
**▶ Play Current**.

**From the Macros tab:**

- **▶ Play Selected** — play the highlighted macro (or double-click it).
- **▶▶ Play All (in order)** — play every saved macro alphabetically.
- **🔀 Play All (random)** — play every saved macro in random order.

A **3-second countdown** runs before playback so you can position windows.
Switch to your target application during the countdown.

### 3. Playback options (Record tab)

| Option | Description |
| --- | --- |
| **Loops → Infinite** | Repeat until you stop it manually. |
| **Loops → Fixed** | Repeat an exact number of times. |
| **Max loops (safety)** | Hard upper limit that always applies. |
| **Human-like playback** | Adds timing jitter and micro-pauses for natural motion. |
| **Playback stop hotkey** | Change the key that stops playback (default `F10`). Accepts combos like `ctrl+shift+s`. |

### 4. Manage macros (Macros tab)

- **✨ Clean Selected** — remove stray `F9`/`F10` key events and accidental
  clicks on the app window.
- **✏ Rename** — give a macro a new name.
- **🗑 Delete** — permanently remove a macro (asks for confirmation).
- **↻ Refresh** — reload the macro list from disk.

### 5. Schedule playback (Scheduler tab)

1. Tick **Enable Scheduler**.
2. Set a **Start** and **End** time (`HH:MM`, 24-hour).
3. Choose the **Days of Week** to run on.
4. Click **Apply Schedule**.

When the current time enters the window on an enabled day, all saved macros
play in order. Each window fires at most once per day.

### 6. Idle auto-start (Scheduler tab)

1. Tick **Auto-start playback when idle**.
2. Set the **Idle threshold** in minutes.
3. Choose a specific macro, or leave it on *(all macros in order)*.
4. Click **Apply**.

After the computer is idle for the threshold, playback begins automatically.
**Any keyboard press immediately stops idle playback.**

### 7. Stats & log (Stats & Log tab)

- View **Total runs**, **Total active time** and **Last run**.
- **Reset Stats** clears the counters.
- The **Activity Log** shows live events. Use **Open Log File** to view the
  full history (`logs/activity.log`) or **Clear Display** to clear the view.

### 8. System tray

Closing the window asks whether to **minimize to tray**, **exit completely**,
or **cancel**. From the tray icon you can **Show** the window again or
**Quit** the app.

---

## Safety & Emergency Stops

Tith Worker automates real input, so it ships with several ways to stop it
instantly:

| Trigger | Effect |
| --- | --- |
| **`F9`** | Stops recording (system-wide, always reserved). |
| **`F10`** *(configurable)* | Stops playback or the countdown. |
| **Mouse to top-left corner** | Emergency stop — instantly halts playback. |
| **Any keypress during idle play** | Cancels idle-triggered playback. |
| **Moving the mouse / typing** | Cancels idle auto-start once active again. |

---

## Project Structure

```
tith-worker/
├── main.py            # GUI entry point and application logic
├── recorder.py        # Captures mouse/keyboard input into a macro
├── player.py          # Replays macros with optional human-like timing
├── idle_detector.py   # Detects user inactivity for idle auto-start
├── scheduler.py       # Time-window / weekday scheduler
├── requirements.txt   # Python dependencies
├── macros/            # Saved macros (.json) — created at runtime
├── logs/              # Activity log — created at runtime
├── LICENSE
└── README.md
```

---

## Troubleshooting

| Problem | Solution |
| --- | --- |
| **`pip` install fails on `pyautogui`/`Pillow`** | Upgrade pip first: `python -m pip install --upgrade pip`, then retry. |
| **Hotkeys don't respond** | The `keyboard` library needs permission to capture global keys. Try running the terminal as Administrator. |
| **Playback clicks land in the wrong place** | Screen scaling can offset coordinates. Set Windows display scaling to 100% and re-record. |
| **Tray icon doesn't appear** | Ensure `pystray` and `Pillow` installed correctly: `pip install -r requirements.txt`. |
| **App window won't close** | Choose **No** in the close dialog to exit completely, or use **Quit** from the tray menu. |

---

## Disclaimer

Tith Worker is provided for legitimate automation of repetitive tasks on
systems you own or are authorized to use. You are responsible for complying
with the terms of service of any application you automate. The authors accept
no liability for misuse.

---

## License

Released under the [MIT License](LICENSE).
