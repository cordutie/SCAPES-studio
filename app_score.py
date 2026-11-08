"""SCAPES Studio, Score mode (offline, on a timeline). Run: python app_score.py   then open http://127.0.0.1:7860
It shows the models of models/ that have the snippets of their sources (see studio/score/library.py)."""
from studio import config
from studio.hub import fetch_models
from studio.score.library import Library
from studio.score.page import mount_score
from studio.server import base_app, parse_args, serve


def main():
    args = parse_args("SCAPES Studio: Score mode")
    if args.fetch or config.ON_HUGGING_FACE:
        fetch_models(args.models_dir)
    app = base_app()
    mount_score(app, Library(args.models_dir), "/")
    serve(app, args)


if __name__ == "__main__":
    main()
