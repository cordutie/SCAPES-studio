"""Manual check of the engine on a real model: (1) same audio as the offline generation, (2) speed against real time.
Run: python tests/engine_check.py [model_dir]"""
import sys, time
import numpy as np, torch
sys.path.insert(0, ".")
import studio.scapes_path  # noqa
from SCAPES.inference.FlowInference import FlowInference
from studio.atlas_model import AtlasModel
from studio.live.engine import RealtimeEngine

model_dir = sys.argv[1] if len(sys.argv) > 1 else "../data/models_build/tape_echo_music2latent_10hz_1000ms/models/small_mem1000"
inf = FlowInference(model_dir, device="cuda", checkpoint="best")
atlas = AtlasModel.load(f"{model_dir}/atlas.npz")
g = inf.geom
print("mode", g.mode, "sr", inf.sr, "hop_s", g.hop_samples / g.sample_rate, "window", inf.geom.memory_units)
vec = atlas.from_mean(atlas.mu[2], [0.3, -0.2]).astype(np.float32)

# (1) the same audio as the offline generation
N = 25
chunks = []
eng = RealtimeEngine(inf, lambda: vec, chunks.append, lambda: 10**12)   # the player is infinitely far: no waiting
eng.nfe, eng.cfg = 8, 1.0
torch.manual_seed(0)
timeline = [{"step": t, "atom_given": None, "context_embedding": torch.from_numpy(vec).cuda()[None],
             "atom_generated": None, "TF": False} for t in range(N)]
inf.decode_seed = 0
inf.generate(timeline, NFE=8, cfg_scale=1.0)
offline = inf.decode_timeline(timeline).numpy()
lead = g.atom_samples - g.hop_samples - g.crossfade_samples
# the engine: N steps, then stop. Reproduce: seed the RNG, and the decoder seed is 0
import studio.live.engine as E
torch.manual_seed(0)
stream = E._AtomsStream(inf, 0); tl = []
parts = [eng._step(tl, stream, torch.from_numpy(vec).cuda()[None], 8, 1.0) for _ in range(N)] + [stream.finish().float().cpu().numpy()]
online = np.concatenate(parts, axis=1)
print("offline", offline[:, lead:].shape, "online", online.shape, "max abs diff", float(np.abs(online - offline[:, lead:]).max()),
      "peak", float(np.abs(offline).max()))

# (2) speed: run the engine for 6 s against a fake player that plays in real time
for nfe in (8, 16, 32):
    chunks.clear()
    t0 = time.perf_counter()
    eng = RealtimeEngine(inf, lambda: vec, chunks.append, lambda: int((time.perf_counter() - t0) * inf.sr))
    eng.nfe = nfe
    eng.warmup()
    t0 = time.perf_counter()
    ok, why = eng.start(); assert ok, why
    time.sleep(6)
    eng.stop(wait=True)
    got = sum(c.shape[1] for c in chunks) / inf.sr
    print(f"NFE {nfe}: {eng.steps} steps, step {eng.step_ms:.1f} ms of {eng.hop_s*1000:.1f} ms hop (load {eng.step_ms/1000/eng.hop_s:.2f}), "
          f"audio {got:.2f} s in 6 s, error {eng.error}")
