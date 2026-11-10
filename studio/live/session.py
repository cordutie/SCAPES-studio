"""One listener: the model, the embedding the GUI is making, the real-time engine, and the state the player reports.
The web layers (transport.py for the audio, live_api.py for the page) talk to this object and to nothing deeper."""
from pathlib import Path

import numpy as np
import torch

import studio.scapes_path  # noqa: F401  (before SCAPES)
from SCAPES.inference.FlowInference import FlowInference

from studio import config
from studio.atlas_model import AtlasModel
from studio.live.engine import RealtimeEngine
from studio.live.live_feed import LiveFeed


class Session:
    def __init__(self, model_dir, name=None, device=None, checkpoint="best"):
        model_dir = Path(model_dir)
        if not (model_dir / "atlas.npz").exists():
            raise FileNotFoundError(f"{model_dir / 'atlas.npz'} is missing: Live needs a model trained with GUI = True")
        # on a Hugging Face Space (ZeroGPU) the GPU exists only inside a @spaces.GPU call, so the model stays on the CPU there
        device = device or ("cuda" if torch.cuda.is_available() and not config.ON_HUGGING_FACE else "cpu")
        self.path, self.name = model_dir, name or model_dir.name
        self.inference = FlowInference(model_dir, device=device, checkpoint=checkpoint)
        self.atlas = AtlasModel(self.inference.atlas)
        self.feed = LiveFeed()
        self.sink = None                      # the connected player (transport.py), or None
        self.run, self.played, self.underruns = 0, 0, 0
        self.engine = RealtimeEngine(self.inference, self.feed.latest, self._emit, lambda: self.played, self._ended)
        self.engine.warmup()

    # --- from the engine thread ---
    def _emit(self, samples):
        if self.sink is not None:
            self.sink.audio(samples)

    def _ended(self):
        if self.sink is not None:
            self.sink.ended()

    # Ends this session: the generator stops (with its fade-out) and the model can be freed
    def close(self):
        self.sink = None
        self.engine.stop(wait=True)

    # --- from the page ---
    def attach(self, sink):
        self.sink = sink

    def detach(self, sink):
        if self.sink is sink:
            self.sink = None
            self.engine.stop()

    # Play: returns (run id, None), or (None, why). The player counts its frames from 0 for each run id.
    def play(self):
        if self.engine.state != "idle":
            return None, "already running"
        self.run, self.played, self.underruns = self.run + 1, 0, 0
        ok, why = self.engine.start()
        return (self.run, None) if ok else (None, why)

    def stop(self):
        self.engine.stop()

    # NFE and CFG apply from the next step
    def set_params(self, nfe=None, cfg=None):
        if nfe is not None:
            self.engine.nfe = int(min(max(nfe, config.NFE_RANGE[0]), config.NFE_RANGE[1]))
        if cfg is not None:
            self.engine.cfg = float(min(max(cfg, config.CFG_RANGE[0]), config.CFG_RANGE[1]))

    def acked(self, run, frames):
        if run == self.run:
            self.played = int(frames)

    def underrun(self, run):
        if run == self.run:
            self.underruns += 1
            self.engine.bump_lead()

    def info(self):
        g = self.inference.geom
        memory_s = (g.memory_units * self.engine.hop_s if g.mode == "atoms" else g.memory_frames * g.hop_length / g.sample_rate)
        return {"model": self.name, "sample_rate": int(self.inference.sr), "channels": 2,
                "rate_hz": 1.0 / self.engine.hop_s, "memory_s": float(memory_s), "codec_mode": g.mode,
                "prebuffer_s": config.PREBUFFER_S, "nfe": self.engine.nfe, "cfg": self.engine.cfg,
                "nfe_range": list(config.NFE_RANGE), "cfg_range": list(config.CFG_RANGE), "cfg_step": config.CFG_STEP,
                "load_warn": config.LOAD_WARN, "late_hold_s": config.LATE_HOLD_S}

    def status(self):
        return dict(self.engine.status(), underruns=self.underruns, run=self.run)
