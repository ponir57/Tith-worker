"""
Tith Worker — GUI entry point.

A macro recorder and player with human-like playback, scheduling and an
idle auto-start engine.

Safety shortcuts:
    F9                = Stop recording (never recorded; suppressed system-wide)
    F10               = Stop playback  (configurable)
    Mouse to top-left = Emergency stop during playback.
"""

import os
import json
import time
import random
import threading
import datetime
import logging
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import keyboard

from recorder import MacroRecorder, FILTERED_KEYS
from player import MacroPlayer
from idle_detector import IdleDetector
from scheduler import MacroScheduler

# ── Branding ─────────────────────────────────────────────────────────────────

APP_NAME    = "Tith Worker"
APP_TAGLINE = "Record · Automate · Repeat"
APP_VERSION = "1.0.0"

# ── Paths ──────────────────────────────────────────────────────────────────────

# Anchor all runtime paths to the application directory so the program works the
# same regardless of the directory it is launched from.
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MACROS_DIR = os.path.join(BASE_DIR, "macros")
LOGS_DIR   = os.path.join(BASE_DIR, "logs")
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
LOG_FILE   = os.path.join(LOGS_DIR, "activity.log")

os.makedirs(MACROS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,   exist_ok=True)

COUNTDOWN_SECS = 3

# ── Dark theme palette ─────────────────────────────────────────────────────────

_BG      = "#181a1f"   # main window background
_BG2     = "#21242b"   # panel / frame background
_BG3     = "#2b2f38"   # input field / surface background
_BG_HOV  = "#343943"   # hovered surface
_FG      = "#e6e8ec"   # primary text
_FG2     = "#9aa0ab"   # secondary / disabled text
_ACC     = "#3d7eff"   # accent (brand blue)
_ACC_HOV = "#5a92ff"   # accent hover
_BORD    = "#343943"   # border
_RED     = "#f0616d"
_RED_HOV = "#ff7882"
_GRN     = "#3fcaa3"
_ORG     = "#e0a85a"


