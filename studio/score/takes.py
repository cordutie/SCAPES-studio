"""The takes of Score mode: the pieces it generated, kept in config.TAKES_DIR as <id>.wav with <id>.json next to it (what made it: the model,
NFE, CFG, seed, the clips). Newest first. Nothing here generates: the generator hands `add` the samples when it has them."""
import json
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ID = re.compile(r"^take-[0-9]{8}-[0-9]{6}(-[0-9]+)?$")


class Takes:
    def __init__(self, folder):
        self.dir = Path(folder)

    def path(self, take_id):
        if not ID.match(take_id):
            raise ValueError(f"{take_id}: not a take")
        return self.dir / f"{take_id}.wav"

    # the takes, newest first: each is its json (id, name, created, seconds, model, nfe, cfg, seed, clips)
    def list(self):
        out = []
        for j in sorted(self.dir.glob("take-*.json"), reverse=True) if self.dir.is_dir() else []:
            try:
                meta = json.loads(j.read_text())
            except (OSError, ValueError):
                continue
            if ID.match(str(meta.get("id", ""))) and (self.dir / f"{meta['id']}.wav").exists():
                out.append(meta)
        return out

    # samples [n, channels] float32 at `sr`; meta: model, nfe, cfg, seed, clips. Returns the take
    def add(self, samples, sr, meta):
        self.dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("take-%Y%m%d-%H%M%S")
        take_id, n = stamp, 1
        while (self.dir / f"{take_id}.wav").exists():
            n += 1
            take_id = f"{stamp}-{n}"
        samples = np.asarray(samples, dtype=np.float32)
        sf.write(self.dir / f"{take_id}.wav", samples, int(sr), subtype="PCM_16")
        take = dict(meta, id=take_id, name=meta.get("name") or take_id.replace("take-", "take "), created=time.strftime("%Y-%m-%d %H:%M:%S"),
                    seconds=round(len(samples) / sr, 2), sample_rate=int(sr))
        (self.dir / f"{take_id}.json").write_text(json.dumps(take, indent=1))
        return take

    def delete(self, take_id):
        self.path(take_id)                                  # validates the id
        for suffix in (".wav", ".json"):
            (self.dir / f"{take_id}{suffix}").unlink(missing_ok=True)
