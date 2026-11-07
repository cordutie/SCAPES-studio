"""What the apps share to serve a page: the static files of web/ (always at /web, so a page finds its files wherever it is mounted)
and the way the apps are started (python app.py, app_live.py, app_score.py)."""
import argparse

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from studio import config


# static files that the browser never keeps: an edit to web/ shows on the next reload
class _Fresh(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


# A FastAPI app that serves /web
def base_app():
    app = FastAPI()
    app.mount("/web", _Fresh(directory=str(config.WEB_DIR)), name="web")
    return app


# A route that answers with an HTML file of web/ (some words of it replaced: {"{{NAME}}": "text"})
def add_html_route(app, path, file, replace=None):
    @app.get(path, response_class=HTMLResponse)
    def page():
        html = (config.WEB_DIR / file).read_text()
        for key, value in (replace or {}).items():
            html = html.replace(key, value)
        return html


def parse_args(description, models=True):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--host", default=config.HOST)
    p.add_argument("--port", type=int, default=config.PORT)
    if models:
        p.add_argument("--model", default=config.MODEL_DIR, help="the model to start with: a name in the models folder, or a path "
                       "(default: the one used last time)")
        p.add_argument("--models-dir", default=str(config.MODELS_DIR), help="the folder of models")
        p.add_argument("--checkpoint", default="best", help="best | last")
        p.add_argument("--fetch", action="store_true", help=f"download the models of {config.MODELS_REPO} first (always done on a Hugging Face Space)")
    return p.parse_args()


def serve(app, args):
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
