"""SCAPES Studio: the start page, where you choose a mode. Run: python app.py   then open http://127.0.0.1:7860
Live (real time) is at /live and Score (offline, under construction) at /score. To open one mode directly: python app_live.py,
python app_score.py. A model is loaded only when Live is opened. On a Hugging Face Space the models are downloaded at start."""
import os

os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import studio.scapes_path  # noqa: F401,E402  (before SCAPES)
from studio import config  # noqa: E402
from studio.hub import fetch_models  # noqa: E402
from studio.live.page import make_manager, mount_live  # noqa: E402
from studio.score.page import mount_score  # noqa: E402
from studio.server import add_html_route, base_app, parse_args, serve  # noqa: E402


def build_app(models_dir, checkpoint="best"):
    app = base_app()
    add_html_route(app, "/", "selector/index.html", {"{{ON_HF}}": "true" if config.ON_HUGGING_FACE else "false"})
    mount_score(app, "/score")
    mount_live(app, make_manager(models_dir, checkpoint), "/live")        # last: Gradio answers everything under /live
    return app


def main():
    args = parse_args("SCAPES Studio")
    if args.fetch or config.ON_HUGGING_FACE:
        fetch_models(args.models_dir)
    serve(build_app(args.models_dir, args.checkpoint), args)


if __name__ == "__main__":
    main()
