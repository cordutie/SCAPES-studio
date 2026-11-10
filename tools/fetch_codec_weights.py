"""Downloads the SpectroStream codec weights (what SpectroStream models need in Live) at the revision and with the sha256 that the installed
audio_codec_wrappers records in its weights.lock.json. It never rewrites that file (the wrappers' own scripts/fetch_weights.py does, with
the newest revision, which would change what the pinned install expects).

    python tools/fetch_codec_weights.py

Files go to ~/.cache/audio_codec_wrappers/spectrostream/ (override the root with ACW_CACHE). A file that is already there with the right
hash is kept. music2latent needs nothing here: it downloads its own weights on first use.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import sys

CODEC = "spectrostream"
REPO = "google/magenta-realtime-2"


def lock_path():
    spec = importlib.util.find_spec("audio_codec_wrappers")         # finds the package without importing it (no jax, no torch)
    if spec is None or spec.origin is None:
        sys.exit("audio_codec_wrappers is not installed: run pip install -r requirements.txt first")
    return pathlib.Path(spec.origin).parent / "weights.lock.json"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def main():
    from huggingface_hub import hf_hub_download

    entry = json.loads(lock_path().read_text())[CODEC]["codec"]
    revision, files = entry["revision"], entry["files"]
    root = pathlib.Path(os.environ.get("ACW_CACHE", pathlib.Path.home() / ".cache" / "audio_codec_wrappers"))
    out = root / CODEC
    out.mkdir(parents=True, exist_ok=True)
    for name, info in files.items():
        target = out / name
        if target.exists() and sha256_of(target) == info["sha256"]:
            print(f"ok       {name} (already there)")
            continue
        print(f"download {name} ({info['bytes'] / 1e6:.0f} MB) from {REPO} at {revision[:7]}")
        got = pathlib.Path(hf_hub_download(REPO, name, revision=revision, local_dir=out))
        if sha256_of(got) != info["sha256"]:
            got.unlink()
            sys.exit(f"{name}: sha256 differs from weights.lock.json; the file was removed")
    print(f"SpectroStream weights are in {out}")


if __name__ == "__main__":
    main()
