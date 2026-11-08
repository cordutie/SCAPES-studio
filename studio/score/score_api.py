"""The functions the Score page calls through Gradio (`server.boot`, `server.locate`, ...): the sources (the representatives of the clusters of
a model), where the point is among the dots of the semantic playground, the takes, and the generation of a take (a job in a thread that the
page follows with `render_status`). The model is loaded only when a take is generated."""
import re
import time

import numpy as np

from studio import config, hull
from studio.atlas_model import AtlasModel
from studio.live.live_api import clamp_dots, read_names, zone_point
from studio.score import path as score_path
from studio.score.jobs import Job

SNIPPET = re.compile(r"^[0-9]{3}\.mp3$")


def make_functions(library, takes, prefix, generator=None):
    job = Job()

    # what the page needs at start: the model (the one asked for, else the default), the models for the menu, and the sources
    def boot(state):
        name = (state or {}).get("name") if isinstance(state, dict) else None
        name = name or library.default()
        if name is None:
            return {"no_models": True, "dir": str(library.dir), "repo": config.MODELS_REPO, "github": config.GITHUB_URL}
        model = library.model(name)
        reps = model.atlas.reps
        if len(reps) > 999:
            raise ValueError(f"{len(reps)} sources: too many for the page")
        names = read_names(model)
        return {"model": name, "models": library.available(), "K": model.atlas.K, "names": names,
                "cloud": model.atlas.cloud.tolist(), "labels": model.atlas.cloud_labels.tolist(),
                "generation": {"nfe": config.NFE_DEFAULT, "nfe_range": list(config.NFE_RANGE), "cfg": config.CFG_DEFAULT,
                               "cfg_range": list(config.CFG_RANGE), "cfg_step": config.CFG_STEP},
                "takes": takes.list(), "takes_url": f"{prefix}/takes/",
                "sources": [{"cluster": int(reps.cluster[i]), "name": reps.name(i), "file": reps.files[reps.file[i]],
                             "start": float(reps.start[i]), "url": f"{prefix}/snippets/{name}/{i:03d}.mp3"} for i in range(len(reps))]}

    # where the control point is among the dots: the dots (one entry per source, [x, y] or None), the point asked for (c) and the pixel size
    # of the playground (the tolerances of hull.py are in plane units for a 520 px square). Answers the point inside the zone of the dots,
    # the sources around it with their weights, and the outline of the zone
    def locate(state):
        dots = clamp_dots(state.get("dots") or [])
        ids, _ = hull.unique_dots(dots)
        if len(ids) == 0:
            return {"sel": None, "c": None, "outline": []}
        scale = 520.0 / float(state.get("px") or 520)
        c = state.get("c")
        c_out, p1, _ = zone_point(None if c is None else [float(c[0]), float(c[1])], dots)
        found = hull.locate(p1, dots, hull.DOT_TOL * scale, hull.EDGE_TOL * scale)
        idx, lam = found if found is not None else ((int(ids[0]),), (1.0,))
        return {"sel": {"idx": [int(i) for i in idx], "lam": [float(w) for w in lam]}, "c": c_out, "outline": hull.outline(dots)}

    # the takes (newest first), and the removal of one
    def list_takes(_):
        return takes.list()

    def delete_take(state):
        takes.delete(str(state["id"]))
        return takes.list()

    # the generation of a take. state: model, clips [{start, dur, comp}], nfe, cfg, seed. Answers {ok} at once; the page follows the job.
    def render(state):
        if generator is None:
            return {"ok": False, "error": "this app cannot generate"}
        try:
            name = str(state["model"])
            model = library.model(name)
            vecs = model.atlas.reps.vec
            clips, nfe, cfg, seed = state["clips"], int(state["nfe"]), float(state["cfg"]), int(state["seed"])
            score_path.read_clips(clips, vecs)                       # a bad score is refused here, before the job
            nfe = min(max(nfe, config.NFE_RANGE[0]), config.NFE_RANGE[1])
            cfg = min(max(cfg, config.CFG_RANGE[0]), config.CFG_RANGE[1])
        except (KeyError, ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

        def work(j):
            if not generator.lock.acquire(blocking=False):
                raise RuntimeError("another piece is being generated")
            try:
                j.say(f"loading {name}")
                hop = generator.hop_s(name)
                rows, t0 = score_path.build_path(clips, vecs, hop)
                seconds = len(rows) * hop
                j.say(f"{len(clips)} clip{'s' if len(clips) > 1 else ''} · {seconds:.1f} s · {len(rows)} steps · NFE {nfe} · CFG {cfg:.1f} · seed {seed}")
                mark = [0]

                def progress(done, total):
                    j.progress = done / total
                    if done == total or done >= mark[0] + max(1, total // 10):          # a line every tenth
                        mark[0] = done
                        j.say(f"{100 * done // total}%  ({done}/{total} steps, {time.time() - j.started:.0f} s)")

                samples, sr = generator.render(name, rows, nfe, cfg, seed, progress)
                path3 = np.round(AtlasModel(model.atlas).to3d(rows), 4).tolist()          # where the piece went in the 3-D atlas
                take = takes.add(samples, sr, {"model": name, "nfe": nfe, "cfg": cfg, "seed": seed, "start": t0, "rate": 1.0 / hop,
                                               "clips": [{"start": c["start"], "dur": c["dur"], "comp": c["comp"]} for c in clips],
                                               "path3": path3})
                j.say(f"done: {take['name']} · {take['seconds']:.1f} s of audio in {time.time() - j.started:.0f} s")
                return {k: v for k, v in take.items() if k != "path3"}
            finally:
                generator.lock.release()

        started = job.start(work)
        return {"ok": started, "error": None if started else "a piece is already being generated"}

    def render_status(_):
        return job.status()

    # where a take went in the 3-D atlas
    def take_trace(state):
        return takes.trace(str(state["id"]))

    return [boot, locate, list_takes, delete_take, render, render_status, take_trace]
