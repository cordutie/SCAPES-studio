"""The models a mode can play: the folders of models/ (gitignored; --models-dir or config.MODELS_DIR to move it; the Hugging Face
models repo has the same folders, see studio/hub.py).

A model folder is what training makes, cut down to what playing needs (the same shape as a folder of the Hugging Face
models repo):  <name>/checkpoints/inference.gin, best_*.pt (or last_*.pt), latent_stats.pt  and  <name>/atlas.npz.
tools/add_model.py makes one from a trained model. The manager loads one model at a time; switching builds the new one
first, so a model that fails to load leaves the old one playing.
What a loaded model is (its session) depends on the mode: each mode gives the manager a `session_factory(path, name, device, checkpoint)`."""
import gc
import re
import threading
from pathlib import Path

import torch


# What the menu shows about a folder, or None when it is not a model folder
def describe(folder):
    folder = Path(folder)
    gin = folder / "checkpoints" / "inference.gin"
    if not (gin.exists() and (folder / "atlas.npz").exists()):
        return None
    text = gin.read_text()
    codec = re.search(r'^codec\s*=\s*"([^"]+)"', text, re.M)
    rate = re.search(r"^conditioning_rate\s*=\s*([0-9.]+)", text, re.M)
    return {"name": folder.name, "codec": codec.group(1) if codec else "?", "rate": float(rate.group(1)) if rate else 0.0}


class ModelManager:
    def __init__(self, models_dir, session_factory, device=None, checkpoint="best"):
        self.dir, self.device, self.checkpoint = Path(models_dir), device, checkpoint
        self.session_factory = session_factory
        self.session = None
        self._lock = threading.Lock()

    # the models in the folder, by name; the current one is marked (and listed even when it came from another folder)
    def available(self):
        found = [d for d in (describe(p) for p in sorted(self.dir.iterdir()) if p.is_dir()) if d] if self.dir.is_dir() else []
        if self.session is not None and all(m["name"] != self.session.name for m in found):
            found.append(dict(describe(self.session.path), name=self.session.name))
        return [dict(m, current=self.session is not None and m["name"] == self.session.name) for m in found]

    # the model to start with: the one used last time if it is still there, else the first
    def default(self):
        names = [m["name"] for m in self.available()]
        last = self.dir / ".last"
        if last.exists() and last.read_text().strip() in names:
            return last.read_text().strip()
        return names[0] if names else None

    # Loads a model by name (a folder of models/) or by path, and makes it the current one. Raises when it cannot.
    def load(self, name_or_path):
        path = self.dir / name_or_path
        path = path if path.is_dir() else Path(name_or_path)
        if describe(path) is None:
            raise FileNotFoundError(f"{name_or_path}: not a model folder (needs checkpoints/inference.gin and atlas.npz)")
        with self._lock:
            if self.session is not None and self.session.path == path:
                return self.session
            new = self.session_factory(path, name=path.name, device=self.device, checkpoint=self.checkpoint)
            old, self.session = self.session, new
            if old is not None:
                old.close()
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if self.dir.is_dir():
                (self.dir / ".last").write_text(path.name)
            return new
