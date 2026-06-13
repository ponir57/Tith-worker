import time
import random
import threading
import pyautogui
import pynput.keyboard as pynput_keyboard

pyautogui.FAILSAFE = True   # top-left corner raises FailSafeException

CORNER_RADIUS = 4           # pixels — distance from (0,0) counted as emergency stop


class MacroPlayer:
    def __init__(self, actions, loop_count=1,
                 human_like=True,
                 on_loop=None, on_stop=None):
        """
        actions    : list of action dicts produced by MacroRecorder
        loop_count : int >= 1, or None / 0 for infinite
        human_like : add timing jitter, natural move duration, micro-pauses
        on_loop    : callback(loop_number)
        on_stop    : callback(loops_done, elapsed_seconds)
        """
        self.actions = actions
        self.loop_count = loop_count
        self.human_like = human_like
        self.on_loop = on_loop
        self.on_stop = on_stop

        self._stop_event = threading.Event()
        self._thread = None
        self._kb = pynput_keyboard.Controller()
        self._loops_done = 0

    # ── Human-like helpers ─────────────────────────────────────────────────────

    def _jitter(self, delay: float) -> float:
        """Return delay ± 10-20 % random variance."""
        if not self.human_like or delay <= 0:
            return delay
        pct = random.uniform(0.10, 0.20)
        return max(0.0, delay * (1 + random.choice([-1, 1]) * pct))

    def _micro_pause(self):
        """~10 % chance of an extra 0.1-0.3 s pause."""
        if self.human_like and random.random() < 0.10:
            self._stop_event.wait(timeout=random.uniform(0.1, 0.3))

    def _move_duration(self) -> float:
        """Natural mouse movement duration when human-like is on."""
        return random.uniform(0.01, 0.07) if self.human_like else 0

    # ── Key parsing ───────────────────────────────────────────────────────────

    def _parse_key(self, key_str: str):
        if key_str.startswith("Key."):
            return getattr(pynput_keyboard.Key, key_str[4:], key_str)
        return key_str

    # ── Corner check ──────────────────────────────────────────────────────────

    def _in_corner(self) -> bool:
        try:
            x, y = pyautogui.position()
            return x <= CORNER_RADIUS and y <= CORNER_RADIUS
        except Exception:
            return False

    # ── Single action ─────────────────────────────────────────────────────────

    def _play_action(self, action: dict):
        delay = self._jitter(action.get("delay", 0))
        if delay > 0:
            self._stop_event.wait(timeout=delay)
        if self._stop_event.is_set():
            return

        if self._in_corner():
            self._stop_event.set()
            return

        t = action["type"]
        try:
            if t == "move":
                pyautogui.moveTo(action["x"], action["y"],
                                 duration=self._move_duration())

            elif t == "click":
                btn = action.get("button", "left")
                if btn not in ("left", "right", "middle"):
                    btn = "left"
                if action.get("pressed", True):
                    pyautogui.mouseDown(x=action["x"], y=action["y"], button=btn)
                else:
                    pyautogui.mouseUp(x=action["x"], y=action["y"], button=btn)

            elif t == "scroll":
                pyautogui.scroll(int(action.get("dy", 0)),
                                 x=action["x"], y=action["y"])

            elif t == "key_press":
                self._kb.press(self._parse_key(action["key"]))

            elif t == "key_release":
                self._kb.release(self._parse_key(action["key"]))

        except pyautogui.FailSafeException:
            self._stop_event.set()
            return

        self._micro_pause()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _run(self):
        t0 = time.monotonic()
        loop = 0
        infinite = not self.loop_count  # None or 0 → infinite

        while not self._stop_event.is_set():
            loop += 1
            if self.on_loop:
                self.on_loop(loop)

            for action in self.actions:
                if self._stop_event.is_set():
                    break
                self._play_action(action)

            self._loops_done = loop
            if not infinite and loop >= self.loop_count:
                break

        elapsed = time.monotonic() - t0
        if self.on_stop:
            self.on_stop(self._loops_done, elapsed)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        self._stop_event.clear()
        self._loops_done = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    @property
    def is_playing(self):
        return self._thread is not None and self._thread.is_alive()
