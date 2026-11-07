# SCAPES Studio

Interactive demos of **[SCAPES](https://github.com/cordutie/SCAPES)**, a generative model of environmental sounds controlled through
an atlas of its data. Two modes:

| Mode | What it is | Needs | Status |
|---|---|---|---|
| **Live** | Real-time generation: drop semantic sources on a plane, move a point between them, and the sound follows. Atlas, effects, meter and recorder. | An NVIDIA GPU that keeps up with the sound | working |
| **Score** | Offline generation on a timeline: arrange sources over time, render, listen, export. | Any GPU (it does not run in real time) | under construction |

`python app.py` opens the start page, where you choose one. `python app_live.py` and `python app_score.py` open a mode directly.
Online: [huggingface.co/spaces/cordutie/SCAPES-demo](https://huggingface.co/spaces/cordutie/SCAPES-demo) (Live needs a GPU of its
own: on a shared one it stops suddenly, so run it locally).

## Run it

1. Clone this repository (and, to work on the model too, SCAPES next to it).
2. Make an environment and install: `python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
   (SpectroStream models also need `pip install --no-deps magenta-rt==2.0.3`).
3. Get models into `models/`: `python app.py --fetch` downloads them from the Hugging Face repository
   [cordutie/SCAPES-models](https://huggingface.co/cordutie/SCAPES-models), or copy a folder yourself (see below).
4. `python app.py`, then open http://127.0.0.1:7860.

Without models, Live says so and where to get them; the start page and Score still open.

## Models

A model is a folder of `models/` (gitignored), the same shape as a folder of the Hugging Face repository:
`<name>/checkpoints/inference.gin`, `best_*.pt` (or `last_*.pt`), `latent_stats.pt`, and `<name>/atlas.npz` (the atlas that dataprep makes
with `GUI = True`). Make one from a trained model with `python tools/add_model.py <build>/models/<size>_mem<ms>`.
The Live page has a menu to switch models; the last one used starts next time.

## Layout

| Where | What |
|---|---|
| `app.py`, `app_live.py`, `app_score.py` | the three ways to start (a mode is a page mounted on the same server) |
| `studio/` | Python: `config.py` (every number), `models.py`, `hub.py`, `server.py`, `atlas_model.py`, `hull.py` |
| `studio/live/` | Live: the generator thread (`engine.py`), the model session, the audio line (`transport.py`), the page's server functions |
| `studio/score/` | Score (a placeholder page for now) |
| `web/shared/` | what every page uses: the look (`theme.css`, `theme.js`), knobs, the (i) texts (`info.js`), the effects |
| `web/live/` | the Live page: one file per panel in `blocks/`, the audio player in `audio/`, the grid in `layout.html` |
| `web/selector/`, `web/score/` | the start page and the Score placeholder |
| `tests/` | `test_live_api.py` (pytest, no GPU), and browser checks: `studio_check.py` (start page, modes, warning), `ui_check.py`, `browser_check.py`, `model_menu_check.py`, `engine_check.py` |

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
