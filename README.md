# SCAPES Studio

Interactive demos of **[SCAPES](https://github.com/cordutie/SCAPES)**, a generative model of environmental sounds controlled through
an atlas of its data. Two modes:

| Mode | What it is | Needs | Status |
|---|---|---|---|
| **Live** | Real-time generation: drop semantic sources on a plane, move a point between them, and the sound follows. Atlas, effects, meter and recorder. | An NVIDIA GPU that keeps up with the sound | working |
| **Score** | Offline generation on a timeline: arrange sources over time, render, listen, export. | Any GPU (it does not run in real time) | the page works (sources, playground, timeline, model panel, log, takes); generating the piece is the next step |

`python app.py` opens the start page, where you choose one. `python app_live.py` and `python app_score.py` open a mode directly.
Online: [huggingface.co/spaces/cordutie/SCAPES-demo](https://huggingface.co/spaces/cordutie/SCAPES-demo) (Live needs a GPU of its
own: on a shared one it stops suddenly, so run it locally).

## Run it

Quick path (Ubuntu; needs git and the venv module for your Python):

```bash
sudo apt install -y git python3-venv          # or python3.12-venv
git clone https://github.com/cordutie/SCAPES-studio && cd SCAPES-studio
./setup.sh                                    # environment, packages, SpectroStream weights, models
source .venv/bin/activate && python app.py    # then open http://127.0.0.1:7860
```

`setup.sh` takes the environment from `.venv` (change it with `VENV=...`) and the Python from `python3` (change it with
`PYTHON=python3.12 ./setup.sh`). The same steps by hand:

1. `python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
2. `pip install --no-deps magenta-rt==2.0.3` (for the SpectroStream models; its own dependencies are not needed)
3. `python tools/fetch_codec_weights.py`: the SpectroStream codec weights (247 MB) into `~/.cache/audio_codec_wrappers/`
   (`ACW_CACHE` changes the folder). Music2latent downloads its own weights on first use.
4. `python -c "from studio.hub import fetch_models; fetch_models('models')"`: the models of
   [cordutie/SCAPES-models](https://huggingface.co/cordutie/SCAPES-models) into `models/`. `python app.py --fetch` does the same.
5. `python app.py`, then open http://127.0.0.1:7860.

Without models, Live says so and where to get them; the start page and Score still open.
The project was written for Python 3.12; Python 3.14 also installed and ran on a test machine.

| What you see | Cause | Fix |
|---|---|---|
| `FileNotFoundError: .../site-packages/weights.lock.json` (Live, music2latent) | the codec wrappers pinned at an old commit looked for their lock file outside the package | the pin is `audio_codec_wrappers@4a4db83` in `requirements.txt`; reinstall with `pip install --no-deps --force-reinstall "audio-codec-wrappers @ git+https://github.com/cordutie/audio_codec_wrappers@4a4db83"` |
| `spectrostream weights not found ... run: python scripts/fetch_weights.py` (Live, SpectroStream) | the weights are not in the cache | `python tools/fetch_codec_weights.py` (not the wrappers' script: that one rewrites the lock file) |
| `python3 -m venv` fails with `ensurepip is not available` | the venv module is not installed | `sudo apt install python3-venv` |
| `git: command not found` | git is not installed | `sudo apt install git` |
| Live does not keep up with the sound | the GPU is too slow for real time | use a faster GPU; Score works on any GPU |

## Models

A model is a folder of `models/` (gitignored), the same shape as a folder of the Hugging Face repository:
`<name>/checkpoints/inference.gin`, `best_*.pt` (or `last_*.pt`), `latent_stats.pt`, and `<name>/atlas.npz` (the atlas that dataprep makes
with `GUI = True`). Make one from a trained model with `python tools/add_model.py <build>/models/<size>_mem<ms>`.
A model can also have `<name>/snippets/` (`000.mp3`, `001.mp3`, …: the audio of the representatives that its atlas lists, for Score mode; Live
does not use them). The atlas can have up to 60 clusters; the cluster panel of Live scrolls.
The Live page has a menu to switch models; the last one used starts next time.

## Layout

| Where | What |
|---|---|
| `setup.sh` | the whole setup of a new machine (see Run it) |
| `tools/` | `fetch_codec_weights.py` (SpectroStream weights), `add_model.py` (a model from a build) |
| `app.py`, `app_live.py`, `app_score.py` | the three ways to start (a mode is a page mounted on the same server) |
| `studio/` | Python: `config.py` (every number), `models.py`, `hub.py`, `server.py`, `atlas_model.py`, `hull.py` |
| `studio/live/` | Live: the generator thread (`engine.py`), the model session, the audio line (`transport.py`), the page's server functions |
| `studio/score/` | Score: `library.py` (the models that have snippets), `takes.py` (the generated pieces, wavs in `takes/`, gitignored), `score_api.py` (the server functions), `page.py` (the page and the snippets and takes routes) |
| `web/shared/` | what every page uses: the look (`theme.css`, `theme.js`), knobs, the (i) texts (`info.js`), the effects |
| `web/live/` | the Live page: one file per panel in `blocks/`, the audio player in `audio/`, the grid in `layout.html` |
| `web/score/` | the Score page: the grid in `layout.html`, one file per block in `blocks/` (sources, takes, playground, timeline, settings, log) |
| `web/selector/` | the start page |
| `tests/` | `test_live_api.py` (pytest, no GPU), and browser checks: `studio_check.py` (start page, modes, warning), `score_check.py`, `midi_check.py`, `ui_check.py`, `browser_check.py`, `model_menu_check.py`, `engine_check.py` |

Where to change things: numbers in `studio/config.py`; the look in `web/shared/theme.css` and `theme.js`; the panel texts in
`web/shared/info.js`; the grid of Live in `web/live/layout.html` and `BLOCKS` in `web/live/main.js`; an effect in
`web/shared/audio/fx/<name>.js` (listed in `index.js`).

## Tests

```bash
pip install -r requirements-dev.txt && playwright install chromium
python -m pytest tests -q                  # the server functions
python tests/studio_check.py               # the combined app in a browser (starts its own servers)
python app_live.py --port 7871 & python tests/ui_check.py && python tests/browser_check.py 7871
```

## Licence

MIT.
