"""SCAPES Studio, Live mode (real time). Run: python app_live.py [--model NAME]   then open http://127.0.0.1:7860
The models are the folders of models/ (see studio/models.py; add one with tools/add_model.py); the page has a menu to switch."""
import os

# SpectroStream runs on jax next to torch: jax takes GPU memory as it needs it, not all of it at start
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import studio.scapes_path  # noqa: F401,E402  (before SCAPES)
from studio import config  # noqa: E402
from studio.hub import fetch_models  # noqa: E402
from studio.live.page import make_manager, mount_live  # noqa: E402
from studio.server import base_app, parse_args, serve  # noqa: E402


def main():
    args = parse_args("SCAPES Studio: Live mode")
    if args.fetch or config.ON_HUGGING_FACE:
        fetch_models(args.models_dir)
    manager = make_manager(args.models_dir, args.checkpoint)
    first = args.model or manager.default()
    if first:
        manager.load(first)
        print(f"Model {manager.session.name} ready: open http://{args.host}:{args.port}")
    else:
        print(f"No models in {args.models_dir}: the page will say how to get them (python app_live.py --fetch)")
    app = base_app()
    mount_live(app, manager, "/")
    serve(app, args)


if __name__ == "__main__":
    main()
