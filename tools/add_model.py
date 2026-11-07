"""Puts a trained model into models/ so the page can play it: copies what playing needs (not the epoch checkpoints, the losses,
the validation audio or the dataset), and gives its atlas the cluster names and the prior if it was saved without them (a model
trained before dataprep wrote them), learning both from the CLAP embeddings that are still in the build folder.

    python tools/add_model.py <build>/models/<size>_mem<ms> [--name NAME]

The name defaults to <build folder>_<model folder>. The trained model is not changed."""
import argparse
import shutil
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import studio.scapes_path  # noqa: F401,E402  (before SCAPES)
from SCAPES.auxiliar.atlas import Atlas  # noqa: E402

CHECKPOINT_FILES = ["inference.gin", "best_flow_model.pt", "best_local_encoder.pt", "last_flow_model.pt",
                    "last_local_encoder.pt", "latent_stats.pt"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("model_dir")
    p.add_argument("--name", default=None)
    p.add_argument("--models-dir", default=str(ROOT / "models"))
    args = p.parse_args()
    src = Path(args.model_dir).resolve()
    if not (src / "atlas.npz").exists() or not (src / "checkpoints" / "inference.gin").exists():
        sys.exit(f"{src}: needs atlas.npz (the model must be trained with GUI = True) and checkpoints/inference.gin")
    name = args.name or f"{src.parent.parent.name}_{src.name}"
    dst = Path(args.models_dir) / name
    if dst.exists():
        sys.exit(f"{dst} exists: choose another --name, or delete it")
    (dst / "checkpoints").mkdir(parents=True)
    for f in CHECKPOINT_FILES:
        if (src / "checkpoints" / f).exists():
            shutil.copy2(src / "checkpoints" / f, dst / "checkpoints" / f)
    shutil.copy2(src / "atlas.npz", dst / "atlas.npz")

    atlas = Atlas.load(dst / "atlas.npz")
    if atlas.prior is None or all(n.startswith("cluster ") for n in atlas.names):
        files = sorted(src.parent.parent.glob("dataset/representations/*/clap/*/**/*.pt"))
        if files:
            atlas.add_names_and_prior([torch.load(f, weights_only=True) for f in files], [f.stem for f in files])
            atlas.save(dst / "atlas.npz")
            print(f"atlas: names and prior learned from {len(files)} embedding files")
        else:
            print("atlas: no names and no prior (the CLAP embeddings of the build folder were not found)")
    size = sum(f.stat().st_size for f in dst.rglob("*") if f.is_file()) / 1e6
    print(f"{name}: {atlas.K} clusters {atlas.names}, prior {'yes' if atlas.prior else 'no'}, {size:.0f} MB\n-> {dst}")


if __name__ == "__main__":
    main()
