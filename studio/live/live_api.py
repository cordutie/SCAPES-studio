"""The functions the page calls through Gradio (`server.boot`, `server.live`, `server.project`, `server.prior_step`).
They are the maths of the atlas page: from the dots, the control point and the disk point to the embedding. The embedding
is handed to the session's LiveFeed, where the generator reads it."""
import json

import numpy as np

from studio import config, hull

NAMES_FILE = "names.json"          # in the model folder: the names the user gave to the clusters (index -> name)


# the names of the atlas with the user's renames applied
def read_names(session):
    names = list(session.atlas.names)
    try:
        for k, v in json.loads((session.path / NAMES_FILE).read_text()).items():
            if 0 <= int(k) < len(names) and str(v).strip():
                names[int(k)] = str(v).strip()
    except (OSError, ValueError, AttributeError):
        pass
    return names


# clamp a disk point (ux, uy) to the unit disk
def clamp_to_disk(ux, uy):
    n = float(np.hypot(ux, uy))
    return (float(ux), float(uy)) if n <= 1.0 else (float(ux / n), float(uy / n))


# clamp each placed dot to the plane [-1, 1]^2; unplaced dots stay None
def clamp_dots(dots):
    return [None if d is None else [float(min(max(d[0], -1.0), 1.0)), float(min(max(d[1], -1.0), 1.0))] for d in dots]


# the selection to use: the pointer's if it selects something, else the given one (if still valid), else the first dot
def pick_selection(sel, pointer, dots, locate=True):
    if locate and pointer is not None:
        found = hull.locate(pointer, dots, hull.DOT_TOL, hull.EDGE_TOL)
        if found is not None:
            return found
    if sel is not None:
        idx = [int(i) for i in sel["idx"]]
        if idx and all(0 <= i < len(dots) and dots[i] is not None for i in idx):
            return tuple(idx), tuple(float(w) for w in sel["lam"])
    ids, _ = hull.unique_dots(dots)
    return (int(ids[0]),), (1.0,)


# the dot with the largest weight; the lowest index on a tie
def main_dot(idx, lam):
    best = max(lam)
    return min(i for i, w in zip(idx, lam) if w >= best - 1e-9)


# the control point in the zone of the dots: the point to answer with, the projection, and whether it moved
def zone_point(c, dots):
    start = np.zeros(2) if c is None else np.asarray(c, dtype=np.float64)
    p1 = hull.project_to_zone(start, dots)
    moved = c is None or float(np.linalg.norm(p1 - start)) > 1e-12
    if not moved:
        return [float(c[0]), float(c[1])], p1, False
    return [float(p1[0]), float(p1[1])], p1, True


def make_functions(manager):
    # what the page needs at start (Gradio passes one argument; the page sends a dummy)
    def boot(_):
        if manager.session is None and manager.default():          # the first visit loads the model used last time (or the first)
            manager.load(manager.default())
        session = manager.session
        if session is None:                                         # nothing to play yet: the page says so
            return {"no_models": True, "dir": str(manager.dir), "repo": config.MODELS_REPO, "github": config.GITHUB_URL}
        atlas = session.atlas
        if atlas.K > config.MAX_CLUSTERS:
            raise ValueError(f"the atlas has {atlas.K} clusters; the page shows at most {config.MAX_CLUSTERS}")
        return {"cloud": atlas.cloud.tolist(), "names": read_names(session), "labels": atlas.labels.tolist(), "K": atlas.K,
                "has_prior": atlas.prior is not None, "info": session.info()}

    # the models of the folder, for the menu (read again each time, so a model that was just added shows)
    def models(_):
        return manager.available()

    # switch to another model: {"ok": True}, or {"ok": False, "error": why} with the old model still playing. The page reloads after it.
    def load_model(state):
        try:
            manager.load(state["name"])
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # the live call: selection, mean, decoded point, outline and cluster; the embedding goes to the generator
    def live(state):
        session = manager.session
        atlas, feed = session.atlas, session.feed
        dots = clamp_dots(state.get("dots") or [None] * atlas.K)
        u = clamp_to_disk(*(state.get("u") or (0.0, 0.0)))
        c = state.get("c")
        c_sent = None if c is None else [float(c[0]), float(c[1])]
        ids, _ = hull.unique_dots(dots)
        if len(ids) == 0:
            feed.publish(None)
            return {"sel": None, "c": c_sent, "u": list(u), "dots": dots, "outline": [], "dec3": None, "mean3": None,
                    "cluster": None}
        c_out, p1, moved = zone_point(c_sent, dots)
        idx, lam = pick_selection(state.get("sel"), p1, dots, bool(state.get("locate", True)) or moved)
        mean = atlas.mean_at(idx, lam)
        vector = atlas.from_mean(mean, u)
        feed.publish(vector)
        return {"sel": {"idx": list(idx), "lam": list(lam)}, "c": c_out, "u": list(u), "dots": dots,
                "outline": hull.outline(dots), "dec3": atlas.to3d(vector)[0].tolist(), "mean3": atlas.to3d(mean)[0].tolist(),
                "cluster": int(main_dot(idx, lam))}

    # one sample of the prior from the history (10 x 2, newest first), the cluster and the tick (same tick, same point)
    def prior_step(state):
        rng = np.random.default_rng((0, int(state["tick"])))
        u = manager.session.atlas.prior.sample(np.asarray(state["hist"], dtype=np.float64), int(state["cluster"]), rng)
        return {"u": [float(u[0]), float(u[1])]}

    # the closest point of the zone of the dots to p (the Glide target)
    def project(state):
        dots = clamp_dots(state.get("dots") or [])
        if len(hull.unique_dots(dots)[0]) == 0:
            return {"c": None}
        p = hull.project_to_zone(state["p"], dots)
        return {"c": [float(p[0]), float(p[1])]}

    # keeps the name the user gave to a cluster, for the next sessions
    def rename(state):
        session = manager.session
        k, name = int(state["index"]), str(state["name"]).strip()[:40]
        path = session.path / NAMES_FILE
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        if name and name != session.atlas.names[k]:
            data[str(k)] = name
        else:
            data.pop(str(k), None)                  # an empty name, or the original one, takes the rename away
        if data:
            path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        else:                                       # no renames left: no file
            path.unlink(missing_ok=True)
        return {"name": read_names(session)[k]}

    return [boot, models, load_model, live, project, prior_step, rename]
