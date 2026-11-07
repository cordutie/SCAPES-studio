"""The real-time generator. A thread that, step after step, takes the embedding the GUI is making right now, lets the
SCAPES model generate the next unit from it and from the units before, decodes it, and hands the new audio on.

No web code is here: the audio goes out through the `emit` callback and the player's position comes in through
`get_played_frames`, so the engine can be run and tested alone.

How a step goes (atoms: one hop of audio per step; autoregressive codecs: one block per step)
    wait until the audio ahead of the player is below the lead target  ->  read the current embedding
    ->  FlowInference.generate_step (NFE and CFG are read here, so a change applies to the next step)
    ->  decode the unit and overlap-add it  ->  emit the new samples
Stopping finishes the step in progress, then emits the fade-out of the last unit and ends.
"""
import math
import threading
import time

import numpy as np
import torch

import studio.scapes_path  # noqa: F401  (before SCAPES)
from SCAPES.inference.render import AtomStreamRenderer

from studio import config


# Decoding of atoms: overlap-add one at a time (SCAPES.inference.render.AtomStreamRenderer)
class _AtomsStream:
    def __init__(self, inference, seed):
        self.r = AtomStreamRenderer(inference.codec, inference.geom, inference.mu, inference.std, base_seed=seed)

    def push(self, unit):
        return self.r.push(unit)

    def finish(self):
        return self.r.finish()


# Decoding of autoregressive blocks: the codec's streaming decoder keeps its state; its first `latency` samples are dropped
class _ARStream:
    def __init__(self, inference, seed):
        self.inference = inference
        self.decoder = inference.codec.streaming_decoder(1)
        self.skip = int(self.decoder.latency_samples)

    def _drop_latency(self, y):
        cut = min(self.skip, y.shape[-1])
        self.skip -= cut
        return y[..., cut:]

    def push(self, unit):
        z = self.inference._unstandardise(unit[:, :self.inference.geom.latent_dim, :])
        return self._drop_latency(self.decoder.push(z)[0])

    def finish(self):
        return self._drop_latency(self.decoder.flush()[0])


class RealtimeEngine:
    def __init__(self, inference, get_embedding, emit, get_played_frames, on_end=lambda: None):
        """inference: a FlowInference. get_embedding() -> numpy (d,) or None. emit(samples float32 [ch, n]).
        get_played_frames() -> frames the player has played so far. on_end(): called when the run has ended."""
        self.inference = inference
        self.get_embedding, self.emit, self.get_played_frames, self.on_end = get_embedding, emit, get_played_frames, on_end
        g = inference.geom
        self.sr = inference.sr
        self.hop_s = (g.hop_samples if g.mode == "atoms" else g.unit_frames * g.hop_length) / g.sample_rate
        # the units the model looks back at: the timeline is cut to this many, so the cost of a step does not grow
        self.window = g.memory_units if g.mode == "atoms" else math.ceil(g.memory_frames / g.unit_frames)
        self.nfe, self.cfg = config.NFE_DEFAULT, config.CFG_DEFAULT          # read at every step
        self.lead_target_s = config.LEAD_TARGET_S
        self.state = "idle"                                                  # idle | running | stopping
        self.steps, self.step_ms, self.error = 0, 0.0, None
        self._worst = 0.0                                                   # slowest step since the last status(), over its hop
        self.produced_frames = 0
        self._stop = threading.Event()
        self._thread = None

    # --- control -------------------------------------------------------------------------------------------------

    # Starts a run. Returns (True, None), or (False, why) when it cannot start.
    def start(self):
        if self.state != "idle":
            return False, "already running"
        if self.get_embedding() is None:
            return False, "place a dot on the plane first"
        self._stop.clear()
        self.state, self.steps, self.step_ms, self.error = "running", 0, 0.0, None
        self.produced_frames, self.lead_target_s = 0, config.LEAD_TARGET_S
        self._thread = threading.Thread(target=self._run, name="scapes-engine", daemon=True)
        self._thread.start()
        return True, None

    # Stops after the step in progress, with the fade-out of the last unit. wait=True returns when the run has ended.
    def stop(self, wait=False):
        if self.state == "running":
            self.state = "stopping"
        self._stop.set()
        if wait and self._thread is not None:
            self._thread.join()

    # The player ran dry: keep more audio ahead from now on (an adaptive buffer, up to LEAD_MAX_S)
    def bump_lead(self):
        self.lead_target_s = min(config.LEAD_MAX_S, self.lead_target_s + config.LEAD_BUMP_S)

    def status(self):
        lead = (self.produced_frames - self.get_played_frames()) / self.sr
        worst, self._worst = self._worst, 0.0
        return {"state": self.state, "steps": self.steps, "load": self.step_ms / 1000 / self.hop_s, "worst": worst,
                "lead": max(0.0, lead), "target": self.lead_target_s, "error": self.error}

    # Runs the model on a made-up embedding for a few steps, so the first real step does not pay for the start-up
    def warmup(self, steps=3):
        timeline, stream = [], self._new_stream(seed=0)
        emb = torch.nn.functional.normalize(torch.randn(1, 1024, device=self.inference.device), dim=1)
        for _ in range(steps):
            self._step(timeline, stream, emb, self.nfe, self.cfg)

    # --- the thread ----------------------------------------------------------------------------------------------

    def _new_stream(self, seed):
        return (_AtomsStream if self.inference.geom.mode == "atoms" else _ARStream)(self.inference, seed)

    # One step: generate the unit of the next timeline entry, decode it, return the new samples as numpy [ch, n]
    def _step(self, timeline, stream, embedding, nfe, cfg):
        timeline.append({"step": len(timeline), "atom_given": None, "context_embedding": embedding,
                         "atom_generated": None, "TF": False})
        unit = self.inference.generate_step(timeline, len(timeline) - 1, nfe, cfg)
        samples = stream.push(unit).float().cpu().numpy()
        if len(timeline) > self.window:
            timeline.pop(0)
        return samples

    # Waits while there is already as much audio ahead of the player as the lead target asks
    def _wait_for_room(self):
        while not self._stop.is_set():
            if (self.produced_frames - self.get_played_frames()) / self.sr < self.lead_target_s:
                return
            self._stop.wait(0.004)

    def _send(self, samples):
        if samples.shape[-1]:
            self.produced_frames += samples.shape[-1]
            self.emit(samples)

    def _run(self):
        try:
            self.inference.model.eval()
            self.inference.local_encoder.eval()
            timeline = []
            stream = self._new_stream(seed=int(time.time()) % 100000)
            embedding = None
            while True:
                self._wait_for_room()
                if self._stop.is_set():
                    break
                vector = self.get_embedding()
                if vector is not None:                    # the GUI cleared its dots: keep the last embedding
                    embedding = torch.from_numpy(vector).to(self.inference.device)[None]
                t0 = time.perf_counter()
                self._send(self._step(timeline, stream, embedding, self.nfe, self.cfg))
                ms = 1000 * (time.perf_counter() - t0)
                self.step_ms = ms if self.steps == 0 else 0.9 * self.step_ms + 0.1 * ms
                self._worst = max(self._worst, ms / 1000 / self.hop_s)
                self.steps += 1
            self._send(stream.finish().float().cpu().numpy())
        except Exception as exc:                          # shown in the page, not raised in the thread
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.state = "idle"
            self.on_end()
