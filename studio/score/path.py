"""The path of a score: the conditioning embedding of every step of the piece, from the clips of the timeline.

A clip holds one embedding for its whole length: the mix of some sources (`comp`: [[source, weight], ...], the sources being the
representatives of the atlas). Between two consecutive clips the embedding goes from the end of the first to the start of the second by
slerp (the interpolation of the old demo); with no gap between them it is a cut. How fast it goes is the `curve` of the first clip: dots
[[time, position], ...] of the unit square (0 = the first clip, 1 = the next), joined by their Lagrange polynomial (the position is
limited to [0, 1]). Without a curve, DEFAULT_CURVE. The piece runs from the start of the first clip to the end
of the last one.
"""
import numpy as np

MAX_CLIPS, MAX_SECONDS, MIN_CLIP_SECONDS = 200, 600.0, 0.1
DEFAULT_CURVE = [[0, 0], [0.2, 0.3], [0.5, 0.5], [0.8, 0.7], [1, 1]]      # the same as web/score/core/curve.js
MAX_CURVE_POINTS = 12


def slerp(a, b, t):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    dot = float(np.clip(a @ b, -1.0, 1.0))
    omega = np.arccos(dot)
    if omega < 1e-6:
        out = (1 - t) * a + t * b
    else:
        out = (np.sin((1 - t) * omega) * a + np.sin(t * omega) * b) / np.sin(omega)
    return out / np.linalg.norm(out)


# the dots of a curve as the page sends them -> [(x, y)] sorted by x; None is the default curve
def read_curve(curve):
    pts = DEFAULT_CURVE if curve is None else curve
    pts = sorted((float(x), float(y)) for x, y in pts)
    if not 2 <= len(pts) <= MAX_CURVE_POINTS or any(not (np.isfinite(x) and np.isfinite(y)) or not 0 <= x <= 1 for x, y in pts):
        raise ValueError("a curve has a wrong dot")
    if any(b[0] - a[0] < 1e-3 for a, b in zip(pts, pts[1:])):
        raise ValueError("a curve has two dots at the same time")
    return pts


# the position (0 .. 1) of the curve at time x: its Lagrange polynomial, limited to [0, 1]
def curve_position(pts, x):
    total = 0.0
    for i, (xi, yi) in enumerate(pts):
        term = yi
        for j, (xj, _) in enumerate(pts):
            if j != i:
                term *= (x - xj) / (xi - xj)
        total += term
    return min(1.0, max(0.0, total))


# the unit vector of a clip: the normalised weighted sum of the vectors of its sources
def clip_vector(vecs, comp):
    v = sum(float(w) * vecs[int(i)] for i, w in comp)
    n = np.linalg.norm(v)
    if not np.isfinite(n) or n < 1e-9:
        raise ValueError("a clip with no weight")
    return v / n


# clips as the page sends them -> [{start, end, vec}] sorted, checked (sources in range, no overlap, sensible lengths)
def read_clips(clips, vecs):
    if not clips:
        raise ValueError("the timeline is empty")
    if len(clips) > MAX_CLIPS:
        raise ValueError(f"{len(clips)} clips: at most {MAX_CLIPS}")
    out = []
    for c in clips:
        start, dur = float(c["start"]), float(c["dur"])
        if not (np.isfinite(start) and np.isfinite(dur)) or start < 0 or dur < MIN_CLIP_SECONDS:
            raise ValueError("a clip has a wrong time")
        comp = [(int(i), float(w)) for i, w in c["comp"]]
        if not comp or any(not 0 <= i < len(vecs) or w < 0 for i, w in comp):
            raise ValueError("a clip has a wrong source")
        out.append({"start": start, "end": start + dur, "vec": clip_vector(vecs, comp), "curve": read_curve(c.get("curve"))})
    out.sort(key=lambda c: c["start"])
    for a, b in zip(out, out[1:]):
        if b["start"] < a["end"] - 1e-6:
            raise ValueError("clips overlap")
    if out[-1]["end"] - out[0]["start"] > MAX_SECONDS:
        raise ValueError(f"the piece lasts more than {MAX_SECONDS:.0f} s")
    return out


# the embeddings of the steps of the piece, [n, d] with n = its length / hop_s; and when it starts (s)
def build_path(clips, vecs, hop_s):
    clips = read_clips(clips, vecs)
    t0 = clips[0]["start"]
    n = max(1, int(round((clips[-1]["end"] - t0) / hop_s)))
    rows = np.empty((n, len(vecs[0])), dtype=np.float64)
    j = 0
    for k in range(n):
        t = t0 + (k + 0.5) * hop_s
        while j < len(clips) - 1 and t >= clips[j + 1]["start"]:
            j += 1
        c = clips[j]
        if t < c["end"] or j == len(clips) - 1:
            rows[k] = c["vec"]
        else:                                                   # in the gap after clip j: slerp towards the next
            nxt = clips[j + 1]
            rows[k] = slerp(c["vec"], nxt["vec"], curve_position(c["curve"], (t - c["end"]) / (nxt["start"] - c["end"])))
    return rows.astype(np.float32), t0
