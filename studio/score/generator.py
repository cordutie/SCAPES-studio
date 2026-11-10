"""Generates a score offline, in one pass: the model is run step after step along the path of embeddings (studio/score/path.py), the
units are decoded as they come (the same stream decoders as Live) and the whole piece is returned. One model is kept loaded."""
import threading

import numpy as np
import torch

import studio.scapes_path  # noqa: F401  (before SCAPES)
from SCAPES.inference.FlowInference import FlowInference

from studio.gpu import on_gpu
from studio.live.engine import RealtimeEngine


# the model is loaded and run inside a GPU call (studio/gpu.py): on ZeroGPU the GPU exists only inside one, and the render runs in a job thread
@on_gpu
def _hop_on_gpu(generator, name):
    return generator._hop(name)


@on_gpu
def _render_on_gpu(generator, name, rows, nfe, cfg, seed, progress):
    return generator._render(name, rows, nfe, cfg, seed, progress)


class Generator:
    def __init__(self, library, device=None):
        self.library = library
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._loaded = None                                 # (name, inference, engine)
        self.lock = threading.Lock()                        # one piece at a time

    def _load(self, name):
        if self._loaded is None or self._loaded[0] != name:
            self._loaded = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            inference = FlowInference(self.library.model(name).path, device=self.device, checkpoint="best")
            inference.model.eval()
            inference.local_encoder.eval()
            engine = RealtimeEngine(inference, lambda: None, lambda s: None, lambda: 0)
            self._loaded = (name, inference, engine)
        return self._loaded[1], self._loaded[2]

    # the seconds of audio per step of the path (what a row of the path lasts); this loads the model
    def hop_s(self, name):
        return _hop_on_gpu(self, name)

    def _hop(self, name):
        return self._load(name)[1].hop_s

    # embeddings [n, d] -> (samples [n, channels] float32, sample rate). progress(done, total) is called after every step.
    def render(self, name, rows, nfe, cfg, seed, progress=lambda done, total: None):
        return _render_on_gpu(self, name, rows, nfe, cfg, seed, progress)

    @torch.no_grad()
    def _render(self, name, rows, nfe, cfg, seed, progress):
        inference, engine = self._load(name)
        torch.manual_seed(int(seed))
        np.random.seed(int(seed) % (2 ** 32))
        timeline, stream, parts = [], engine._new_stream(seed=int(seed)), []
        for k, row in enumerate(rows):
            emb = torch.from_numpy(row).to(inference.device)[None]
            parts.append(engine._step(timeline, stream, emb, int(nfe), float(cfg)))
            progress(k + 1, len(rows))
        parts.append(stream.finish().float().cpu().numpy())
        audio = np.concatenate([p for p in parts if p.shape[-1]], axis=-1)           # [channels, samples]
        return np.ascontiguousarray(audio.T, dtype=np.float32), int(inference.sr)
