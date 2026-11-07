"""The atlas of a model as the page needs it: numpy arrays and the few operations of the GUI. The maths (clusters, the
2-D error basis, the scale) is SCAPES.auxiliar.atlas.Atlas; this wraps it, adds nothing to it."""
import numpy as np

import studio.scapes_path  # noqa: F401  (before SCAPES)
from SCAPES.auxiliar.atlas import Atlas

from studio import hull


class AtlasModel:
    def __init__(self, atlas: Atlas):
        self.atlas = atlas
        self.K = atlas.K
        self.names = list(atlas.names)
        self.mu = atlas.mu.numpy()                     # [K, d] float64 unit cluster means
        self.P = atlas.P.numpy()                       # [d, 2]
        self.s = float(atlas.s)
        self.cloud = atlas.cloud.numpy()               # [m, 3] points of the 3-D view
        self.labels = atlas.cloud_labels.numpy()       # [m] their cluster
        self.prior = atlas.prior                       # AtlasPrior, or None

    @classmethod
    def load(cls, path):
        return cls(Atlas.load(path))

    # the unit vector for a mean m (d,) and a disk point u (2,): normalise(m + P (s u))
    def from_mean(self, m, u):
        x = np.asarray(m, dtype=np.float64) + self.P @ (self.s * np.asarray(u, dtype=np.float64))
        return x / np.linalg.norm(x)

    # the mean of a selection (dot indices ascending, weights summing to 1)
    def mean_at(self, idx, lam):
        return hull.mean_at(self.mu, idx, lam)

    # 3-D coordinates of vectors (n, d) or (d,) -> (n, 3)
    def to3d(self, v):
        return self.atlas.to3d(np.atleast_2d(np.asarray(v, dtype=np.float64))).numpy().astype(np.float64)
