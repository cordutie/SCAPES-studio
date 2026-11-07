"""SCAPES Studio, Score mode (offline, on a timeline). Under construction. Run: python app_score.py   then open http://127.0.0.1:7860"""
from studio.score.page import mount_score
from studio.server import base_app, parse_args, serve


def main():
    args = parse_args("SCAPES Studio: Score mode", models=False)
    app = base_app()
    mount_score(app, "/")
    serve(app, args)


if __name__ == "__main__":
    main()
