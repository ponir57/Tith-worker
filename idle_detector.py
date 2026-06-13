import time
import threading
from pynput import mouse, keyboard as pynput_keyboard


class IdleDetector:
    """
    Monitors mouse/keyboard inactivity.

    on_idle()   — called once when idle threshold is first reached.
    on_active() — called once when activity resumes after idle.

    Call pause() before bot-driven playback so that pyautogui mouse
    movements don't erroneously reset the idle clock or fire on_active.
    Call resume() when playback ends.
    """

    def __init__(self, threshold_seconds: float = 300,
                 on_idle=None, on_active=None):
        self.threshold = threshold_seconds
        self.on_idle = on_idle
        self.on_active = on_active

        self._last_activity = time.monotonic()
        self._idle_triggered = False
        self._paused = False
        self._running = False

        self._mouse_listener = None
        self._keyboard_listener = None
        self._checker_thread = None

    # ── Input callbacks ────────────────────────────────────────────────────────

    def _touch(self, *_):
        if self._paused:
            # Still reset timer silently so we don't fire idle right after resume
            self._last_activity = time.monotonic()
            return

        was_idle = self._idle_triggered
        self._last_activity = time.monotonic()
        if was_idle:
            self._idle_triggered = False
            if self.on_active:
                self.on_active()

    # ── Background checker ─────────────────────────────────────────────────────

    def _check_loop(self):
        while self._running:
            if not self._paused:
                elapsed = time.monotonic() - self._last_activity
                if not self._idle_triggered and elapsed >= self.threshold:
                    self._idle_triggered = True
                    if self.on_idle:
                        self.on_idle()
            time.sleep(1)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._last_activity = time.monotonic()
        self._idle_triggered = False

        self._mouse_listener = mouse.Listener(
            on_move=self._touch,
            on_click=self._touch,
            on_scroll=self._touch,
        )
        self._keyboard_listener = pynput_keyboard.Listener(
            on_press=self._touch,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()

        self._checker_thread = threading.Thread(
            target=self._check_loop, daemon=True)
        self._checker_thread.start()

    def stop(self):
        self._running = False
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def pause(self):
        """Suppress activity detection during bot playback."""
        self._paused = True

    def resume(self):
        """Resume activity detection after bot playback."""
        self._last_activity = time.monotonic()
        self._idle_triggered = False
        self._paused = False

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_activity
