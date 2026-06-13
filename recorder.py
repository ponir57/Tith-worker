import time
import json
import threading
from pynput import mouse, keyboard as pynput_keyboard

# Key names (as produced by _key_str) that must never be recorded
FILTERED_KEYS = {"Key.f9", "Key.f10"}


class MacroRecorder:
    def __init__(self, on_action_recorded=None, is_app_click=None):
        self.actions = []
        self.recording = False
        self._last_time = None
        self._mouse_listener = None
        self._keyboard_listener = None
        self._lock = threading.Lock()
        self.on_action_recorded = on_action_recorded  # callback(count)
        self.is_app_click = is_app_click              # callable(x, y) -> bool

    def _elapsed(self):
        now = time.time()
        delay = 0.0 if self._last_time is None else now - self._last_time
        self._last_time = now
        return delay

    def _record(self, action: dict):
        with self._lock:
            if not self.recording:
                return
            action["delay"] = self._elapsed()
            self.actions.append(action)
            if self.on_action_recorded:
                self.on_action_recorded(len(self.actions))

    # ── Mouse callbacks ────────────────────────────────────────────────────────

    def _on_move(self, x, y):
        self._record({"type": "move", "x": x, "y": y})

    def _on_click(self, x, y, button, pressed):
        # Never record clicks on the app's own window
        if self.is_app_click and self.is_app_click(x, y):
            return
        self._record({
            "type": "click",
            "x": x, "y": y,
            "button": button.name,
            "pressed": pressed,
        })

    def _on_scroll(self, x, y, dx, dy):
        self._record({"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy})

    # ── Keyboard callbacks ─────────────────────────────────────────────────────

    def _key_str(self, key):
        try:
            return key.char
        except AttributeError:
            return str(key)

    def _on_press(self, key):
        k = self._key_str(key)
        if k in FILTERED_KEYS:
            return
        self._record({"type": "key_press", "key": k})

    def _on_release(self, key):
        k = self._key_str(key)
        if k in FILTERED_KEYS:
            return
        self._record({"type": "key_release", "key": k})

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        self.actions = []
        self._last_time = None
        self.recording = True

        self._mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener = pynput_keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

    def stop(self):
        self.recording = False
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.actions, f, indent=2)

    def load(self, path: str):
        with open(path) as f:
            self.actions = json.load(f)
        return self.actions

    @property
    def count(self):
        return len(self.actions)
