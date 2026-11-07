"""The Score mode (offline generation on a timeline). Under construction: for now its page only says so (web/score/index.html)."""
from studio.server import add_html_route


# Puts the Score mode on `app` at `path` ("/" alone, "/score" in the combined app)
def mount_score(app, path="/"):
    add_html_route(app, path, "score/index.html")
    if path != "/":
        add_html_route(app, path.rstrip("/") + "/", "score/index.html")
