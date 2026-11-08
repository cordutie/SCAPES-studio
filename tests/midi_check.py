"""MIDI learn in headless Chromium with a fake MIDI port: the ⏣ button, binding a CC to a knob, a fader and the x / y of the playgrounds,
a CC for two controls, the channel, deleting a map. Starts its own server. Run: python tests/midi_check.py [model_folder]"""
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


FAKE = """
window.__midi = {sent: 0};
navigator.requestMIDIAccess = async () => {
  const port = {id: 'fake', name: 'fake', onmidimessage: null};
  const access = {inputs: new Map([['fake', port]]), onstatechange: null};
  window.__cc = (ch, cc, v) => port.onmidimessage && port.onmidimessage({data: [0xB0 | ch, cc, v]});
  return access;
};
"""

tmp = Path(tempfile.mkdtemp())
(tmp / "models" / "m1").mkdir(parents=True)
for f in [x for x in real.rglob("*") if x.is_file()]:
    (tmp / "models" / "m1" / f.relative_to(real)).parent.mkdir(parents=True, exist_ok=True)
    (tmp / "models" / "m1" / f.relative_to(real)).symlink_to(f)
port = 7885
srv = subprocess.Popen([sys.executable, str(root / "app_live.py"), "--models-dir", str(tmp / "models"), "--port", str(port)], cwd=root,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    for _ in range(90):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/"); break
        except Exception:
            time.sleep(1)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.add_init_script(FAKE)
        pg.goto(f"http://127.0.0.1:{port}/")
        pg.wait_for_function("window.__demo && window.__demo.player && window.__demo.player.connected()", timeout=90000)

        btn = pg.locator("[data-ref=midi]")
        knob = lambda lab: pg.locator(".knob", has=pg.locator(f".lab:text-is('{lab}')"))
        num = lambda lab: knob(lab).locator(".num").inner_text()
        log = lambda: pg.locator("[data-block=generation] .lines").inner_text()
        def learn(cc, ch, target, v=64, click=True):
            btn.click(); pg.wait_for_timeout(300)
            if cc is not None:
                pg.evaluate(f"window.__cc({ch}, {cc}, {v})")
            target.click(position={"x": 10, "y": 10}) if click else None
            pg.wait_for_timeout(200)

        check("⏣" in btn.inner_text(), "the fourth button is there")
        check(pg.locator("[data-block=generation] .transport button").count() == 4, "four transport buttons")
        btn.click(); pg.wait_for_timeout(300)
        check("on" in (btn.get_attribute("class") or ""), "pressing ⏣ turns it orange (class on)")
        check(pg.evaluate("document.querySelector('#demo').classList.contains('midi-learning')"), "the page is in learn mode")
        # a press on a knob while learning binds it and does not turn it
        cfg0 = num("CFG")
        pg.evaluate("window.__cc(0, 7, 64)")
        k = knob("CFG").locator("svg").bounding_box()
        pg.mouse.move(k["x"] + 30, k["y"] + 30); pg.mouse.down(); pg.mouse.move(k["x"] + 30, k["y"] - 40, steps=4); pg.mouse.up(); pg.wait_for_timeout(300)
        check("CC 7 (ch 1) → CFG" in log(), "the log says CC 7 (ch 1) → CFG")
        check(num("CFG") == cfg0, "the press did not turn the knob")
        check("on" not in (btn.get_attribute("class") or "").split(), "learn turned off after one map")
        # the CC drives the knob over its range
        pg.evaluate("window.__cc(0, 7, 0)"); pg.wait_for_timeout(200); lo = num("CFG")
        pg.evaluate("window.__cc(0, 7, 127)"); pg.wait_for_timeout(200); hi = num("CFG")
        check(lo != hi, f"CC 7 moves CFG ({lo} .. {hi})")
        # another channel does nothing
        pg.evaluate("window.__cc(1, 7, 0)"); pg.wait_for_timeout(200)
        check(num("CFG") == hi, "the same CC on another channel does nothing")
        # the same CC for a second control (the volume): both follow
        learn(7, 0, knob("Volume").locator("svg"))
        v0 = num("Volume"); c0 = num("CFG")
        pg.evaluate("window.__cc(0, 7, 0)"); pg.wait_for_timeout(200)
        check(num("Volume") != v0 and num("CFG") != c0, "one CC drives two controls")
        # a fader of the EQ
        eq = pg.locator(".bars input").nth(2)
        learn(21, 0, eq)
        pg.evaluate("window.__cc(0, 21, 127)"); pg.wait_for_timeout(200)
        check(float(eq.input_value()) == 12.0, "a CC drives an EQ fader to its top")
        pg.evaluate("window.__cc(0, 21, 0)"); pg.wait_for_timeout(200)
        check(float(eq.input_value()) == -12.0, "...and to its bottom")
        # delete a map: learn with no CC moved, press the control
        learn(None, 0, knob("CFG").locator("svg"))
        check("map deleted" in log(), "pressing a control with no CC deletes its map")
        c1 = num("CFG")
        pg.evaluate("window.__cc(0, 7, 127)"); pg.wait_for_timeout(200)
        check(num("CFG") == c1, "the deleted control no longer follows")
        # a map survives the panel drawing its controls again (an effect switched off and on)
        cell = pg.locator(".fx", has=pg.locator(".title:text-is('Saturator')"))
        gain = lambda: pg.locator(".fx", has=pg.locator(".title:text-is('Saturator')")).locator(".knob .num").first.inner_text()
        learn(50, 0, cell.locator(".knob").first.locator("svg"))
        for step in ("off", "on"):
            pg.locator(".fx", has=pg.locator(".title:text-is('Saturator')")).locator("[data-act=power]").click(); pg.wait_for_timeout(300)
            g0 = gain()
            pg.evaluate("window.__cc(0, 50, 127)"); pg.wait_for_timeout(200); g1 = gain()
            pg.evaluate("window.__cc(0, 50, 0)"); pg.wait_for_timeout(200)
            check(g1 != gain() or g1 != g0, f"the map of an effect knob survives switching the effect {step} ({g0} -> {g1})")
        check("midi-mapped" in (cell.locator(".knob").first.get_attribute("class") or ""), "the mapped mark comes back with the knob")
        # x / y of the playgrounds
        check(not pg.locator("[data-block=plane] .midi-xy").is_visible(), "X and Y are hidden outside learn mode")
        b0 = pg.locator("[data-block=clusters] .blocks button").nth(0).bounding_box(); c = pg.locator("[data-block=plane] canvas").bounding_box()
        pg.mouse.move(b0["x"] + 40, b0["y"] + 20); pg.mouse.down(); pg.mouse.move(c["x"] + c["width"] / 2, c["y"] + c["height"] / 2, steps=5); pg.mouse.up()
        b1 = pg.locator("[data-block=clusters] .blocks button").nth(1).bounding_box()
        pg.mouse.move(b1["x"] + 40, b1["y"] + 20); pg.mouse.down(); pg.mouse.move(c["x"] + 80, c["y"] + 80, steps=5); pg.mouse.up(); pg.wait_for_timeout(300)
        btn.click(); pg.wait_for_timeout(300)
        check(pg.locator("[data-block=plane] .midi-xy").is_visible() and pg.locator("[data-block=disk] .midi-xy").is_visible(), "X and Y show in both playgrounds while learning")
        btn.click(); pg.wait_for_timeout(200)       # leave learn
        learn(30, 0, pg.locator("[data-block=plane] .midi-xy span").nth(0))
        learn(31, 0, pg.locator("[data-block=plane] .midi-xy span").nth(1))
        pg.evaluate("window.__cc(0, 30, 127)"); pg.evaluate("window.__cc(0, 31, 0)"); pg.wait_for_timeout(300)
        aim = pg.evaluate("window.__demo.S.aim")
        check(abs(aim[0] - 1) < 0.02 and abs(aim[1] + 1) < 0.02, f"the semantic playground follows X and Y ({aim})")
        learn(40, 0, pg.locator("[data-block=disk] .midi-xy span").nth(0))
        learn(41, 0, pg.locator("[data-block=disk] .midi-xy span").nth(1))
        pg.evaluate("window.__cc(0, 40, 0)"); pg.evaluate("window.__cc(0, 41, 127)"); pg.wait_for_timeout(300)
        u = pg.evaluate("window.__demo.S.u")
        check(abs(u[0] + 0.7071) < 0.02 and abs(u[1] - 0.7071) < 0.02, f"the structure playground follows X and Y, kept in the disk ({u})")
        check(not errors, f"no page errors {errors}")
        b.close()
finally:
    srv.terminate()
print("\nPROBLEMS:", problems or "none")
