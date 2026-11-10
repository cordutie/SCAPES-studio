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

        # the sources block has no model name any more (the model is in the model panel)
        check(pg.locator("[data-block=sources] .readout").count() == 0, "the sources panel does not show the model name")

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

        # control mode, as in Live: a press sets the point (the mix of the three), and a dot does not move
        pg.mouse.click(c["x"] + c["width"] * 0.5, c["y"] + c["height"] * 0.5); pg.wait_for_timeout(500)
        sel = S("S.point && S.point.sel")
        check(sel and len(sel["idx"]) == 3 and abs(sum(sel["lam"]) - 1) < 1e-6, f"the point inside the triangle mixes three sources ({sel and [round(w, 2) for w in sel['lam']]})")
        d0 = S("S.dots[0]") if S("S.dots[0]") else S("S.dots.find(d => d)")
        i0 = S("S.dots.findIndex(d => d)")
        at = lambda d: (c["x"] + (d[0] + 1) / 2 * c["width"], c["y"] + (1 - d[1]) / 2 * c["height"])
        x0, y0 = at(d0)
        pg.mouse.move(x0, y0); pg.mouse.down(); pg.mouse.move(x0 + 60, y0 + 40, steps=5); pg.mouse.up(); pg.wait_for_timeout(300)
        check(S(f"S.dots[{i0}]") == d0, "without Edit a press on a dot does not move it")
        # Edit moves dots
        pg.locator("[data-block=playground] [data-ref=edit]").click()
        pg.mouse.move(x0, y0); pg.mouse.down(); pg.mouse.move(x0 + 60, y0 + 40, steps=5); pg.mouse.up(); pg.wait_for_timeout(300)
        d1 = S(f"S.dots[{i0}]")
        check(d1 != d0, f"in Edit the dot moves ({d0[0]:.2f} -> {d1[0]:.2f})")
        pg.locator("[data-block=playground] [data-ref=edit]").click()
        pg.keyboard.down("Control"); pg.wait_for_timeout(100)
        check("on" in pg.locator("[data-block=playground] [data-ref=edit]").get_attribute("class"), "Ctrl holds Edit on")
        pg.keyboard.up("Control"); pg.wait_for_timeout(100)

        # a double-click on an empty place makes a free dot: the mix that was there
        n_src = S("S.sources.length")
        pg.mouse.dblclick(c["x"] + c["width"] * 0.5, c["y"] + c["height"] * 0.55); pg.wait_for_timeout(600)
        check(S("S.free.length") == 1 and S("S.dots.length") == n_src + 1 and S("S.dots[S.dots.length - 1] !== null"), "a double-click on an empty place makes a free dot")
        fc = S("S.free[0].comp")
        check(len(fc) == 3 and abs(sum(w for _, w in fc) - 1) < 1e-6, f"...that stands for the mix under it ({len(fc)} sources)")
        # it counts in the mixes: the point on it is that dot alone
        fx_, fy_ = at(S("S.dots[S.dots.length - 1]"))
        pg.mouse.click(fx_, fy_); pg.wait_for_timeout(500)
        check(S("S.point.sel.idx.includes(S.dots.length - 1)"), "the point can be on the free dot")

        # Score: the dots glow and can be dragged onto the timeline; without Score a press on a dot carries nothing
        tl_track = pg.locator("[data-block=timeline] .tl-track").bounding_box()
        pg.mouse.move(fx_, fy_); pg.mouse.down(); pg.mouse.move(fx_ + 10, fy_ + 40, steps=4)
        check(pg.locator(".chip").count() == 0, "without Score nothing is carried")
        pg.mouse.up()
        pg.locator("[data-block=playground] [data-ref=score]").click(); pg.wait_for_timeout(200)
        check("on" in pg.locator("[data-block=playground] [data-ref=score]").get_attribute("class"), "the Score button latches")
        pps = pg.evaluate("window.__score.timeline.scale()")
        pg.mouse.move(fx_, fy_); pg.mouse.down(); pg.mouse.move(fx_, fy_ + 30, steps=3)
        pg.mouse.move(tl_track["x"] + 300, tl_track["y"] + 60, steps=12)
        check(pg.locator(".chip").count() == 1 and pg.locator(".drop-mark").is_visible(), "carrying a dot shows a chip and a mark on the timeline")
        pg.mouse.up(); pg.wait_for_timeout(300)
        clips = S("S.clips")
        check(len(clips) == 1 and clips[0]["dur"] == 3, f"the drop makes a clip of 3 s ({clips and clips[0]['dur']})")
        check(clips and abs(clips[0]["start"] - (300 / pps)) < 0.5, f"...where it was dropped ({clips and round(clips[0]['start'], 2)} s)")
        check(clips and clips[0]["comp"] == fc, "...and it holds the embedding of the free dot")
        check(pg.locator(".chip").count() == 0, "the chip is gone")
        # the control point can be carried too, and a dot of a source is that source alone
        px_, py_ = at(S("S.point.c"))
        i1 = S("S.dots.findIndex(d => d)")
        sx, sy = at(S(f"S.dots[{i1}]"))
        pg.mouse.move(sx, sy); pg.mouse.down(); pg.mouse.move(sx, sy + 30, steps=3)
        pg.mouse.move(tl_track["x"] + 800, tl_track["y"] + 60, steps=12); pg.mouse.up(); pg.wait_for_timeout(300)
        clips = sorted(S("S.clips"), key=lambda k: k["start"])
        check(len(clips) == 2 and clips[1]["comp"] == [[i1, 1]], "a source's dot makes a clip of that source alone")
        pg.mouse.move(sx, sy); pg.mouse.down(); pg.mouse.move(sx, sy + 30, steps=3); pg.mouse.move(900, 300, steps=8); pg.mouse.up(); pg.wait_for_timeout(200)
        check(len(S("S.clips")) == 2 and pg.locator(".chip").count() == 0, "releasing away from the timeline does nothing")
        pg.locator("[data-block=playground] [data-ref=score]").click()
        pg.keyboard.down("Shift"); pg.wait_for_timeout(100)
        check("on" in pg.locator("[data-block=playground] [data-ref=score]").get_attribute("class"), "Shift holds Score on")
        pg.keyboard.up("Shift"); pg.wait_for_timeout(100)

        # a source straight onto the timeline: a clip of 3 s at the place, and the scale fits the piece by itself
        pps0 = pg.evaluate("window.__score.timeline.scale()")
        bb = pg.locator(".src").nth(20).bounding_box(); src_i = int(pg.locator(".src").nth(20).get_attribute("data-i"))
        pg.mouse.move(bb["x"] + 40, bb["y"] + 15); pg.mouse.down(); pg.mouse.move(tl_track["x"] + 1000, tl_track["y"] + 60, steps=10)
        check(pg.locator(".drop-mark").is_visible(), "carrying a source shows the mark on the timeline")
        pg.mouse.up(); pg.wait_for_timeout(300)
        clips = sorted(S("S.clips"), key=lambda k: k["start"])
        check(len(clips) == 3 and any(k["comp"] == [[src_i, 1]] and k["dur"] == 3 for k in clips), "dropping a source on the timeline makes a clip of it (3 s)")
        pps1 = pg.evaluate("window.__score.timeline.scale()")
        sc = pg.locator("[data-block=timeline] .tl-scroll").evaluate("e => [e.scrollWidth, e.clientWidth]")
        check(sc[0] <= sc[1] + 1, f"the timeline fits its width by itself, with no scrolling ({sc})")
        check(pg.locator(".interp").count() == 2, "a symbol of interpolation between every pair of clips (2)")
        check(all(clips[i]["start"] + clips[i]["dur"] <= clips[i + 1]["start"] + 1e-6 for i in range(2)), "clips do not overlap")
        on_clip = tl_track["x"] + clips[0]["start"] * pps1 + 20
        pg.mouse.move(bb["x"] + 40, bb["y"] + 15); pg.mouse.down(); pg.mouse.move(on_clip, tl_track["y"] + 60, steps=10); pg.mouse.up(); pg.wait_for_timeout(300)
        clips = sorted(S("S.clips"), key=lambda k: k["start"])
        check(len(clips) == 4 and all(clips[i]["start"] + clips[i]["dur"] <= clips[i + 1]["start"] + 1e-6 for i in range(3)), "a drop on a clip goes after it, never over it")
        pps2 = pg.evaluate("window.__score.timeline.scale()")
        check(pps2 < pps0, f"the scale shrinks as the piece grows ({pps0:.0f} -> {pps2:.0f} px/s)")

        # move and resize a clip
        e = pg.locator(".clip").first.bounding_box(); start0 = S("S.clips[0].start")
        pg.mouse.move(e["x"] + 40, e["y"] + 40); pg.mouse.down(); pg.mouse.move(e["x"] - 60, e["y"] + 40, steps=6); pg.mouse.up(); pg.wait_for_timeout(200)
        first = sorted(S("S.clips"), key=lambda k: k["start"])[0]
        check(first["start"] < start0 or first["start"] == 0, f"a clip can be dragged ({start0:.2f} -> {first['start']:.2f})")
        e = pg.locator(".clip").first.bounding_box()
        pg.mouse.move(e["x"] + e["width"] - 3, e["y"] + 40); pg.mouse.down(); pg.mouse.move(e["x"] + e["width"] + 25, e["y"] + 40, steps=5); pg.mouse.up(); pg.wait_for_timeout(200)
        first2 = sorted(S("S.clips"), key=lambda k: k["start"])[0]
        check(first2["dur"] != first["dur"], f"its right edge changes its length ({first['dur']:.2f} -> {first2['dur']:.2f})")
        ends = sorted(S("S.clips"), key=lambda k: k["start"])
        check(all(ends[i]["start"] + ends[i]["dur"] <= ends[i + 1]["start"] + 1e-6 for i in range(len(ends) - 1)), "clips still do not overlap")
        pg.locator(".clip").nth(3).dblclick(); pg.wait_for_timeout(200)
        check(len(S("S.clips")) == 3, "double-click removes a clip")

        # the timeline keeps 10 s free after the last clip
        last_end = max(k["start"] + k["dur"] for k in S("S.clips"))
        check(pg.evaluate("window.__score.timeline.span()") >= last_end + 10 - 0.05, f"10 seconds of room after the last clip ({pg.evaluate('window.__score.timeline.span()'):.1f} s on show, the piece ends at {last_end:.1f})")

        # the interpolation: the symbol opens its panel in the place of the playground
        sym = pg.locator(".interp").first
        check(sym.inner_text() == "\u219d", "the symbol between clips is U+219D")
        sym.click(); pg.wait_for_timeout(300)
        check(pg.locator("[data-block=interpolation]").is_visible() and not pg.locator("[data-block=playground]").is_visible() and "open" in sym.get_attribute("class"),
              "clicking it opens the interpolation panel in the place of the playground")
        ib = pg.locator("[data-block=interpolation] canvas").bounding_box()
        U = lambda x, y: (ib["x"] + ib["width"] * (48 + x * (790 - 96)) / 790, ib["y"] + ib["height"] * (790 - 48 - y * (790 - 96)) / 790)
        cv = lambda: S("S.clips.find(c => c.id === S.interp).curve")
        check(cv() == [[0, 0], [0.2, 0.3], [0.5, 0.5], [0.8, 0.7], [1, 1]], "it starts with the default dots (0,0) (0.2,0.3) (0.5,0.5) (0.8,0.7) (1,1)")
        pg.mouse.dblclick(*U(0.35, 0.9)); pg.wait_for_timeout(200)
        check(len(cv()) == 6 and [round(p[0], 2) for p in cv()][2] == 0.35, "a double-click on an empty place adds a dot")
        pg.mouse.move(*U(0.5, 0.5)); pg.mouse.down(); pg.mouse.move(*U(0.55, 0.8), steps=5); pg.mouse.up(); pg.wait_for_timeout(200)
        moved = [p for p in cv() if abs(p[0] - 0.55) < 0.03]
        check(moved and abs(moved[0][1] - 0.8) < 0.03, "a dot can be dragged")
        pg.mouse.move(*U(0, 0)); pg.mouse.down(); pg.mouse.move(*U(0.1, 0.3), steps=4); pg.mouse.up(); pg.wait_for_timeout(100)
        check(cv()[0] == [0, 0], "the ends do not move")
        pg.mouse.dblclick(*U(0.35, 0.9)); pg.wait_for_timeout(200)
        check(len(cv()) == 5, "a double-click on a dot removes it")
        check("custom" in pg.locator(".interp").first.get_attribute("class"), "a changed curve marks its symbol")
        pg.locator("[data-block=interpolation] button", has_text="Default").click(); pg.wait_for_timeout(200)
        check(cv() == [[0, 0], [0.2, 0.3], [0.5, 0.5], [0.8, 0.7], [1, 1]] and "custom" not in pg.locator(".interp").first.get_attribute("class"), "Default puts the dots back")
        pg.mouse.dblclick(*U(0.35, 0.9)); pg.wait_for_timeout(200)              # leave a custom curve for the generation below
        pg.locator("[data-block=interpolation] [data-ref=back]").click(); pg.wait_for_timeout(200)
        check(pg.locator("[data-block=playground]").is_visible() and not pg.locator("[data-block=interpolation]").is_visible(), "Back returns to the playground")
        sym2 = pg.locator(".interp").first
        sym2.click(); pg.wait_for_timeout(200); sym2.click(); pg.wait_for_timeout(200)
        check(pg.locator("[data-block=playground]").is_visible(), "a second click on the symbol closes the panel")

        # Generate: renders from the first clip to the last one, and keeps the path in the atlas
        gen = pg.locator("[data-block=settings] [data-ref=generate]")
        check(gen.is_enabled(), "Generate is on with clips on the timeline")
        seed_w = pg.locator("[data-block=settings] [data-ref=seed]").bounding_box()["width"]
        check(seed_w >= 90, f"the seed box shows six digits ({seed_w:.0f} px)")
        pg.fill("[data-block=settings] [data-ref=seed]", "654321"); pg.locator("[data-block=settings] [data-ref=seed]").press("Enter")
        want = sorted(S("S.clips"), key=lambda k: k["start"]); span = want[-1]["start"] + want[-1]["dur"] - want[0]["start"]
        gen.click(); pg.wait_for_timeout(300)
        check(S("S.rendering !== null") and gen.is_disabled(), "while it generates, Generate is off and shows the progress")
        pg.wait_for_function("window.__score.S.rendering === null && window.__score.S.takes.length === 2", timeout=240000)
        newest = S("S.takes[0]")
        check(abs(newest["seconds"] - span) < 0.6 and newest["seed"] == 654321 and newest["model"] == "m1",
              f"the take lasts from the first clip to the last one ({newest['seconds']:.1f} s for {span:.1f} s) with its seed")
        meta = __import__("json").loads((tmp / "takes" / (newest["id"] + ".json")).read_text())
        check(meta["path3"] and len(meta["path3"][0]) == 3 and abs(len(meta["path3"]) / meta["rate"] - span) < 0.3 and abs(meta["start"] - want[0]["start"]) < 1e-6,
              f"the take keeps the 3-D path of its embeddings ({len(meta['path3'])} points at {meta['rate']:.2f} Hz)")
        check(all(abs(sum(x * x for x in p) ** 0.5) < 1.6 for p in meta["path3"]), "...inside the atlas sphere")
        check("path3" not in newest, "the list of takes does not carry the long path")
        check("generating" in pg.locator("[data-block=log] .lines").inner_text() and "done" in pg.locator("[data-block=log] .lines").inner_text(), "the log has the report")
        check(gen.is_enabled(), "Generate is on again")

        # Clear (timeline and playground)
        pg.locator("[data-block=timeline] [data-ref=clear]").click(); pg.wait_for_timeout(200)
        check(len(S("S.clips")) == 0 and gen.is_disabled() and pg.locator(".interp").count() == 0, "Clear empties the timeline (and Generate goes off)")
        c3 = pg.locator("[data-block=playground] canvas").bounding_box()
        fx_, fy_ = at(S("S.dots[S.dots.length - 1]"))
        pg.mouse.dblclick(fx_, fy_); pg.wait_for_timeout(300)
        check(S("S.dots.filter(d => d).length") == 3, "double-click removes a dot")
        pg.locator("[data-block=playground] [data-ref=clear]").click(); pg.wait_for_timeout(200)
        check(S("S.dots.filter(d => d).length") == 0 and S("S.point") is None and S("S.free.length") == 0 and S("S.dots.length") == n_src, "Clear empties the playground")

        # the model panel: NFE, the model menu
        nfe0 = S("S.gen.nfe")
        k = pg.locator("[data-block=settings] .knob").first.locator("svg").bounding_box()
        pg.mouse.move(k["x"] + 20, k["y"] + 20); pg.mouse.down(); pg.mouse.move(k["x"] + 20, k["y"] - 30, steps=5); pg.mouse.up(); pg.wait_for_timeout(200)
        check(S("S.gen.nfe") != nfe0, f"the NFE knob changes the NFE ({nfe0} -> {S('S.gen.nfe')})")
        pg.locator("[data-block=settings] [data-ref=dice]").click()
        check(S("S.gen.seed") != 654321 and 0 <= S("S.gen.seed") <= 999999, f"the die picks a new seed ({S('S.gen.seed')})")
        pg.locator("[data-block=settings] [data-ref=modelbtn]").click(); pg.wait_for_timeout(200)
        check(pg.locator(".menu button").count() == 1 and "current" in pg.locator(".menu button").first.get_attribute("class"), "the model menu lists the model")
        pg.mouse.click(5, 5); pg.wait_for_timeout(100)
        check(pg.locator(".menu").count() == 0, "a click away closes it")
        check("model m1" in pg.locator("[data-block=log] .lines").inner_text(), "the log says which model is shown")

        # the takes view: the takes in the place of the sources, the atlas in the place of the playground
        check(not pg.locator("[data-block=takes]").is_visible() and pg.locator("[data-block=sources]").is_visible()
              and pg.locator("[data-block=playground]").is_visible() and not pg.locator("[data-block=atlas]").is_visible(), "the sources and the playground show first")
        pg.locator("[data-block=sources] [data-tab=takes]").click(); pg.wait_for_timeout(300)
        check(pg.locator("[data-block=takes]").is_visible() and not pg.locator("[data-block=sources]").is_visible(), "the Takes tab replaces the sources")
        check(pg.locator("[data-block=atlas]").is_visible() and not pg.locator("[data-block=playground]").is_visible(), "...and the atlas replaces the playground")
        ab, pb = pg.locator("[data-block=atlas]").bounding_box(), pg.locator("[data-block=settings]").bounding_box()
        check(ab["x"] <= pb["x"] + 1 and ab["y"] < pb["y"], "the atlas is in the place of the playground")
        check(pg.locator(".take").count() == 2 and "Takes (2)" in pg.locator("[data-block=takes] [data-tab=takes]").inner_text(), "the takes are listed and counted")
        fixture = pg.locator(".take", has_text="seed 7")
        check("NFE 12" in fixture.inner_text(), "a take shows what made it")
        link = fixture.locator("a.tdown")
        check(link.get_attribute("href").endswith(take["id"] + ".wav") and link.get_attribute("download") == take["id"] + ".wav", "each take has its own download button")
        r_ = urllib.request.urlopen(f"http://127.0.0.1:{port}/takes/{take['id']}.wav")
        check(r_.status == 200 and r_.headers["content-type"] == "audio/wav" and r_.read(4) == b"RIFF", "the takes route serves the wav")
        # play the generated take: the atlas shows its path and follows the sound
        made = pg.locator(".take", has_text="seed 654321")
        made.locator(".tplay").click(); pg.wait_for_timeout(700)
        st = pg.evaluate("window.__score.atlas.state()")
        check("playing" in made.get_attribute("class") and made.locator(".tplay").inner_text() == "■" and st["trace"] and st["playing"] and st["points"] == len(meta["path3"]),
              f"playing a take marks it and the atlas follows its path ({st})")
        made.locator(".tplay").click(); pg.wait_for_timeout(200)
        check("playing" not in made.get_attribute("class") and not pg.evaluate("window.__score.atlas.state().playing"), "a second press stops it (and the dot)")
        fixture.locator(".tplay").click(); pg.wait_for_timeout(300)
        check("playing" in fixture.get_attribute("class") and not pg.evaluate("window.__score.atlas.state().trace"), "a take with no path plays without one on the atlas")
        fixture.locator(".tplay").click(); pg.wait_for_timeout(200)
        pg.locator("[data-block=takes] [data-tab=sources]").click(); pg.wait_for_timeout(100)
        check(pg.locator("[data-block=sources]").is_visible() and pg.locator("[data-block=playground]").is_visible(), "the Sources tab brings the sources and the playground back")
        pg.locator("[data-block=sources] [data-tab=takes]").click(); pg.wait_for_timeout(100)
        for _ in range(2):
            pg.locator(".take .tdel").first.click(); pg.wait_for_timeout(400)
        check(pg.locator(".take").count() == 0 and "Nothing generated yet" in pg.locator("[data-block=takes]").inner_text()
              and not list((tmp / "takes").glob("take-*")), "removing the takes removes their files")

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
