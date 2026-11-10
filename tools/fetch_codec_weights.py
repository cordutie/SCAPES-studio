"""Downloads the SpectroStream codec weights (see studio/codec_weights.py). Run it from the SCAPES-studio folder:

    python tools/fetch_codec_weights.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio.codec_weights import fetch  # noqa: E402

if __name__ == "__main__":
    sys.exit(0 if fetch() else 1)
