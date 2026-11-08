"""The combined app (python app.py) in headless Chromium: the start page with its two modes, the warning on Hugging Face, the Score
placeholder, Live under /live (it plays through /live/ws/audio), and Live with no models. Starts its own servers.
Run: python tests/studio_check.py [real_model_folder]"""
import glob, os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent
real = Path(sys.argv[1] if len(sys.argv) > 1 else sorted((root / "models").glob("*music2latent*tiny*"))[0]).resolve()
chrome = glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome"))[0]
problems = []


def check(cond, text):
    print(("ok   " if cond else "FAIL ") + text)
    if not cond:
        problems.append(text)


def start(port, models_dir, env=None):
    p = subprocess.Popen([sys.executable, str(root / "app.py"), "--models-dir", str(models_dir), "--port", str(port)], cwd=root,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(os.environ, **(env or {})))
    for _ in range(90):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/"); return p
        except Exception:
            time.sleep(1)
    raise RuntimeError("server did not start")


tmp = Path(tempfile.mkdtemp())
(tmp / "models" / "m1").mkdir(parents=True)
for f in [x for x in real.rglob("*") if x.is_file()]:
    (tmp / "models" / "m1" / f.relative_to(real)).parent.mkdir(parents=True, exist_ok=True)
    (tmp / "models" / "m1" / f.relative_to(real)).symlink_to(f)
(tmp / "empty").mkdir()
servers = [start(7881, tmp / "models"), start(7882, tmp / "models", {"SPACE_ID": "x/y"}), start(7883, tmp / "empty")]
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
        errors = []

        def new(url):
            pg = b.new_page(viewport={"width": 1920, "height": 1080})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(url); return pg

        # the start page, locally: Live goes straight to /live/
        pg = new("http://127.0.0.1:7881/")
        check("Live" in pg.inner_text("#live") and "Score" in pg.inner_text("#score"), "the start page shows both modes")
        check(not pg.locator("#warn").is_visible(), "no warning is open")
        pg.click("#live"); pg.wait_for_url("**/live/", timeout=10000)
        pg.wait_for_function("window.__demo && window.__demo.player && window.__demo.player.connected()", timeout=90000)
        check(True, "Live opens under /live and its audio line connects")
        b0 = pg.locator("[data-block=clusters] .blocks button").nth(0).bounding_box(); c = pg.locator("[data-block=plane] canvas").bounding_box()
        pg.mouse.move(b0["x"] + 40, b0["y"] + 20); pg.mouse.down(); pg.mouse.move(c["x"] + c["width"] / 2, c["y"] + c["height"] / 2, steps=5); pg.mouse.up()
        pg.wait_for_function("window.__demo.S.lastLive && window.__demo.S.lastLive.dec3", timeout=20000)
        pg.click("[data-ref=play]")
        pg.wait_for_function("document.querySelector('[data-block=generation] .m-log .live').innerText.includes('Running')", timeout=20000)
        time.sleep(2)
        pg.wait_for_function("(() => { const v = window.__demo.player.levels(); return v.l > -60 || v.r > -60; })()", timeout=8000)
        check(True, "Live makes sound under /live")
        pg.screenshot(path=str(tmp / "live.png"))
        # score placeholder
        pg = new("http://127.0.0.1:7881/score/")
        check("under construction" in pg.inner_text("body").lower(), "/score says it is under construction")
        # on Hugging Face: Live asks first
        pg = new("http://127.0.0.1:7882/")
        pg.click("#live")
        check(pg.locator("#warn").is_visible() and "stop suddenly" in pg.inner_text("#warn"), "on Hugging Face the Live card opens the warning")
        check(pg.url.endswith(":7882/"), "...and does not leave the page")
        pg.screenshot(path=str(tmp / "warn.png"))
        pg.click("#back"); check(not pg.locator("#warn").is_visible(), "Back closes it")
        pg.click("#live"); pg.click("#go"); pg.wait_for_url("**/live/", timeout=10000)
        check(True, "Open Live anyway goes on")
        # no models
        pg = new("http://127.0.0.1:7883/live/")
        pg.wait_for_selector(".notice", timeout=30000)
        check("No models yet" in pg.inner_text(".notice") and "SCAPES-models" in pg.inner_text(".notice"), "Live with no models says where to get them")
        check(not errors, f"no page errors {errors[:3]}")
        b.close()
finally:
    for s in servers:
        s.terminate()
        s.wait(timeout=20)
print("\nPROBLEMS:", problems if problems else "none", "· screenshots in", tmp)
sys.exit(1 if problems else 0)
