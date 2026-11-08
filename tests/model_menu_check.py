"""The model menu, in the real page: starts its own server on a folder with two models (links to the files of a real one), opens the menu,
switches, and checks that the page reloads on the other model and still plays; a name that is not a model is refused and the
current model stays. Run: python tests/model_menu_check.py [real_model_folder]"""
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

tmp = Path(tempfile.mkdtemp())
for name in ("alpha", "beta"):                    # two real folders whose files are links to the real model
    for f in [p for p in real.rglob("*") if p.is_file()]:
        (tmp / name / f.relative_to(real)).parent.mkdir(parents=True, exist_ok=True)
        (tmp / name / f.relative_to(real)).symlink_to(f)
(tmp / "not_a_model").mkdir()
port = 7871
server = subprocess.Popen([sys.executable, str(root / "app_live.py"), "--models-dir", str(tmp), "--port", str(port)],
                          cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    for _ in range(90):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/"); break
        except Exception:
            time.sleep(1)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chrome)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/")
        page.wait_for_function("window.__demo && window.__demo.player && window.__demo.player.connected()", timeout=60000)
        btn = page.locator("[data-ref=modelbtn]")
        first = btn.inner_text(); print("button:", first)
        check("alpha" in first, "the first model (alphabetical) is loaded")
        btn.click()
        items = page.locator("[data-block=generation] .menu button")
        page.wait_for_timeout(1500)
        check(items.count() == 2, f"the menu lists the two models and not the folder that is not one ({items.count()})")
        check("current" in (items.nth(0).get_attribute("class") or ""), "the loaded model is marked")
        page.screenshot(path=str(tmp / "menu.png"))
        page.click("body", position={"x": 5, "y": 5})
        check(page.locator("[data-ref=menu]").is_hidden(), "a click outside closes the menu")

        refused = page.evaluate("window.__demo.api.loadModel('nope')")
        check(refused["ok"] is False and "not a model folder" in refused["error"], f"an unknown model is refused: {refused['error'][:60]}")
        check("alpha" in btn.inner_text(), "...and the current model stays")

        btn.click(); page.locator("[data-block=generation] .menu button").nth(1).click()
        page.wait_for_function("document.querySelector('[data-ref=modelbtn]') && document.querySelector('[data-ref=modelbtn]').innerText.includes('beta')", timeout=90000)
        page.wait_for_function("window.__demo && window.__demo.player && window.__demo.player.connected()", timeout=60000)
        check("beta" in btn.inner_text(), "after the switch the page reloads on the other model")
        check((tmp / ".last").read_text() == "beta", "the choice is remembered for the next start")

        # and it plays
        b = page.locator("[data-block=clusters] .blocks button").nth(0).bounding_box()
        c = page.locator("[data-block=plane] canvas").bounding_box()
        page.mouse.move(b["x"] + 40, b["y"] + 20); page.mouse.down()
        page.mouse.move(c["x"] + c["width"] / 2, c["y"] + c["height"] / 2, steps=5); page.mouse.up()
        page.wait_for_function("window.__demo.S.lastLive && window.__demo.S.lastLive.dec3", timeout=20000)
        page.click("[data-ref=play]")
        page.wait_for_function("document.querySelector('[data-block=generation] .m-log .live').innerText.includes('Running')", timeout=20000)
        time.sleep(2)
        page.wait_for_function("(() => { const v = window.__demo.player.levels(); return v.l > -60 || v.r > -60; })()", timeout=8000)
        check(True, "the new model makes sound")
        # switching while it plays stops it first
        btn.click(); page.locator("[data-block=generation] .menu button").nth(0).click()
        page.wait_for_function("document.querySelector('[data-ref=modelbtn]') && document.querySelector('[data-ref=modelbtn]').innerText.includes('alpha')", timeout=90000)
        page.wait_for_function("window.__demo && window.__demo.player && window.__demo.player.connected()", timeout=60000)
        check("Stopped" in page.inner_text("[data-block=generation] .m-log .live"), "switching while playing leaves the new model stopped")
        check(not errors, f"no page errors {errors[:3]}")
        browser.close()
finally:
    server.terminate(); server.wait(timeout=20)
print("\nPROBLEMS:", problems if problems else "none")
sys.exit(1 if problems else 0)