# ── App ────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("760x640")
        self.minsize(720, 600)
        self.configure(bg=_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Window-bounds cache — updated from main thread, read from recorder thread
        self._win_bounds = None

        # Core state
        self._recorder = MacroRecorder(
            on_action_recorded=self._update_count,
            is_app_click=self._is_app_click,
        )
        self._player: MacroPlayer | None = None
        self._state = "idle"     # idle | recording | countdown | playing
        self._current_name: str = ""
        self._play_stop_hotkey = "f10"

        # Background services
        self._idle_detector = IdleDetector(
            threshold_seconds=300,
            on_idle=self._on_idle_triggered,
            on_active=self._on_user_active,
        )
        self._scheduler = MacroScheduler(on_trigger=self._on_schedule_trigger)

        # Persistence
        self._stats = self._load_stats()
        self._setup_logging()

        # Hotkeys
        # F9 — stop recording; suppress=True so pynput never sees it
        keyboard.add_hotkey("f9",  self._hotkey_stop_recording, suppress=True)
        # F10 — stop playback (configurable)
        keyboard.add_hotkey(self._play_stop_hotkey,
                            self._hotkey_stop_playback, suppress=False)

        # Build UI, then start services
        self._build_ui()

        # Start tracking window position for app-click filter
        self.bind("<Configure>", self._update_win_bounds)
        self.after(100, self._poll_win_bounds)

        self._idle_detector.start()
        self._scheduler.start()
        self._start_corner_monitor()

        self._tray_icon = None
        self.after(600, self._setup_tray)

    # ── Window-bounds tracking (thread-safe cache) ─────────────────────────────

    def _update_win_bounds(self, _event=None):
        try:
            self._win_bounds = (
                self.winfo_rootx(), self.winfo_rooty(),
                self.winfo_width(), self.winfo_height(),
            )
        except Exception:
            pass

    def _poll_win_bounds(self):
        """Periodic refresh so bounds stay fresh even without resize events."""
        self._update_win_bounds()
        try:
            if self.winfo_exists():
                self.after(800, self._poll_win_bounds)
        except Exception:
            pass

    def _is_app_click(self, x: int, y: int) -> bool:
        """Return True if (x, y) falls within the app window. Thread-safe."""
        b = self._win_bounds
        if b is None:
            return False
        wx, wy, ww, wh = b
        return wx <= x <= wx + ww and wy <= y <= wy + wh

    # ── Logging & stats ────────────────────────────────────────────────────────

    def _setup_logging(self):
        self._logger = logging.getLogger("TithWorker")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            self._logger.addHandler(fh)
        self._log(f"{APP_NAME} started.")

    def _log(self, msg: str):
        self._logger.info(msg)
        if hasattr(self, "_log_text"):
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self.after(0, lambda m=msg, t=ts: self._append_log_line(f"[{t}] {m}"))

    def _append_log_line(self, line: str):
        self._log_text.config(state="normal")
        self._log_text.insert("end", line + "\n")
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def _load_stats(self) -> dict:
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"total_runs": 0, "total_time": 0.0, "last_run": None}

    def _save_stats(self):
        try:
            with open(STATS_FILE, "w") as f:
                json.dump(self._stats, f, indent=2)
        except Exception:
            pass

    def _record_play_stats(self, loops_done: int, elapsed: float):
        self._stats["total_runs"] += loops_done
        self._stats["total_time"] += elapsed
        self._stats["last_run"]    = datetime.datetime.now().isoformat(timespec="seconds")
        self._save_stats()
        self.after(0, self._refresh_stats_labels)

    # ── Macro file helpers ─────────────────────────────────────────────────────

    def _list_macros(self) -> list[str]:
        try:
            return sorted(f[:-5] for f in os.listdir(MACROS_DIR)
                          if f.endswith(".json"))
        except Exception:
            return []

    def _macro_path(self, name: str) -> str:
        return os.path.join(MACROS_DIR, f"{name}.json")

    def _load_macro(self, name: str) -> list:
        with open(self._macro_path(name)) as f:
            return json.load(f)

    def _sanitize_name(self, raw: str) -> str:
        name = "".join(c for c in raw if c.isalnum() or c in "_ -").strip()
        return name or "unnamed"

    # ── Macro cleaning & validation ────────────────────────────────────────────

    def _clean_macro_actions(self, actions: list) -> list:
        """Remove filtered keys and accidental app-window clicks."""
        cleaned = []
        for a in actions:
            t = a.get("type", "")
            if t in ("key_press", "key_release"):
                if a.get("key") in FILTERED_KEYS:
                    continue
            if t == "click":
                x, y = a.get("x", -1), a.get("y", -1)
                if self._is_app_click(x, y):
                    continue
            cleaned.append(a)
        return cleaned

    def _validate_macro(self, actions: list) -> tuple[bool, str]:
        """
        Return (ok, warning_message).
        Validates the action list before playback starts.
        """
        if not actions:
            return False, "Macro has no actions."
        key_events = [a for a in actions
                      if a.get("type") in ("key_press", "key_release")
                      and a.get("key") in FILTERED_KEYS]
        if key_events:
            return False, (
                f"Macro contains {len(key_events)} filtered key event(s) "
                f"(F9/F10). Use 'Clean Macro' to remove them before playback."
            )
        return True, ""

    # ── Dark theme setup ───────────────────────────────────────────────────────

    def _setup_dark_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".",
            background=_BG2, foreground=_FG,
            fieldbackground=_BG3, troughcolor=_BG,
            bordercolor=_BORD, darkcolor=_BG2, lightcolor=_BG3,
            relief="flat", font=("Segoe UI", 10))

        style.configure("TFrame", background=_BG2)

        style.configure("TLabelframe",
            background=_BG2, bordercolor=_BORD, relief="groove")
        style.configure("TLabelframe.Label",
            background=_BG2, foreground=_ACC,
            font=("Segoe UI", 9, "bold"))

        style.configure("TLabel", background=_BG2, foreground=_FG)

        style.configure("TButton",
            background=_BG3, foreground=_FG,
            padding=(10, 7), relief="flat", borderwidth=0,
            font=("Segoe UI", 10))
        style.map("TButton",
            background=[("active", _BG_HOV), ("disabled", _BG2)],
            foreground=[("active", _FG), ("disabled", _FG2)],
            relief=[("pressed", "flat")])

        # Primary call-to-action button (accent fill)
        style.configure("Accent.TButton",
            background=_ACC, foreground="#ffffff",
            padding=(10, 7), relief="flat", borderwidth=0,
            font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton",
            background=[("active", _ACC_HOV), ("disabled", _BG2)],
            foreground=[("disabled", _FG2)])

        # Destructive button (red fill)
        style.configure("Danger.TButton",
            background=_RED, foreground="#ffffff",
            padding=(10, 7), relief="flat", borderwidth=0,
            font=("Segoe UI", 10, "bold"))
        style.map("Danger.TButton",
            background=[("active", _RED_HOV), ("disabled", _BG2)],
            foreground=[("disabled", _FG2)])

        style.configure("TEntry",
            fieldbackground=_BG3, foreground=_FG,
            insertcolor=_FG, bordercolor=_BORD)
        style.map("TEntry", bordercolor=[("focus", _ACC)])

        style.configure("TSpinbox",
            fieldbackground=_BG3, foreground=_FG,
            bordercolor=_BORD, arrowcolor=_FG2,
            insertcolor=_FG)

        style.configure("TCombobox",
            fieldbackground=_BG3, foreground=_FG,
            bordercolor=_BORD, arrowcolor=_FG2,
            selectbackground=_ACC, selectforeground="#ffffff")
        style.map("TCombobox",
            fieldbackground=[("readonly", _BG3)],
            bordercolor=[("focus", _ACC)])

        style.configure("TNotebook", background=_BG, borderwidth=0,
            tabmargins=[2, 4, 2, 0])
        style.configure("TNotebook.Tab",
            background=_BG, foreground=_FG2,
            padding=[16, 8], font=("Segoe UI", 10), borderwidth=0)
        style.map("TNotebook.Tab",
            background=[("selected", _BG2), ("active", _BG3)],
            foreground=[("selected", _FG), ("active", _FG)],
            expand=[("selected", [1, 1, 1, 0])])

        style.configure("TCheckbutton", background=_BG2, foreground=_FG)
        style.map("TCheckbutton",
            background=[("active", _BG2)],
            foreground=[("active", _FG)])

        style.configure("TRadiobutton", background=_BG2, foreground=_FG)
        style.map("TRadiobutton",
            background=[("active", _BG2)],
            foreground=[("active", _FG)])

        style.configure("TScrollbar",
            background=_BG3, troughcolor=_BG,
            arrowcolor=_FG2, borderwidth=0)
        style.map("TScrollbar", background=[("active", _ACC)])

        style.configure("TSeparator", background=_BORD)

        # Header bar
        style.configure("Header.TFrame", background=_BG)
        style.configure("HeaderTitle.TLabel",
            background=_BG, foreground=_FG,
            font=("Segoe UI Semibold", 17))
        style.configure("HeaderTag.TLabel",
            background=_BG, foreground=_ACC,
            font=("Segoe UI", 9))
        style.configure("HeaderVer.TLabel",
            background=_BG, foreground=_FG2,
            font=("Segoe UI", 9))

        # Status bar variant — slightly different background
        style.configure("Status.TFrame", background=_BG3)
        style.configure("Status.TLabel",
            background=_BG3, foreground=_FG2,
            font=("Segoe UI", 9))
        style.configure("StateLabel.TLabel",
            background=_BG3, foreground=_FG,
            font=("Segoe UI", 11, "bold"))

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._setup_dark_theme()

        # ── Header bar (brand) ─────────────────────────────────────────────────
        hf = ttk.Frame(self, style="Header.TFrame")
        hf.pack(side="top", fill="x", padx=14, pady=(12, 4))

        logo = tk.Canvas(hf, width=34, height=34, bg=_BG,
                         highlightthickness=0, bd=0)
        logo.create_oval(2, 2, 32, 32, fill=_ACC, outline="")
        logo.create_polygon(13, 10, 13, 24, 25, 17, fill="#ffffff", outline="")
        logo.pack(side="left", padx=(0, 10))

        title_box = ttk.Frame(hf, style="Header.TFrame")
        title_box.pack(side="left", anchor="w")
        ttk.Label(title_box, text=APP_NAME,
                  style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(title_box, text=APP_TAGLINE,
                  style="HeaderTag.TLabel").pack(anchor="w")

        ttk.Label(hf, text=f"v{APP_VERSION}",
                  style="HeaderVer.TLabel").pack(side="right", anchor="n")

        ttk.Separator(self, orient="horizontal").pack(side="top", fill="x",
                                                       padx=14, pady=(4, 0))

        # ── Status bar (always visible at bottom) ──────────────────────────────
        sf = ttk.Frame(self, style="Status.TFrame", relief="flat")
        sf.pack(side="bottom", fill="x")

        # Left: state indicator
        self._lbl_state = ttk.Label(
            sf, text="\u26aa Idle",
            style="StateLabel.TLabel", width=20, anchor="w")
        self._lbl_state.pack(side="left", padx=(10, 4), pady=5)

        self._lbl_ctx = ttk.Label(
            sf, text="", style="Status.TLabel", width=26, anchor="w")
        self._lbl_ctx.pack(side="left", pady=5)

        # Right: hotkey reference
        ttk.Label(
            sf,
            text="F9 = Stop Recording  \u2502  F10 = Stop Playback  \u2502  Top-left = Emergency Stop",
            style="Status.TLabel",
        ).pack(side="right", padx=10, pady=5)

        # ── Notebook ───────────────────────────────────────────────────────────
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=6, pady=(6, 0))

        self._tab_record    = ttk.Frame(self._nb)
        self._tab_macros    = ttk.Frame(self._nb)
        self._tab_scheduler = ttk.Frame(self._nb)
        self._tab_stats     = ttk.Frame(self._nb)

        self._nb.add(self._tab_record,    text="  \u23fa  Record  ")
        self._nb.add(self._tab_macros,    text="  \U0001f4c2  Macros  ")
        self._nb.add(self._tab_scheduler, text="  \U0001f552  Scheduler  ")
        self._nb.add(self._tab_stats,     text="  \U0001f4ca  Stats & Log  ")

        self._nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self._build_record_tab()
        self._build_macros_tab()
        self._build_scheduler_tab()
        self._build_stats_tab()

    # ── Record tab ─────────────────────────────────────────────────────────────

    def _build_record_tab(self):
        tab = self._tab_record
        pad = dict(padx=10, pady=5)

        # Name
        nf = ttk.LabelFrame(tab, text="Macro Name")
        nf.pack(fill="x", **pad)
        ttk.Label(nf, text="Name:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self._name_var = tk.StringVar(value="my_macro")
        ttk.Entry(nf, textvariable=self._name_var, width=34).grid(
            row=0, column=1, padx=4, pady=6, sticky="ew")
        nf.columnconfigure(1, weight=1)

        # Controls
        cf = ttk.LabelFrame(tab, text="Controls")
        cf.pack(fill="x", **pad)

        self._btn_rec = ttk.Button(
            cf, text="\u23fa  Start Recording", style="Accent.TButton",
            command=self._cmd_start_rec, width=22)
        self._btn_rec.grid(row=0, column=0, padx=8, pady=8)

        self._btn_stop_rec = ttk.Button(
            cf, text="\u23f9  Stop & Save  (F9)", style="Danger.TButton",
            command=self._cmd_stop_rec, width=22)
        self._btn_stop_rec.grid(row=0, column=1, padx=8, pady=8)

        self._btn_play_cur = ttk.Button(
            cf, text="\u25b6  Play Current", style="Accent.TButton",
            command=self._cmd_play_current, width=22)
        self._btn_play_cur.grid(row=0, column=2, padx=8, pady=8)

        self._btn_clean = ttk.Button(
            cf, text="\u2728  Clean Macro",
            command=self._cmd_clean_current, width=22)
        self._btn_clean.grid(row=1, column=0, padx=8, pady=(0, 8))

        # Info
        inf = ttk.LabelFrame(tab, text="Recording Info")
        inf.pack(fill="x", **pad)
        self._lbl_count = ttk.Label(
            inf, text="Actions: 0", font=("Segoe UI", 11))
        self._lbl_count.pack(side="left", padx=10, pady=6)

        # Playback options
        pf = ttk.LabelFrame(tab, text="Playback Options")
        pf.pack(fill="x", **pad)

        ttk.Label(pf, text="Loops:").grid(row=0, column=0, padx=8, pady=6, sticky="w")
        self._loop_var = tk.StringVar(value="infinite")
        ttk.Radiobutton(pf, text="Infinite", variable=self._loop_var,
                        value="infinite", command=self._toggle_loop).grid(
                        row=0, column=1, padx=4)
        ttk.Radiobutton(pf, text="Fixed:", variable=self._loop_var,
                        value="fixed", command=self._toggle_loop).grid(
                        row=0, column=2, padx=4)
        self._spin_loops = ttk.Spinbox(pf, from_=1, to=99999, width=7,
                                       state="disabled")
        self._spin_loops.set(5)
        self._spin_loops.grid(row=0, column=3, padx=4)

        ttk.Label(pf, text="Max loops (safety):").grid(
            row=0, column=4, padx=(16, 4))
        self._spin_max = ttk.Spinbox(pf, from_=1, to=999999, width=8)
        self._spin_max.set(10000)
        self._spin_max.grid(row=0, column=5, padx=4)

        self._human_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            pf, text="\U0001f9d0  Human-like playback  (timing jitter + micro-pauses)",
            variable=self._human_var,
        ).grid(row=1, column=0, columnspan=6, padx=8, pady=(0, 6), sticky="w")

        # Playback stop hotkey (F9 for recording is always fixed)
        hkf = ttk.LabelFrame(tab, text="Playback Stop Hotkey  (F9 = Recording stop is always fixed)")
        hkf.pack(fill="x", **pad)
        ttk.Label(hkf, text="Playback hotkey:").grid(
            row=0, column=0, padx=8, pady=6, sticky="w")
        self._hk_var = tk.StringVar(value="f10")
        ttk.Entry(hkf, textvariable=self._hk_var, width=12).grid(
            row=0, column=1, padx=4, pady=6)
        ttk.Button(hkf, text="Apply", command=self._apply_hotkey).grid(
            row=0, column=2, padx=6, pady=6)
        ttk.Label(hkf, text="(e.g. f10, ctrl+shift+s)",
                  foreground=_FG2, font=("Segoe UI", 8)).grid(
                  row=0, column=3, padx=4)

    # ── Macros tab ─────────────────────────────────────────────────────────────

    def _build_macros_tab(self):
        tab = self._tab_macros

        lf = ttk.LabelFrame(tab, text="Saved Macros")
        lf.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        vsb = ttk.Scrollbar(lf, orient="vertical")
        self._macro_lb = tk.Listbox(
            lf, yscrollcommand=vsb.set, selectmode="single", height=16,
            font=("Segoe UI", 10), activestyle="dotbox",
            bg=_BG3, fg=_FG, selectbackground=_ACC, selectforeground="#ffffff",
            borderwidth=0, highlightthickness=0,
        )
        vsb.config(command=self._macro_lb.yview)
        self._macro_lb.pack(side="left", fill="both", expand=True,
                            padx=(4, 0), pady=4)
        vsb.pack(side="right", fill="y", pady=4)

        self._macro_lb.bind("<<ListboxSelect>>", self._on_macro_select)
        self._macro_lb.bind("<Double-Button-1>", lambda _: self._cmd_play_selected())

        bf = ttk.LabelFrame(tab, text="Actions")
        bf.pack(side="right", fill="y", padx=(0, 10), pady=10)
        bw = dict(width=22)

        ttk.Button(bf, text="\u25b6  Play Selected", style="Accent.TButton",
                   command=self._cmd_play_selected, **bw).pack(padx=8, pady=(8, 2))
        ttk.Button(bf, text="\u25b6\u25b6  Play All  (in order)",
                   command=self._cmd_play_all_ordered, **bw).pack(padx=8, pady=2)
        ttk.Button(bf, text="\U0001f500  Play All  (random)",
                   command=self._cmd_play_all_random, **bw).pack(padx=8, pady=2)

        ttk.Separator(bf, orient="horizontal").pack(fill="x", padx=8, pady=8)

        ttk.Button(bf, text="\u2728  Clean Selected",
                   command=self._cmd_clean_selected, **bw).pack(padx=8, pady=2)
        ttk.Button(bf, text="\u270f  Rename",
                   command=self._cmd_rename_macro, **bw).pack(padx=8, pady=2)
        ttk.Button(bf, text="\U0001f5d1  Delete", style="Danger.TButton",
                   command=self._cmd_delete_macro, **bw).pack(padx=8, pady=2)

        ttk.Separator(bf, orient="horizontal").pack(fill="x", padx=8, pady=8)

        ttk.Button(bf, text="\u21bb  Refresh",
                   command=self._refresh_macro_list, **bw).pack(padx=8, pady=2)

        self._lbl_macro_info = ttk.Label(
            bf, text="No macro selected.",
            font=("Segoe UI", 9), foreground=_FG2,
            wraplength=165, justify="center")
        self._lbl_macro_info.pack(padx=8, pady=10)

        self._refresh_macro_list()

    # ── Scheduler tab ──────────────────────────────────────────────────────────

    def _build_scheduler_tab(self):
        tab = self._tab_scheduler
        pad = dict(padx=10, pady=6)

        sf = ttk.LabelFrame(tab, text="Auto-Play Schedule")
        sf.pack(fill="x", **pad)

        self._sched_en = tk.BooleanVar(value=False)
        ttk.Checkbutton(sf, text="Enable Scheduler",
                        variable=self._sched_en,
                        command=self._apply_scheduler).grid(
                        row=0, column=0, columnspan=5,
                        padx=8, pady=6, sticky="w")

        ttk.Label(sf, text="Start (HH:MM):").grid(
            row=1, column=0, padx=8, pady=4, sticky="w")
        self._sched_start = tk.StringVar(value="09:00")
        ttk.Entry(sf, textvariable=self._sched_start, width=8).grid(
            row=1, column=1, padx=4, pady=4)

        ttk.Label(sf, text="End (HH:MM):").grid(
            row=1, column=2, padx=8, pady=4, sticky="w")
        self._sched_end = tk.StringVar(value="17:00")
        ttk.Entry(sf, textvariable=self._sched_end, width=8).grid(
            row=1, column=3, padx=4, pady=4)

        ttk.Button(sf, text="Apply Schedule",
                   command=self._apply_scheduler).grid(
                   row=1, column=4, padx=10, pady=4)

        df = ttk.LabelFrame(tab, text="Days of Week")
        df.pack(fill="x", **pad)
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        self._day_vars: list[tk.BooleanVar] = []
        for i, d in enumerate(day_names):
            v = tk.BooleanVar(value=(i < 5))
            self._day_vars.append(v)
            ttk.Checkbutton(df, text=d, variable=v,
                            command=self._apply_scheduler).grid(
                            row=0, column=i, padx=10, pady=8)

        idf = ttk.LabelFrame(tab, text="Idle Auto-Start")
        idf.pack(fill="x", **pad)

        self._idle_en = tk.BooleanVar(value=False)
        ttk.Checkbutton(idf, text="Auto-start playback when idle",
                        variable=self._idle_en,
                        command=self._apply_idle).grid(
                        row=0, column=0, columnspan=3,
                        padx=8, pady=6, sticky="w")

        ttk.Label(idf, text="Idle threshold (minutes):").grid(
            row=1, column=0, padx=8, pady=4, sticky="w")
        self._idle_thresh = tk.StringVar(value="5")
        ttk.Spinbox(idf, from_=1, to=120, textvariable=self._idle_thresh,
                    width=6, command=self._apply_idle).grid(
                    row=1, column=1, padx=4, pady=4)
        ttk.Button(idf, text="Apply", command=self._apply_idle).grid(
            row=1, column=2, padx=8, pady=4)

        ttk.Label(idf, text="Macro to play on idle:").grid(
            row=2, column=0, padx=8, pady=4, sticky="w")
        self._idle_macro_var = tk.StringVar(value="(all macros in order)")
        self._idle_combo = ttk.Combobox(idf, textvariable=self._idle_macro_var,
                                        width=26, state="readonly")
        self._idle_combo.grid(row=2, column=1, columnspan=2, padx=4, pady=4)

        ttk.Label(idf,
                  text="Note: any keyboard press stops idle-triggered playback.",
                  font=("Segoe UI", 8), foreground=_FG2).grid(
                  row=3, column=0, columnspan=3,
                  padx=8, pady=(0, 6), sticky="w")

    # ── Stats tab ──────────────────────────────────────────────────────────────

    def _build_stats_tab(self):
        tab = self._tab_stats
        pad = dict(padx=10, pady=6)

        stf = ttk.LabelFrame(tab, text="Statistics")
        stf.pack(fill="x", **pad)

        self._lbl_runs = ttk.Label(stf, text="Total runs: 0",
                                   font=("Segoe UI", 10))
        self._lbl_runs.grid(row=0, column=0, padx=14, pady=6, sticky="w")

        self._lbl_time = ttk.Label(stf, text="Total active time: 0s",
                                   font=("Segoe UI", 10))
        self._lbl_time.grid(row=0, column=1, padx=14, pady=6, sticky="w")

        self._lbl_last = ttk.Label(stf, text="Last run: never",
                                   font=("Segoe UI", 10))
        self._lbl_last.grid(row=1, column=0, columnspan=2,
                            padx=14, pady=(0, 6), sticky="w")

        ttk.Button(stf, text="Reset Stats",
                   command=self._cmd_reset_stats).grid(
                   row=0, column=2, padx=14, pady=6)

        lf = ttk.LabelFrame(tab, text="Activity Log")
        lf.pack(fill="both", expand=True, **pad)

        vsb = ttk.Scrollbar(lf, orient="vertical")
        self._log_text = tk.Text(
            lf, state="disabled", height=14,
            font=("Consolas", 9), yscrollcommand=vsb.set, wrap="word",
            bg=_BG3, fg=_FG, insertbackground=_FG,
            selectbackground=_ACC, borderwidth=0, highlightthickness=0,
        )
        vsb.config(command=self._log_text.yview)
        self._log_text.pack(side="left", fill="both", expand=True,
                            padx=(4, 0), pady=4)
        vsb.pack(side="right", fill="y", pady=4)

        bbf = ttk.Frame(tab)
        bbf.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Button(bbf, text="Clear Display",
                   command=self._clear_log_display).pack(side="left", padx=4)
        ttk.Button(bbf, text="Open Log File",
                   command=self._open_log_file).pack(side="left", padx=4)

        self._refresh_stats_labels()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _toggle_loop(self):
        self._spin_loops.config(
            state="normal" if self._loop_var.get() == "fixed" else "disabled")

    def _loop_count(self):
        if self._loop_var.get() == "infinite":
            return None
        try:
            return max(1, int(self._spin_loops.get()))
        except ValueError:
            return 1

    def _apply_hotkey(self):
        new_hk = self._hk_var.get().strip().lower()
        if not new_hk or new_hk == "f9":
            messagebox.showwarning("Invalid",
                "F9 is reserved for Stop Recording. Choose a different key.")
            return
        try:
            keyboard.remove_hotkey(self._play_stop_hotkey)
        except Exception:
            pass
        self._play_stop_hotkey = new_hk
        keyboard.add_hotkey(new_hk, self._hotkey_stop_playback, suppress=False)
        self._log(f"Playback stop hotkey changed to: {new_hk.upper()}")

    def _apply_scheduler(self):
        self._scheduler.enabled = self._sched_en.get()
        try:
            h, m = map(int, self._sched_start.get().split(":"))
            self._scheduler.start_time = datetime.time(h, m)
        except Exception:
            self._scheduler.start_time = None
        try:
            h, m = map(int, self._sched_end.get().split(":"))
            self._scheduler.end_time = datetime.time(h, m)
        except Exception:
            self._scheduler.end_time = None
        self._scheduler.days = {i for i, v in enumerate(self._day_vars) if v.get()}
        status = "enabled" if self._scheduler.enabled else "disabled"
        self._log(f"Scheduler {status}.")

    def _apply_idle(self):
        try:
            minutes = max(1, int(self._idle_thresh.get()))
        except ValueError:
            minutes = 5
        self._idle_detector.threshold = minutes * 60
        self._log(f"Idle threshold: {minutes} min.")

    def _on_tab_change(self, _event=None):
        idx = self._nb.index(self._nb.select())
        if idx == 2:
            options = ["(all macros in order)"] + self._list_macros()
            self._idle_combo["values"] = options

    def _refresh_macro_list(self):
        self._macro_lb.delete(0, "end")
        for name in self._list_macros():
            self._macro_lb.insert("end", name)

    def _on_macro_select(self, _event=None):
        sel = self._macro_lb.curselection()
        if not sel:
            return
        name = self._macro_lb.get(sel[0])
        try:
            actions = self._load_macro(name)
            self._lbl_macro_info.config(text=f"{name}\n{len(actions)} actions")
        except Exception:
            self._lbl_macro_info.config(text=f"{name}\n(read error)")

    def _selected_macro(self) -> str | None:
        sel = self._macro_lb.curselection()
        return self._macro_lb.get(sel[0]) if sel else None

    def _refresh_stats_labels(self):
        runs  = self._stats.get("total_runs", 0)
        secs  = self._stats.get("total_time", 0.0)
        last  = self._stats.get("last_run",   None)
        h, rem = divmod(int(secs), 3600)
        m, s   = divmod(rem, 60)
        self._lbl_runs.config(text=f"Total runs: {runs}")
        self._lbl_time.config(text=f"Total active time: {h}h {m}m {s}s")
        self._lbl_last.config(text=f"Last run: {last or 'never'}")

    def _clear_log_display(self):
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.config(state="disabled")

    def _open_log_file(self):
        import subprocess
        try:
            subprocess.Popen(["notepad", os.path.abspath(LOG_FILE)])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _update_count(self, n: int):
        self.after(0, lambda: self._lbl_count.config(text=f"Actions: {n}"))

    # ── State machine ──────────────────────────────────────────────────────────

    _STATE_LABELS = {
        "idle":      ("\u26aa Idle",           _FG2),
        "recording": ("\U0001f534 Recording\u2026", _RED),
        "countdown": ("\U0001f7e0 Countdown\u2026", _ORG),
        "playing":   ("\U0001f7e2 Playing\u2026",   _GRN),
    }

    def _set_state(self, state: str, ctx: str = ""):
        self._state = state
        label, color = self._STATE_LABELS.get(state, (state, _FG))
        self._lbl_state.config(text=label, foreground=color)
        self._lbl_ctx.config(text=ctx)
        self._refresh_buttons()

    def _refresh_buttons(self):
        s = self._state
        idle = s == "idle"
        self._btn_rec.config(state="normal" if idle else "disabled")
        self._btn_stop_rec.config(
            state="normal" if s == "recording" else "disabled")
        self._btn_play_cur.config(
            state="normal" if idle and self._recorder.count > 0 else "disabled")
        self._btn_clean.config(
            state="normal" if idle and self._recorder.count > 0 else "disabled")

    # ── Record tab commands ────────────────────────────────────────────────────

    def _cmd_start_rec(self):
        if self._state != "idle":
            return
        self._set_state("recording")
        self._lbl_count.config(text="Actions: 0")
        self._recorder.start()
        self._log("Recording started.  (Press F9 to stop)")

    def _cmd_stop_rec(self):
        """Stop recording and save. Safe to call from F9 hotkey or button click."""
        if self._state != "recording":
            return
        self._recorder.stop()
        name = self._sanitize_name(self._name_var.get())
        # Auto-clean before saving: remove any filtered keys / app clicks
        cleaned = self._clean_macro_actions(self._recorder.actions)
        self._recorder.actions = cleaned
        self._recorder.save(self._macro_path(name))
        n = self._recorder.count
        self._set_state("idle")
        self._refresh_macro_list()
        self._log(f"Saved '{name}' ({n} actions).")
        messagebox.showinfo("Saved", f"Macro '{name}' saved with {n} actions.")

    def _cmd_play_current(self):
        if self._state != "idle" or self._recorder.count == 0:
            return
        ok, warn = self._validate_macro(self._recorder.actions)
        if not ok:
            messagebox.showerror("Macro Error", warn)
            return
        self._current_name = self._sanitize_name(self._name_var.get())
        self._start_countdown(self._recorder.actions, self._loop_count())

    def _cmd_clean_current(self):
        """Clean the currently recorded (in-memory) macro."""
        if self._recorder.count == 0:
            return
        before = self._recorder.count
        self._recorder.actions = self._clean_macro_actions(self._recorder.actions)
        after = self._recorder.count
        removed = before - after
        self._lbl_count.config(text=f"Actions: {after}")
        self._log(f"Cleaned current macro: removed {removed} suspicious action(s).")
        messagebox.showinfo("Cleaned",
            f"Removed {removed} suspicious action(s).\n"
            f"Macro now has {after} action(s).")

    # ── Macros tab commands ────────────────────────────────────────────────────

    def _cmd_play_selected(self):
        if self._state != "idle":
            messagebox.showwarning("Busy", "Stop the current playback first.")
            return
        name = self._selected_macro()
        if not name:
            messagebox.showwarning("Select Macro", "Select a macro from the list.")
            return
        try:
            actions = self._load_macro(name)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load macro: {e}")
            return
        ok, warn = self._validate_macro(actions)
        if not ok:
            messagebox.showerror("Macro Error", warn)
            return
        self._current_name = name
        self._start_countdown(actions, self._loop_count())

    def _cmd_play_all_ordered(self):
        if self._state != "idle":
            messagebox.showwarning("Busy", "Stop the current playback first.")
            return
        names = self._list_macros()
        if not names:
            messagebox.showwarning("No Macros", "No macros saved yet.")
            return
        self._play_sequence(names)

    def _cmd_play_all_random(self):
        if self._state != "idle":
            messagebox.showwarning("Busy", "Stop the current playback first.")
            return
        names = self._list_macros()
        if not names:
            messagebox.showwarning("No Macros", "No macros saved yet.")
            return
        random.shuffle(names)
        self._play_sequence(names)

    def _cmd_clean_selected(self):
        """Clean the selected saved macro file."""
        name = self._selected_macro()
        if not name:
            messagebox.showwarning("Select Macro", "Select a macro first.")
            return
        try:
            actions = self._load_macro(name)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load macro: {e}")
            return
        before = len(actions)
        cleaned = self._clean_macro_actions(actions)
        after = len(cleaned)
        removed = before - after
        # Save cleaned version
        with open(self._macro_path(name), "w") as f:
            json.dump(cleaned, f, indent=2)
        self._on_macro_select()   # refresh info label
        self._log(f"Cleaned '{name}': removed {removed} suspicious action(s).")
        messagebox.showinfo("Cleaned",
            f"Removed {removed} suspicious action(s) from '{name}'.\n"
            f"Macro now has {after} action(s).")

    def _cmd_rename_macro(self):
        name = self._selected_macro()
        if not name:
            messagebox.showwarning("Select Macro", "Select a macro first.")
            return
        new_name = simpledialog.askstring(
            "Rename Macro", f"New name for '{name}':", initialvalue=name)
        if not new_name:
            return
        new_name = self._sanitize_name(new_name)
        new_path = self._macro_path(new_name)
        if os.path.exists(new_path):
            messagebox.showerror("Name Taken", f"'{new_name}' already exists.")
            return
        os.rename(self._macro_path(name), new_path)
        self._refresh_macro_list()
        self._lbl_macro_info.config(text="No macro selected.")
        self._log(f"Renamed '{name}' \u2192 '{new_name}'.")

    def _cmd_delete_macro(self):
        name = self._selected_macro()
        if not name:
            messagebox.showwarning("Select Macro", "Select a macro first.")
            return
        if not messagebox.askyesno("Delete Macro",
                                   f"Permanently delete '{name}'?"):
            return
        try:
            os.remove(self._macro_path(name))
            self._refresh_macro_list()
            self._lbl_macro_info.config(text="No macro selected.")
            self._log(f"Deleted '{name}'.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _cmd_reset_stats(self):
        if messagebox.askyesno("Reset Stats",
                               "Reset all statistics to zero?"):
            self._stats = {"total_runs": 0, "total_time": 0.0, "last_run": None}
            self._save_stats()
            self._refresh_stats_labels()
            self._log("Statistics reset.")

    # ── Playback orchestration ─────────────────────────────────────────────────

    def _start_countdown(self, actions: list, loop_count):
        self._set_state("countdown", f"[{self._current_name}]")
        threading.Thread(
            target=self._countdown_thread,
            args=(actions, loop_count), daemon=True).start()

    def _countdown_thread(self, actions: list, loop_count):
        for secs in range(COUNTDOWN_SECS, 0, -1):
            if self._state != "countdown":
                return
            self.after(0, lambda s=secs: self._lbl_ctx.config(
                text=f"[{self._current_name}] starting in {s}s\u2026"))
            time.sleep(1)
        if self._state != "countdown":
            return
        self.after(0, lambda: self._set_state("playing", f"[{self._current_name}]"))
        self._idle_detector.pause()
        self._player = MacroPlayer(
            actions=actions,
            loop_count=loop_count,
            human_like=self._human_var.get(),
            on_loop=lambda n: None,
            on_stop=self._on_play_done,
        )
        self._player.start()
        self._log(f"Playback started: '{self._current_name}'.")

    def _play_sequence(self, names: list[str]):
        self._set_state("playing", "[sequence]")
        self._idle_detector.pause()

        def run():
            for name in names:
                if self._state != "playing":
                    break
                try:
                    actions = self._load_macro(name)
                except Exception:
                    continue
                ok, _ = self._validate_macro(actions)
                if not ok:
                    continue
                self.after(0, lambda n=name: self._lbl_ctx.config(text=f"[{n}]"))
                self._log(f"Playing '{name}'\u2026")
                done = threading.Event()
                p = MacroPlayer(
                    actions=actions, loop_count=1,
                    human_like=self._human_var.get(),
                    on_stop=lambda *_: done.set())
                self._player = p
                p.start()
                done.wait()
            self._on_play_done(0, 0.0)

        threading.Thread(target=run, daemon=True).start()

    def _on_play_done(self, loops_done: int, elapsed: float):
        self.after(0, lambda: self._set_state("idle"))
        self._record_play_stats(loops_done, elapsed)
        self._idle_detector.resume()
        self._log(f"Playback done: '{self._current_name}' "
                  f"\u2014 {loops_done} loop(s), {elapsed:.1f}s.")

    # ── Idle auto-play ─────────────────────────────────────────────────────────

    def _on_idle_triggered(self):
        if not self._idle_en.get() or self._state != "idle":
            return
        self._log("Idle threshold reached \u2014 auto-starting playback.")
        choice = self._idle_macro_var.get()
        names  = self._list_macros() if choice == "(all macros in order)" \
                 else [choice]
        if not names:
            return
        self.after(0, lambda: self._start_idle_playback(names))

    def _start_idle_playback(self, names: list[str]):
        self._set_state("playing", "[idle auto-play]")
        self._idle_detector.pause()

        from pynput import keyboard as pynput_kb
        stop_flag = threading.Event()

        def on_key(_key):
            stop_flag.set()
            if self._player:
                self._player.stop()
            return False

        kb_listener = pynput_kb.Listener(on_press=on_key)
        kb_listener.start()

        def run():
            for name in names:
                if stop_flag.is_set() or self._state != "playing":
                    break
                try:
                    actions = self._load_macro(name)
                except Exception:
                    continue
                self.after(0, lambda n=name: self._lbl_ctx.config(
                    text=f"[{n}] (idle)"))
                done = threading.Event()
                p = MacroPlayer(
                    actions=actions, loop_count=None,
                    human_like=True,
                    on_stop=lambda *_: done.set())
                self._player = p
                p.start()
                done.wait()

            kb_listener.stop()
            self._on_play_done(0, 0.0)
            self._log("Idle playback ended.")

        threading.Thread(target=run, daemon=True).start()

    def _on_user_active(self):
        if self._state == "playing":
            if self._player:
                self._player.stop()
            self.after(0, lambda: self._set_state("idle"))
            self._log("User activity \u2014 playback stopped.")

    # ── Scheduler trigger ──────────────────────────────────────────────────────

    def _on_schedule_trigger(self):
        if self._state != "idle":
            return
        self._log("Scheduler triggered \u2014 starting playback.")
        names = self._list_macros()
        if names:
            self.after(0, lambda: self._play_sequence(names))

    # ── Safety: corner monitor & hotkeys ─────────────────────────────────────

    def _start_corner_monitor(self):
        def _monitor():
            import pyautogui
            while True:
                try:
                    x, y = pyautogui.position()
                    if x <= 3 and y <= 3 and self._state == "playing":
                        if self._player:
                            self._player.stop()
                        self.after(0, lambda: self._set_state("idle"))
                        self.after(0, lambda: self._log(
                            "Emergency stop: mouse moved to top-left corner."))
                except Exception:
                    pass
                time.sleep(0.2)
        threading.Thread(target=_monitor, daemon=True).start()

    def _hotkey_stop_recording(self):
        """F9 handler — stops recording. Never gets recorded (suppress=True)."""
        if self._state == "recording":
            self.after(0, self._cmd_stop_rec)

    def _hotkey_stop_playback(self):
        """F10 (or custom) handler — stops playback/countdown."""
        if self._state in ("playing", "countdown"):
            if self._player:
                self._player.stop()
            self.after(0, lambda: self._set_state("idle"))
            self._log(f"Stopped via {self._play_stop_hotkey.upper()} hotkey.")

    # ── System tray ────────────────────────────────────────────────────────────

    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            img  = Image.new("RGB", (64, 64), _ACC)
            draw = ImageDraw.Draw(img)
            draw.polygon([(24, 18), (24, 46), (47, 32)], fill="white")

            def show(icon, _item):
                icon.stop()
                self._tray_icon = None
                self.after(0, self.deiconify)

            def quit_app(icon, _item):
                icon.stop()
                self.after(0, self._force_exit)

            self._tray_icon = pystray.Icon(
                "TithWorker", img, APP_NAME,
                pystray.Menu(
                    pystray.MenuItem("Show", show, default=True),
                    pystray.MenuItem("Quit", quit_app),
                ))
        except ImportError:
            self._tray_icon = None

    def _minimize_to_tray(self):
        if self._tray_icon is None:
            self._setup_tray()
        if self._tray_icon is not None:
            self.withdraw()
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        else:
            self.iconify()

    # ── Window close ──────────────────────────────────────────────────────────

    def _on_close(self):
        result = messagebox.askyesnocancel(
            APP_NAME,
            "Minimize to system tray?\n\n"
            "Yes = minimize to tray\n"
            "No  = exit completely\n"
            "Cancel = keep open")
        if result is None:
            return
        if result:
            self._minimize_to_tray()
        else:
            self._force_exit()

    def _force_exit(self):
        if self._state == "recording":
            self._recorder.stop()
        if self._player:
            self._player.stop()
        self._idle_detector.stop()
        self._scheduler.stop()
        keyboard.unhook_all()
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        self._log(f"{APP_NAME} closed.")
        self.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
