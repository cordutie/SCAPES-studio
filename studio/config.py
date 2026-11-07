"""Every number you may want to change, in one place. The look of the pages is web/shared/theme.css and web/shared/theme.js."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
MODELS_DIR = ROOT / "models"

# on Hugging Face a Space sets SPACE_ID (and runs in a container that must listen on 0.0.0.0, port 7860)
ON_HUGGING_FACE = bool(os.environ.get("SPACE_ID"))

# server
HOST = "0.0.0.0" if ON_HUGGING_FACE else "127.0.0.1"
PORT = int(os.environ.get("PORT", 7860))

# the Hugging Face repository with the models (the same folders as models/); the app downloads from it on a Space, or with --fetch
MODELS_REPO = "cordutie/SCAPES-models"
GITHUB_URL = "https://github.com/cordutie/SCAPES-studio"

# the model folder (the one with checkpoints/ and atlas.npz); --model or this variable overrides it
MODEL_DIR = os.environ.get("SCAPES_STUDIO_MODEL", "")

# generation controls: default, range and step shown in the Generation block
NFE_DEFAULT, NFE_RANGE = 8, (1, 64)
CFG_DEFAULT, CFG_RANGE, CFG_STEP = 1.0, (0.0, 10.0), 0.1

# real time. Lead = audio generated but not yet played. The generator waits when the lead is at LEAD_TARGET_S; the
# browser starts playing when PREBUFFER_S of audio has arrived. Each time the browser runs dry (an underrun) the target
# grows by LEAD_BUMP_S, up to LEAD_MAX_S, so a slow machine settles on a buffer it can keep full.
PREBUFFER_S = 0.30
LEAD_TARGET_S = 0.40
LEAD_BUMP_S = 0.10
LEAD_MAX_S = 2.00
STATUS_PERIOD_S = 0.10

# the light of the Generation block: orange when a step takes more than LOAD_WARN of the audio it makes (its hop), red when the
# player ran dry (a frame was not there in time), which stays on for LATE_HOLD_S so that it can be seen; green otherwise
LOAD_WARN = 0.85
LATE_HOLD_S = 1.5

# the Live page shows at most this many cluster blocks (the palette in web/shared/theme.js holds 32)
MAX_CLUSTERS = 32
