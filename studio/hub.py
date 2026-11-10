"""The models on Hugging Face: one folder per model in the models repo (config.MODELS_REPO), the same shape as models/.
fetch_models downloads the ones that are missing, or the ones asked for by name, and (with no names) the codec weights that the models
need beyond their folders (studio/codec_weights.py). It never raises: with no network, or an empty repo, it says so and the app starts
with the models it has."""
from pathlib import Path

from studio import config


def fetch_models(models_dir, names=None, repo=config.MODELS_REPO):
    ok = True
    try:
        from huggingface_hub import snapshot_download
        patterns = [f"{n}/*" for n in names] if names else None
        snapshot_download(repo_id=repo, repo_type="model", local_dir=str(Path(models_dir)), allow_patterns=patterns)
        print(f"Models of {repo} are in {models_dir}")
    except Exception as exc:                      # no network, an empty or private repo, a name that is not there...
        print(f"Could not get the models of {repo}: {type(exc).__name__}: {exc}")
        ok = False
    if names is None:
        from studio.codec_weights import fetch as fetch_codec
        ok = fetch_codec() and ok
    return ok
