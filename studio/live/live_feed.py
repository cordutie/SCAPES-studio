"""The embedding the GUI is making right now. The page writes it (live), the generator reads it at every step."""
import threading

import numpy as np


class LiveFeed:
    def __init__(self):
        self._lock = threading.Lock()
        self._vector = None
        self.counter = 0

    # the page's new embedding: a unit vector (d,), or None when no dot is placed
    def publish(self, vector):
        with self._lock:
            self._vector = None if vector is None else np.asarray(vector, dtype=np.float32).copy()
            self.counter += 1

    # the latest embedding (d,) float32, or None before the first dot
    def latest(self):
        with self._lock:
            return self._vector
