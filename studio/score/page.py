"""The Score page: one gr.HTML whose markup is web/score/layout.html and whose script is web/score/main.js (the same way as Live), and the
route that serves the audio snippets of the sources. Nothing about the look or the behaviour of the page is written in Python."""
import re

import gradio as gr
from fastapi import HTTPException
from fastapi.responses import FileResponse

from studio import config
from studio.score.library import Library
from studio.score.score_api import SNIPPET, make_functions
from studio.score.takes import ID, Takes

ON_LOAD = "(async () => { const m = await import('/web/score/main.js?v=' + Date.now()); await m.start({element, server}); })();"


def build_page(server_functions):
    layout = (config.WEB_DIR / "score" / "layout.html").read_text()
    with gr.Blocks(title="SCAPES Studio · Score") as page:
        gr.HTML(value="", html_template=layout, js_on_load=ON_LOAD, server_functions=server_functions)
    return page


# Puts the Score mode on `app` at `path` ("/" alone, "/score" in the combined app): the snippets route, then the page (last: Gradio answers
# everything under its path)
def mount_score(app, library: Library, path="/", takes: Takes | None = None):
    takes = takes or Takes(config.TAKES_DIR)
    prefix = "" if path == "/" else path.rstrip("/")

    @app.get(prefix + "/snippets/{model}/{file}")
    def snippet(model: str, file: str):
        if not SNIPPET.match(file) or not re.match(r"^[A-Za-z0-9_.-]+$", model) or model.startswith("."):
            raise HTTPException(404)
        f = library.dir / model / "snippets" / file
        if not f.is_file():
            raise HTTPException(404)
        return FileResponse(f, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})

    @app.get(prefix + "/takes/{take_id}.wav")
    def take(take_id: str):
        if not ID.match(take_id) or not takes.path(take_id).is_file():
            raise HTTPException(404)
        return FileResponse(takes.path(take_id), media_type="audio/wav", headers={"Cache-Control": "no-store"},
                            filename=f"{take_id}.wav")

    return gr.mount_gradio_app(app, build_page(make_functions(library, takes, prefix)), path=path, ssr_mode=False)
