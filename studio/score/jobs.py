"""The generation of a take runs in a thread, and the page asks how it goes: a job has a progress, a log (lines the page appends to its own)
and, at the end, the take or an error. One job at a time."""
import threading
import time


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.running, self.progress, self.lines, self.take, self.error, self.started = False, 0.0, [], None, None, 0.0

    def say(self, text, warn=False):
        self.lines.append({"text": text, "warn": warn})

    # runs fn(job) in a thread; False if a job is running
    def start(self, fn):
        with self.lock:
            if self.running:
                return False
            self.reset()
            self.running, self.started = True, time.time()
        threading.Thread(target=self._run, args=(fn,), name="scapes-score", daemon=True).start()
        return True

    def _run(self, fn):
        try:
            self.take = fn(self)
        except Exception as exc:                            # shown in the page, not raised in the thread
            self.error = f"{type(exc).__name__}: {exc}"
            self.say(self.error, warn=True)
        finally:
            self.running = False

    def status(self):
        return {"running": self.running, "progress": self.progress, "lines": list(self.lines), "take": self.take, "error": self.error,
                "elapsed": (time.time() - self.started) if self.started else 0.0}
