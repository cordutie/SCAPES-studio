"""The functions the Score page calls through Gradio (`server.boot`, `server.locate`): the list of sources (the representatives of the
clusters of a model) the takes, and, for the semantic playground, where the point is among the dots. No model is loaded and nothing is generated here yet."""
import re

import numpy as np

from studio import config, hull
from studio.live.live_api import clamp_dots, read_names, zone_point

SNIPPET = re.compile(r"^[0-9]{3}\.mp3$")


def make_functions(library, takes, prefix):
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

    return [boot, locate, list_takes, delete_take]
