"""The server functions of the page, on a made-up atlas (no GPU, no model). Run: python -m pytest tests -q"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import studio.scapes_path  # noqa: F401,E402
from SCAPES.auxiliar.atlas import Atlas  # noqa: E402

from studio.atlas_model import AtlasModel  # noqa: E402
from studio.live.live_api import make_functions  # noqa: E402
from studio.live.live_feed import LiveFeed  # noqa: E402


@pytest.fixture(scope="module")
def manager():
    g = torch.Generator().manual_seed(0)
    centres = torch.nn.functional.normalize(torch.randn(4, 1024, generator=g), dim=1)
    plane = torch.linalg.qr(torch.randn(1024, 2, generator=g))[0]
    rows = centres.repeat_interleave(80, 0) + 0.3 * torch.randn(320, 2, generator=g) @ plane.T + 0.005 * torch.randn(320, 1024, generator=g)
    atlas = Atlas.fit(rows, k_range=(4, 4))
    atlas.add_names_and_prior([rows[:160], rows[160:]], ["rain", "wind"])
    session = SimpleNamespace(atlas=AtlasModel(atlas), feed=LiveFeed(), info=lambda: {"model": "toy"})
    return SimpleNamespace(session=session, available=lambda: [{"name": "toy", "codec": "x", "rate": 10.0, "current": True}])


def test_boot_live_prior_project(manager):
    session = manager.session
    boot, models, load_model, live, project, prior_step, rename = make_functions(manager)
    assert models(0)[0]["name"] == "toy"
    assert load_model({"name": "no-such-model"})["ok"] is False                       # an error comes back, nothing is raised
    b = boot(0)
    assert b["K"] == 4 and len(b["names"]) == 4 and b["has_prior"] and len(b["cloud"]) == len(b["labels"])

    dots = [None] * 4
    assert live({"dots": dots, "u": [0, 0]})["dec3"] is None and session.feed.latest() is None     # no dot, no embedding

    dots[0], dots[2] = [-0.5, 0.2], [0.5, -0.2]
    r = live({"dots": dots, "u": [0.1, 0.1], "c": [0.0, 0.0], "locate": True})
    assert r["sel"]["idx"] == [0, 2] and abs(sum(r["sel"]["lam"]) - 1) < 1e-9 and len(r["dec3"]) == 3
    v = session.feed.latest()                                                                        # what the generator reads
    assert v.shape == (1024,) and abs(np.linalg.norm(v) - 1) < 1e-5

    near = live({"dots": dots, "u": [0.1, 0.1], "c": [-0.5, 0.2], "locate": True})
    assert near["sel"]["idx"] == [0] and near["cluster"] == 0                                        # on a dot: that cluster
    assert not np.allclose(session.feed.latest(), v)                                                 # the sound changed

    u = prior_step({"hist": np.zeros((10, 2)).tolist(), "cluster": 0, "tick": 3})["u"]
    assert np.hypot(*u) <= 1 + 1e-9 and prior_step({"hist": np.zeros((10, 2)).tolist(), "cluster": 0, "tick": 3})["u"] == u
    p = project({"dots": dots, "p": [0.0, 5.0]})["c"]
    assert -1 <= p[0] <= 1 and -1 <= p[1] <= 1 and project({"dots": [None] * 4, "p": [0, 0]})["c"] is None


def test_rename(manager, tmp_path):
    boot, models, load_model, live, project, prior_step, rename = make_functions(manager)
    manager.session.path = tmp_path                                           # names.json goes to the model folder
    assert rename({"index": 1, "name": "  my rain "})["name"] == "my rain"
    assert boot(0)["names"][1] == "my rain" and (tmp_path / "names.json").exists()
    assert rename({"index": 1, "name": ""})["name"] == manager.session.atlas.names[1]       # empty: the original name
    assert boot(0)["names"][1] == manager.session.atlas.names[1]


def test_boot_without_models(tmp_path):
    empty = SimpleNamespace(session=None, default=lambda: None, dir=tmp_path)
    boot = make_functions(empty)[0]
    b = boot(0)
    assert b["no_models"] is True and b["dir"] == str(tmp_path) and "SCAPES-models" in b["repo"]
