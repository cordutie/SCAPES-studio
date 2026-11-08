"""The models Score mode can show: the folders of models/ that have the audio of the representatives of their clusters
(snippets/, see SCAPES/data/dataprep/snippets.py). Score does not load the model to arrange sources on a timeline, only its atlas."""
from pathlib import Path
from types import SimpleNamespace

import studio.scapes_path  # noqa: F401  (before SCAPES)
from SCAPES.auxiliar.atlas import Atlas

from studio.models import describe


class Library:
    def __init__(self, models_dir):
        self.dir = Path(models_dir)
        self._cache = {}

    # the models that can be shown, by name
    def available(self):
        if not self.dir.is_dir():
            return []
        return [d for d in (describe(p) for p in sorted(self.dir.iterdir()) if p.is_dir() and (p / "snippets").is_dir()) if d]

    # the model used last time in Live if it can be shown here, else the first
    def default(self):
        names = [m["name"] for m in self.available()]
        last = self.dir / ".last"
        if last.exists() and last.read_text().strip() in names:
            return last.read_text().strip()
        return names[0] if names else None

    # {name, path, atlas}; the atlas must have representatives
    def model(self, name):
        if name not in {m["name"] for m in self.available()}:
            raise ValueError(f"{name}: not a model with snippets")
        if name not in self._cache:
            path = self.dir / name
            atlas = Atlas.load(path / "atlas.npz")
            if atlas.reps is None or len(atlas.reps) == 0:
                raise ValueError(f"{name}: its atlas has no representatives")
            count = len(list((path / "snippets").glob("*.mp3")))
            if count != len(atlas.reps):
                raise ValueError(f"{name}: {len(atlas.reps)} representatives but {count} snippets")
            self._cache[name] = SimpleNamespace(name=name, path=path, atlas=atlas)
        return self._cache[name]
