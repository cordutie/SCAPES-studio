"""The Score page in headless Chromium: the three blocks at 1920 x 1080, the sources (click plays their audio, drag places them), the mix of the
playground, and the timeline (drop the point, move, resize, remove). Starts its own server. Run: python tests/score_check.py [model_folder]"""
import glob, os, subprocess, sys, tempfile, time, urllib.request, urllib.error
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
sys.path.insert(0, str(root))
import numpy as np
from studio.score.takes import Takes
takes = Takes(tmp / "takes")
take = takes.add(np.sin(np.linspace(0, 440 * 2 * np.pi, 44100, dtype=np.float32))[:, None] * 0.2, 44100,
                 {"model": "m1", "nfe": 12, "cfg": 2.5, "seed": 7, "clips": []})
(tmp / "models").mkdir()
(tmp / "models" / "m1").symlink_to(real)
(tmp / "empty").mkdir()
port = 7886
srv = subprocess.Popen([sys.executable, str(root / "app_score.py"), "--models-dir", str(tmp / "models"), "--port", str(port)], cwd=root,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(os.environ, SCAPES_STUDIO_TAKES=str(tmp / "takes")))
srv2 = subprocess.Popen([sys.executable, str(root / "app_score.py"), "--models-dir", str(tmp / "empty"), "--port", str(port + 1)], cwd=root,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    for p_ in (port, port + 1):
        for _ in range(90):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{p_}/"); break
            except Exception:
                time.sleep(1)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{port}/")
        pg.wait_for_function("window.__score && window.__score.timeline", timeout=90000)
        S = lambda expr: pg.evaluate(f"(() => {{ const S = window.__score.S; return ({expr}); }})()")

        # the page: three blocks, centred, inside 1920 x 1080
        pg.wait_for_timeout(800)                       # Gradio is still settling its own padding for a moment after the page loads
        box = pg.locator("#demo").bounding_box()
        check(all(pg.locator(f"[data-block={n}]").count() == 1 for n in ("sources", "takes", "playground", "timeline", "settings", "log")),
              "the blocks: sources (and takes), playground, timeline, model, log")
        check(box["height"] <= 1080 and box["width"] <= 1920, f"the page fits 1920 x 1080 ({box['width']:.0f} x {box['height']:.0f})")
        check(abs(box["x"] - (1920 - box["x"] - box["width"])) < 2, f"it is centred horizontally (left {box['x']:.0f}, right {1920 - box['x'] - box['width']:.0f})")
        tl = pg.locator("[data-block=timeline]").bounding_box()
        check(0.17 < tl["height"] / 1080 < 0.23, f"the timeline is about a fifth of the screen ({tl['height'] / 1080:.0%})")
        # where they are: the timeline under the sources, the model panel and the log under the playground, the timeline as wide as the sources
        r = lambda n: pg.locator(f"[data-block={n}]").bounding_box()
        check(r("timeline")["y"] > r("sources")["y"] + r("sources")["height"] - 2 and abs(r("timeline")["width"] - r("sources")["width"]) < 2,
              "the timeline is under the sources and as wide as them")
        check(r("settings")["y"] == r("log")["y"] == r("timeline")["y"] and r("settings")["x"] >= r("playground")["x"] - 1
              and abs(r("settings")["x"] + r("settings")["width"] + 8 - r("log")["x"]) < 2 and abs(r("settings")["height"] - r("timeline")["height"]) < 2,
              "the model panel and the log are under the playground, as high as the timeline")
        n = pg.locator(".src").count()
        check(n == S("S.sources.length") and n > 0, f"one button per representative ({n})")

        # click a source: its audio is fetched and it shows as playing
        with pg.expect_response(lambda r: r.url.endswith(".mp3")) as resp:
            pg.locator(".src").nth(0).click()
        check(resp.value.status in (200, 206) and "audio" in resp.value.headers.get("content-type", ""), f"a click fetches the audio of the source ({resp.value.status})")
        check("playing" in (pg.locator(".src").nth(0).get_attribute("class") or ""), "...and marks it as playing")

        # drag three sources onto the playground
        c = pg.locator("[data-block=playground] canvas").bounding_box()
        spots = [(0.25, 0.7), (0.75, 0.7), (0.5, 0.2)]
        for k, (fx, fy) in enumerate(spots):
            bb = pg.locator(".src").nth(k * 4).bounding_box()
            pg.mouse.move(bb["x"] + 40, bb["y"] + 15); pg.mouse.down()
            pg.mouse.move(c["x"] + c["width"] * fx, c["y"] + c["height"] * fy, steps=6); pg.mouse.up()
            pg.wait_for_timeout(250)
        check(S("S.dots.filter(d => d).length") == 3, "three dragged sources are three dots")
        check(pg.locator(".src.placed").count() == 3, "the placed sources are marked")

        # the point: a press between them mixes the three
        pg.mouse.click(c["x"] + c["width"] * 0.5, c["y"] + c["height"] * 0.5); pg.wait_for_timeout(500)
        sel = S("S.point && S.point.sel")
        check(sel and len(sel["idx"]) == 3 and abs(sum(sel["lam"]) - 1) < 1e-6, f"the point inside the triangle mixes three sources ({sel and [round(w, 2) for w in sel['lam']]})")
        # carrying the point onto a dot makes it that source alone (a press on a dot would grab the dot instead)
        pt = S("S.point.c")
        pg.mouse.move(c["x"] + (pt[0] + 1) / 2 * c["width"], c["y"] + (1 - pt[1]) / 2 * c["height"]); pg.mouse.down()
        pg.mouse.move(c["x"] + c["width"] * 0.25, c["y"] + c["height"] * 0.7, steps=8); pg.mouse.up(); pg.wait_for_timeout(500)
        sel = S("S.point && S.point.sel")
        check(sel and max(sel["lam"]) > 0.9, f"on a dot it is that source alone ({sel and [round(w, 2) for w in sel['lam']]})")
        pg.mouse.click(c["x"] + c["width"] * 0.5, c["y"] + c["height"] * 0.55); pg.wait_for_timeout(500)

        # drag the point out of the playground onto the timeline
        pt = S("S.point.c")
        px = c["x"] + (pt[0] + 1) / 2 * c["width"]; py = c["y"] + (1 - pt[1]) / 2 * c["height"]
        tl_track = pg.locator("[data-block=timeline] .tl-track").bounding_box()
        pg.mouse.move(px, py); pg.mouse.down(); pg.mouse.move(px, py + 30, steps=3)
        pg.mouse.move(tl_track["x"] + 300, tl_track["y"] + 60, steps=12)
        check(pg.locator(".chip").count() == 1 and pg.locator(".drop-mark").is_visible(), "carrying the point shows a chip and a mark on the timeline")
        pg.mouse.up(); pg.wait_for_timeout(300)
        clips = S("S.clips")
        check(len(clips) == 1 and abs(clips[0]["start"] - 300 / S("S.pps")) < 0.2, f"the drop makes a clip at the place it was dropped ({clips and round(clips[0]['start'], 2)} s)")
        bg = pg.locator(".clip").first.evaluate("e => e.style.background")
        check(len(clips[0]["idx"]) == 3 and "gradient" in bg, f"the clip keeps the mix and shows its colours ({len(clips[0]['idx'])} sources, {bg[:40]})")
        check(pg.locator(".chip").count() == 0, "the chip is gone")

        # dropping on the clip goes after it; a drop elsewhere than the timeline does nothing
        pg.mouse.move(px, py); pg.mouse.down(); pg.mouse.move(px, py + 30, steps=3)
        pg.mouse.move(tl_track["x"] + 320, tl_track["y"] + 60, steps=12); pg.mouse.up(); pg.wait_for_timeout(300)
        clips = sorted(S("S.clips"), key=lambda k: k["start"])
        check(len(clips) == 2 and clips[1]["start"] >= clips[0]["start"] + clips[0]["dur"] - 1e-6, "a second clip never overlaps the first")
        pg.mouse.move(px, py); pg.mouse.down(); pg.mouse.move(px, py + 30, steps=3); pg.mouse.move(900, 300, steps=8); pg.mouse.up(); pg.wait_for_timeout(200)
        check(len(S("S.clips")) == 2 and pg.locator(".chip").count() == 0, "releasing the point away from the timeline does nothing")

        # move and resize a clip
        e = pg.locator(".clip").first.bounding_box(); start0, dur0 = S("S.clips[0].start"), S("S.clips[0].dur")
        pg.mouse.move(e["x"] + 40, e["y"] + 40); pg.mouse.down(); pg.mouse.move(e["x"] - 120, e["y"] + 40, steps=6); pg.mouse.up(); pg.wait_for_timeout(200)
        first = sorted(S("S.clips"), key=lambda k: k["start"])[0]
        check(first["start"] < start0 or first["start"] == 0, f"a clip can be dragged ({start0:.2f} -> {first['start']:.2f})")
        e = pg.locator(".clip").first.bounding_box()
        pg.mouse.move(e["x"] + e["width"] - 3, e["y"] + 40); pg.mouse.down(); pg.mouse.move(e["x"] + e["width"] + 25, e["y"] + 40, steps=5); pg.mouse.up(); pg.wait_for_timeout(200)
        first2 = sorted(S("S.clips"), key=lambda k: k["start"])[0]
        check(first2["dur"] != first["dur"], f"its right edge changes its length ({first['dur']:.2f} -> {first2['dur']:.2f})")
        ends = sorted(S("S.clips"), key=lambda k: k["start"])
        check(all(ends[i]["start"] + ends[i]["dur"] <= ends[i + 1]["start"] + 1e-6 for i in range(len(ends) - 1)), "clips still do not overlap")

        # + Timeline appends, double-click removes, Clear empties
        pg.locator("[data-block=playground] [data-ref=add]").click(); pg.wait_for_timeout(200)
        check(len(S("S.clips")) == 3, "+ Timeline adds a clip")
        pg.locator(".clip").nth(2).dblclick(); pg.wait_for_timeout(200)
        check(len(S("S.clips")) == 2, "double-click removes a clip")
        pg.locator("[data-block=timeline] [data-ref=clear]").click(); pg.wait_for_timeout(200)
        check(len(S("S.clips")) == 0, "Clear empties the timeline")

        # a dot is removed with a double-click, and Clear empties the playground
        c3 = pg.locator("[data-block=playground] canvas").bounding_box()
        pg.mouse.dblclick(c3["x"] + c3["width"] * 0.5, c3["y"] + c3["height"] * 0.2); pg.wait_for_timeout(300)
        check(S("S.dots.filter(d => d).length") == 2, "double-click removes a dot")
        pg.locator("[data-block=playground] [data-ref=clear]").click(); pg.wait_for_timeout(200)
        check(S("S.dots.filter(d => d).length") == 0 and S("S.point") is None, "Clear empties the playground")

        # the model panel: NFE, CFG, seed, the model menu; Generate waits for the next step
        nfe0 = S("S.gen.nfe")
        k = pg.locator("[data-block=settings] .knob").first.locator("svg").bounding_box()
        pg.mouse.move(k["x"] + 20, k["y"] + 20); pg.mouse.down(); pg.mouse.move(k["x"] + 20, k["y"] - 30, steps=5); pg.mouse.up(); pg.wait_for_timeout(200)
        check(S("S.gen.nfe") != nfe0, f"the NFE knob changes the NFE ({nfe0} -> {S('S.gen.nfe')})")
        pg.fill("[data-block=settings] [data-ref=seed]", "123"); pg.locator("[data-block=settings] [data-ref=seed]").press("Enter"); pg.wait_for_timeout(100)
        pg.locator("[data-block=settings] [data-ref=dice]").click()
        check(S("S.gen.seed") != 123 and 0 <= S("S.gen.seed") <= 999999, f"the die picks a new seed ({S('S.gen.seed')})")
        check(pg.locator("[data-block=settings] [data-ref=generate]").is_disabled(), "Generate is off until there is a generator")
        pg.locator("[data-block=settings] [data-ref=modelbtn]").click(); pg.wait_for_timeout(200)
        check(pg.locator(".menu button").count() == 1 and "current" in pg.locator(".menu button").first.get_attribute("class"), "the model menu lists the model")
        pg.mouse.click(5, 5); pg.wait_for_timeout(100)
        check(pg.locator(".menu").count() == 0, "a click away closes it")
        check("model m1" in pg.locator("[data-block=log] .lines").inner_text(), "the log says which model is shown")

        # the takes: a tab in the place of the sources
        check(not pg.locator("[data-block=takes]").is_visible() and pg.locator("[data-block=sources]").is_visible(), "the sources show first")
        pg.locator("[data-block=sources] [data-tab=takes]").click(); pg.wait_for_timeout(200)
        check(pg.locator("[data-block=takes]").is_visible() and not pg.locator("[data-block=sources]").is_visible(), "the Takes tab replaces the sources")
        check(pg.locator(".take").count() == 1 and "NFE 12" in pg.locator(".take").inner_text() and "seed 7" in pg.locator(".take").inner_text(), "a take shows what made it")
        check("Takes (1)" in pg.locator("[data-block=takes] [data-tab=takes]").inner_text(), "the tab counts the takes")
        link = pg.locator(".take a.tdown")
        check(link.get_attribute("href").endswith(take["id"] + ".wav") and link.get_attribute("download") == take["id"] + ".wav", "each take has its own download button")
        r_ = urllib.request.urlopen(f"http://127.0.0.1:{port}/takes/{take['id']}.wav")
        check(r_.status == 200 and r_.headers["content-type"] == "audio/wav" and r_.read(4) == b"RIFF", "the takes route serves the wav")
        pg.locator(".take .tplay").click(); pg.wait_for_timeout(300)
        check("playing" in pg.locator(".take").get_attribute("class") and pg.locator(".take .tplay").inner_text() == "■", "play marks the take and turns into stop")
        pg.locator(".take .tplay").click(); pg.wait_for_timeout(200)
        check("playing" not in pg.locator(".take").get_attribute("class"), "a second press stops it")
        pg.locator("[data-block=takes] [data-tab=sources]").click(); pg.wait_for_timeout(100)
        check(pg.locator("[data-block=sources]").is_visible(), "the Sources tab brings the sources back")
        pg.locator("[data-block=sources] [data-tab=takes]").click(); pg.wait_for_timeout(100)
        pg.locator(".take .tdel").click(); pg.wait_for_timeout(400)
        check(pg.locator(".take").count() == 0 and "Nothing generated yet" in pg.locator("[data-block=takes]").inner_text()
              and not (tmp / "takes" / (take["id"] + ".wav")).exists() and not (tmp / "takes" / (take["id"] + ".json")).exists(),
              "removing a take removes its files")

        # the snippets route: only the audio of the model
        def status(url):
            try:
                return urllib.request.urlopen(url).status
            except urllib.error.HTTPError as ex:
                return ex.code
        base = f"http://127.0.0.1:{port}/snippets"
        check(status(f"{base}/m1/000.mp3") == 200, "the snippet route serves a snippet")
        check(status(f"http://127.0.0.1:{port}/takes/../atlas.wav") == 404 and status(f"http://127.0.0.1:{port}/takes/take-x.wav") == 404, "the takes route serves only takes")
        check(status(f"{base}/m1/abc.mp3") == 404 and status(f"{base}/nope/000.mp3") == 404 and status(f"{base}/m1/..%2Fatlas.npz") == 404,
              "...and nothing else")
        check(not errors, f"no page errors {errors}")

        pg2 = b.new_page(viewport={"width": 1920, "height": 1080})
        pg2.goto(f"http://127.0.0.1:{port + 1}/"); pg2.wait_for_selector(".notice", timeout=60000)
        check("No models yet" in pg2.inner_text(".notice"), "with no models the page says where to get them")
        b.close()
finally:
    srv.terminate(); srv2.terminate()
print("\nPROBLEMS:", problems or "none")
