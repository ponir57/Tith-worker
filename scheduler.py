import time
import datetime
import threading


class MacroScheduler:
    """
    Background scheduler that fires on_trigger() when the current local
    time enters the configured window on an enabled weekday.

    Each window fires at most once per calendar day.
    """

    def __init__(self, on_trigger=None):
        self.on_trigger = on_trigger

        self.enabled = False
        self.start_time: datetime.time | None = None
        self.end_time: datetime.time | None = None
        self.days: set[int] = set()         # 0 = Monday … 6 = Sunday

        self._running = False
        self._thread = None
        self._last_fired_date: datetime.date | None = None

    # ── Internal ───────────────────────────────────────────────────────────────

    def _in_window(self, now: datetime.datetime) -> bool:
        if not self.start_time:
            return False
        t = now.time().replace(second=0, microsecond=0)
        if self.end_time:
            return self.start_time <= t <= self.end_time
        return t >= self.start_time

    def _check_loop(self):
        while self._running:
            if self.enabled and self.days and self.start_time:
                now = datetime.datetime.now()
                if (now.weekday() in self.days
                        and self._in_window(now)
                        and self._last_fired_date != now.date()):
                    self._last_fired_date = now.date()
                    if self.on_trigger:
                        self.on_trigger()
            time.sleep(10)

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
