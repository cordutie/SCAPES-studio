"""The path of a score: the conditioning embedding of every step of the piece, from the clips of the timeline.

A clip holds one embedding for its whole length: the mix of some sources (`comp`: [[source, weight], ...], the sources being the
representatives of the atlas). Between two consecutive clips the embedding goes from the end of the first to the start of the second by
slerp (the interpolation of the old demo); with no gap between them it is a cut. The piece runs from the start of the first clip to the end
of the last one.
"""
import numpy as np

MAX_CLIPS, MAX_SECONDS, MIN_CLIP_SECONDS = 200, 600.0, 0.1


def slerp(a, b, t):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    dot = float(np.clip(a @ b, -1.0, 1.0))
    omega = np.arccos(dot)
    if omega < 1e-6:
        out = (1 - t) * a + t * b
    else:
        out = (np.sin((1 - t) * omega) * a + np.sin(t * omega) * b) / np.sin(omega)
    return out / np.linalg.norm(out)


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
        out.append({"start": start, "end": start + dur, "vec": clip_vector(vecs, comp)})
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
            rows[k] = slerp(c["vec"], nxt["vec"], (t - c["end"]) / (nxt["start"] - c["end"]))
    return rows.astype(np.float32), t0
