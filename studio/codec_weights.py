"""The codec weights that the models need beyond their own folder: SpectroStream (for Live, with the SpectroStream models) comes from
google/magenta-realtime-2 at the revision and with the sha256 that the installed audio_codec_wrappers records in its weights.lock.json.
The wrappers' own scripts/fetch_weights.py would rewrite that file with the newest revision, so this module never does.
Files go to ~/.cache/audio_codec_wrappers/spectrostream/ (ACW_CACHE changes the root). A file already there with the right hash is kept.
music2latent needs nothing here: it downloads its own weights on first use. fetch() never raises: it says what went wrong and returns False."""
import hashlib
import importlib.util
import json
import os
import pathlib

CODEC = "spectrostream"
REPO = "google/magenta-realtime-2"


def lock_path():
    spec = importlib.util.find_spec("audio_codec_wrappers")      # finds the package without importing it (no jax, no torch)
    if spec is None or spec.origin is None:
        raise RuntimeError("audio_codec_wrappers is not installed (pip install -r requirements.txt)")
    return pathlib.Path(spec.origin).parent / "weights.lock.json"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def fetch():
    try:
        from huggingface_hub import hf_hub_download
        entry = json.loads(lock_path().read_text())[CODEC]["codec"]
        revision, files = entry["revision"], entry["files"]
        root = pathlib.Path(os.environ.get("ACW_CACHE", pathlib.Path.home() / ".cache" / "audio_codec_wrappers"))
        out = root / CODEC
        out.mkdir(parents=True, exist_ok=True)
        for name, info in files.items():
            target = out / name
            if target.exists() and sha256_of(target) == info["sha256"]:
                print(f"SpectroStream weights: {name} is there")
                continue
            print(f"SpectroStream weights: downloading {name} ({info['bytes'] / 1e6:.0f} MB) at {revision[:7]}")
            got = pathlib.Path(hf_hub_download(REPO, name, revision=revision, local_dir=out))
            if sha256_of(got) != info["sha256"]:
                got.unlink()
                raise RuntimeError(f"{name}: sha256 differs from weights.lock.json; the file was removed")
        print(f"SpectroStream weights are in {out}")
        return True
    except Exception as exc:                  # no network, a bad file: say so, the rest of the app still starts
        print(f"Could not get the SpectroStream weights: {type(exc).__name__}: {exc}")
        return False
