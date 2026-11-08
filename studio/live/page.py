"""The Live page: one gr.HTML whose markup is web/live/layout.html and whose script is web/live/main.js (an ES module, served from
/web). Nothing about the look or the behaviour of the page is written in Python."""
import gradio as gr

from studio import config
from studio.live.live_api import make_functions
from studio.live.session import Session
from studio.live.transport import add_audio_route
from studio.models import ModelManager

# runs once when the page loads: import the module (a new URL each time, so an edited file is always reloaded)
ON_LOAD = "(async () => { const m = await import('/web/live/main.js?v=' + Date.now()); await m.start({element, server}); })();"


def build_page(server_functions):
    layout = (config.WEB_DIR / "live" / "layout.html").read_text()
    with gr.Blocks(title="SCAPES Studio · Live") as page:
        gr.HTML(value="", html_template=layout, js_on_load=ON_LOAD, server_functions=server_functions)
    return page


def make_manager(models_dir, checkpoint="best"):
    return ModelManager(models_dir, Session, checkpoint=checkpoint)


# Puts the Live mode on `app` at `path` ("/" alone, "/live" in the combined app): its audio line and its page.
# The page is added last: Gradio answers everything under its path.
# ssr_mode=False: on a Hugging Face Space Gradio turns on server-side rendering, which starts a Node server on GRADIO_SERVER_PORT (7860),
# the port that this server needs. The page is drawn in the browser anyway.
def mount_live(app, manager, path="/"):
    prefix = "" if path == "/" else path.rstrip("/")
    add_audio_route(app, manager, prefix)
    return gr.mount_gradio_app(app, build_page(make_functions(manager)), path=path, ssr_mode=False)
