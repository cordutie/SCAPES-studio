"""Generates a score offline, in one pass: the model is run step after step along the path of embeddings (studio/score/path.py), the
units are decoded as they come (the same stream decoders as Live) and the whole piece is returned. One model is kept loaded.

On ZeroGPU the model work runs in a GPU call (studio/gpu.py), whose arguments are pickled: so the functions below take only plain
values (a path, a device name, numbers and arrays), and the model is kept at module level, not on the Generator."""
import os
import tempfile
import threading

import numpy as np
import torch

import studio.scapes_path  # noqa: F401  (before SCAPES)
from SCAPES.inference.FlowInference import FlowInference

from studio import config
from studio.gpu import on_gpu
from studio.live.engine import RealtimeEngine

_LOADED = {"key": None, "inference": None, "engine": None}      # the one model kept loaded


def _load(path, device):
    key = (path, device)
    if _LOADED["key"] != key:
        _LOADED.update(key=None, inference=None, engine=None)
        if device == "cuda":
            torch.cuda.empty_cache()
        inference = FlowInference(path, device=device, checkpoint="best")
        inference.model.eval()
        inference.local_encoder.eval()
        engine = RealtimeEngine(inference, lambda: None, lambda s: None, lambda: 0)
        _LOADED.update(key=key, inference=inference, engine=engine)
    return _LOADED["inference"], _LOADED["engine"]


# the seconds of audio per step of the path (what a row of the path lasts); this loads the model
def _hop(path, device):
    return _load(path, device)[1].hop_s


# embeddings [n, d] -> (samples [n, channels] float32, sample rate). After every step: progress(done, total) if given, and the
# numbers are written to progress_file if given (a file, because on a Space the GPU call cannot take a callback)
@torch.no_grad()
def _render(path, device, rows, nfe, cfg, seed, progress, progress_file):
    inference, engine = _load(path, device)
    torch.manual_seed(int(seed))
    np.random.seed(int(seed) % (2 ** 32))
    timeline, stream, parts = [], engine._new_stream(seed=int(seed)), []
    for k, row in enumerate(rows):
        emb = torch.from_numpy(row).to(inference.device)[None]
        parts.append(engine._step(timeline, stream, emb, int(nfe), float(cfg)))
        if progress:
            progress(k + 1, len(rows))
        if progress_file:
            with open(progress_file, "w") as f:
                f.write(f"{k + 1} {len(rows)}")
    parts.append(stream.finish().float().cpu().numpy())
    audio = np.concatenate([p for p in parts if p.shape[-1]], axis=-1)           # [channels, samples]
    return np.ascontiguousarray(audio.T, dtype=np.float32), int(inference.sr)


# the same functions inside a GPU call on ZeroGPU; anywhere else they are the plain functions
_hop_gpu = on_gpu(_hop)
_render_gpu = on_gpu(_render)


class Generator:
    def __init__(self, library, device=None):
        self.library = library
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.lock = threading.Lock()                        # one piece at a time

    def _path(self, name):
        return str(self.library.model(name).path)

    def hop_s(self, name):
        return _hop_gpu(self._path(name), self.device)

    # embeddings [n, d] -> (samples [n, channels] float32, sample rate). progress(done, total) is called after every step. On a Space
    # the GPU call writes the steps to a file, and a thread here reads it and calls progress.
    def render(self, name, rows, nfe, cfg, seed, progress=lambda done, total: None):
        rows = np.ascontiguousarray(rows, dtype=np.float32)
        path, args = self._path(name), (self.device, rows, int(nfe), float(cfg), int(seed))
        if not config.ON_HUGGING_FACE:
            return _render_gpu(path, *args, progress, None)
        fd, progress_file = tempfile.mkstemp(suffix=".progress")
        os.close(fd)
        stop = threading.Event()

        def watch():
            last = None
            while not stop.wait(0.3):
                now = _read_progress(progress_file)
                if now and now != last:
                    last = now
                    progress(*now)

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            samples = _render_gpu(path, *args, None, progress_file)
        finally:
            stop.set()
            watcher.join()
            os.remove(progress_file)
        progress(len(rows), len(rows))                  # the watcher may have missed the last steps
        return samples


def _read_progress(progress_file):
    try:
        with open(progress_file) as f:
            done, total = f.read().split()
        return int(done), int(total)
    except (OSError, ValueError):
        return None
