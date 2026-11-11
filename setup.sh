#!/usr/bin/env bash
# Sets up SCAPES Studio from this folder: an environment, the packages, the SpectroStream weights and the models.
#   ./setup.sh                  (environment in .venv; PYTHON=python3.12 ./setup.sh to choose the Python; VENV=... to choose the folder)
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV="${VENV:-.venv}"

die() { echo "error: $*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "git is missing. Install it with: sudo apt install git"
command -v "$PYTHON" >/dev/null 2>&1 || die "$PYTHON is missing. Install Python 3.12 (or pass PYTHON=/path/to/python)"
"$PYTHON" -c "import ensurepip" >/dev/null 2>&1 || die "the venv module is missing for $PYTHON. Install it with: sudo apt install python3-venv (or python3.12-venv)"

if [ ! -d "$VENV" ]; then
    echo "==> creating the environment $VENV"
    "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"

echo "==> installing the packages (this takes a while: torch, jax)"
python -m pip install --upgrade pip
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    echo "    NVIDIA GPU found: CUDA builds (torch cu128, jax cuda12)"
    python -m pip install -r requirements.txt
else
    echo "    no NVIDIA GPU: CPU builds (torch cpu, plain jax). SpectroStream still works, on the CPU."
    REQ="$(mktemp)"
    grep -v -E '^(torch|torchaudio|--extra-index-url)' requirements.txt | sed 's/^jax\[cuda12\]==/jax==/' > "$REQ"
    python -m pip install torch==2.10.0+cpu torchaudio==2.10.0+cpu --index-url https://download.pytorch.org/whl/cpu
    python -m pip install -r "$REQ"
    rm -f "$REQ"
fi
python -m pip install --no-deps magenta-rt==2.0.3          # for the SpectroStream models; its own dependencies are not needed

echo "==> SpectroStream codec weights"
python tools/fetch_codec_weights.py

echo "==> models (from cordutie/SCAPES-models)"
python -c "import sys; from studio.hub import fetch_models; sys.exit(0 if fetch_models('models') else 1)" \
    || die "the models could not be downloaded (see the message above). Run this script again when the connection works."

echo
echo "Done. To run SCAPES Studio:"
echo "    source $VENV/bin/activate && python app.py"
echo "then open http://127.0.0.1:7860"
