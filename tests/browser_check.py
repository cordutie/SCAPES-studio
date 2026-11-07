"""The audio side of the page, in headless Chromium against a running server (python app_live.py --model ... --port 7870):
each effect measured offline on a test tone, the order of the chain, and a machine that cannot keep up (the buffer grows, the
light goes red, nothing stops). The panels and the controls are in tests/ui_check.py.
Run: python tests/browser_check.py [port]"""
import glob, re, sys, time
from playwright.sync_api import sync_playwright

port = sys.argv[1] if len(sys.argv) > 1 else "7870"
chrome = glob.glob("/home/esteban/.cache/ms-playwright/chromium-*/chrome-linux64/chrome")[0]
problems = []


def check(cond, text):
    print(("ok   " if cond else "FAIL ") + text)
    if not cond:
        problems.append(text)


def live(page):                                   # the live line of the log: state, load, audio ahead, underruns
    return page.inner_text("[data-block=generation] .m-log .live")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{port}/")
    page.wait_for_function("window.__demo && window.__demo.player && window.__demo.player.connected()", timeout=60000)
    d = "window.__demo"

    # --- each effect, measured: an offline render of a test tone through the same chain code ---
    fxr = page.evaluate("""async () => {
      const {createChain} = await import('/web/shared/audio/fx/chain.js');
      const {EFFECTS} = await import('/web/shared/audio/fx/index.js');
      const SR = 44100;
      async function render(source, setup, seconds = 1) {
        const o = new OfflineAudioContext(2, SR * seconds, SR);
        const chain = createChain(o, EFFECTS);
        setup(chain);
        const buf = o.createBuffer(2, SR * seconds, SR);
        for (let c = 0; c < 2; c++) buf.getChannelData(c).set(source(SR * seconds));
        const src = o.createBufferSource(); src.buffer = buf;
        src.connect(chain.input); chain.output.connect(o.destination); src.start();
        return (await o.startRendering()).getChannelData(0);
      }
      const sine = (hz, amp) => (n) => Float32Array.from({length: n}, (_, i) => amp * Math.sin(2 * Math.PI * hz * i / SR));
      const rms = (x, a = 0, b = x.length) => Math.sqrt(x.slice(a, b).reduce((s, v) => s + v * v, 0) / (b - a));
      const peak = (x) => x.reduce((m, v) => Math.max(m, Math.abs(v)), 0);
      const goertzel = (x, hz) => { let re = 0, im = 0; for (let i = 0; i < x.length; i++) { const w = 2 * Math.PI * hz * i / SR; re += x[i] * Math.cos(w); im -= x[i] * Math.sin(w); } return 2 * Math.hypot(re, im) / x.length; };
      const maxdiff = (a, b, from = 2000) => { let m = 0; for (let i = from; i < a.length; i++) m = Math.max(m, Math.abs(a[i] - b[i])); return m; };
      const out = {};
      const bypass = await render(sine(1000, 0.5), () => {});
      // saturator: 0 dB gain leaves a quiet signal as it is; +12 dB gain squares the wave up; level -inf is silence
      const quiet = sine(200, 0.05)(SR);
      const sat0 = await render(sine(200, 0.05), (c) => c.setEnabled('saturator', true));
      out.sat0_ratio = rms(sat0.slice(10000)) / rms(quiet.slice(10000));      // the oversampling delays the wave a little: compare levels
      const sat12 = await render(sine(200, 0.5), (c) => { c.setEnabled('saturator', true); c.setParam('saturator', 'gain', 12); });
      out.sat12_peak = peak(sat12.slice(2000));
      const satoff = await render(sine(200, 0.5), (c) => { c.setEnabled('saturator', true); c.setParam('saturator', 'level', -Infinity); });
      out.sat_silent = peak(satoff.slice(20000));
      // eq: +12 dB at 1 kHz (band 4) is about 4x; a band elsewhere leaves 1 kHz alone
      const eq1 = await render(sine(1000, 0.25), (c) => { c.setEnabled('eq', true); c.setParam('eq', 'b4', 12); });
      out.eq_gain_1k = rms(eq1.slice(4000)) / rms(sine(1000, 0.25)(SR).slice(4000));
      const eq2 = await render(sine(1000, 0.25), (c) => { c.setEnabled('eq', true); c.setParam('eq', 'b0', 12); });
      out.eq_gain_other = rms(eq2.slice(4000)) / rms(sine(1000, 0.25)(SR).slice(4000));
      // reverb: an impulse leaves a tail after 0.5 s; with the effect off there is none
      const imp = (n) => { const x = new Float32Array(n); x[10] = 1; return x; };
      const revOn = await render(imp, (c) => { c.setEnabled('reverb', true); c.setParam('reverb', 'mix', 0.8); c.setParam('reverb', 'decay', 1.5); }, 2);
      const revOff = await render(imp, () => {}, 2);
      out.rev_tail_on = rms(revOn, 22050, 44100); out.rev_tail_off = rms(revOff, 22050, 44100);
      // ring mod: 1000 Hz x 200 Hz gives 800 and 1200 Hz and no 1000 Hz (mix 1)
      const rm = await render(sine(1000, 0.5), (c) => { c.setEnabled('ringmod', true); c.setParam('ringmod', 'freq', 200); c.setParam('ringmod', 'mix', 1); });
      const t = rm.slice(4000, 4000 + 22050);
      out.rm_800 = goertzel(t, 800); out.rm_1200 = goertzel(t, 1200); out.rm_1000 = goertzel(t, 1000);
      // order: saturator then EQ is not the same sound as EQ then saturator
      const setup = (first) => (c) => {
        c.setEnabled('saturator', true); c.setParam('saturator', 'gain', 12);
        c.setEnabled('eq', true); c.setParam('eq', 'b6', -12); c.setParam('eq', 'b5', 12);
        if (first === 'eq') c.place('eq', 0);
      };
      const a = await render(sine(3000, 0.4), setup('sat')), b = await render(sine(3000, 0.4), setup('eq'));
      out.order_diff = maxdiff(a, b, 4000);
      // switched off, everything is the bypass
      out.off_diff = maxdiff(await render(sine(1000, 0.5), (c) => { c.setParam('saturator', 'gain', 12); }), bypass);
      return out;
    }""")
    print("fx", {k: round(v, 4) for k, v in fxr.items()})
    check(0.93 < fxr["sat0_ratio"] < 1.07, "saturator at 0 dB gain leaves a quiet signal at the same level (x%.3f)" % fxr["sat0_ratio"])
    check(fxr["sat12_peak"] > 0.95, "saturator at +12 dB soft-clips towards 1 (peak %.2f)" % fxr["sat12_peak"])
    check(fxr["sat_silent"] < 1e-4, "saturator level -inf dB is silence")
    check(3.3 < fxr["eq_gain_1k"] < 4.6, "eq: +12 dB at 1 kHz is x%.2f (4.0 expected)" % fxr["eq_gain_1k"])
    check(0.9 < fxr["eq_gain_other"] < 1.15, "eq: a boost at 63 Hz leaves 1 kHz alone (x%.2f)" % fxr["eq_gain_other"])
    check(fxr["rev_tail_on"] > 20 * max(fxr["rev_tail_off"], 1e-6), "reverb: a tail after the impulse (%.4f vs %.6f off)" % (fxr["rev_tail_on"], fxr["rev_tail_off"]))
    check(fxr["rm_800"] > 0.2 and fxr["rm_1200"] > 0.2 and fxr["rm_1000"] < 0.05, "ring mod: sidebands at 800 and 1200 Hz, none at 1000 Hz")
    check(fxr["order_diff"] > 0.02, "order: saturator->EQ differs from EQ->saturator (max diff %.3f)" % fxr["order_diff"])
    check(fxr["off_diff"] < 1e-4, "an effect that is off leaves the sound untouched")

    # --- a machine that cannot keep up: the buffer must grow, the player must not click or stop ---
    bb = page.locator("[data-block=clusters] .blocks button").nth(0).bounding_box()
    c = page.locator("[data-block=plane] canvas").bounding_box()
    page.mouse.move(bb["x"] + 40, bb["y"] + 20); page.mouse.down()
    page.mouse.move(c["x"] + c["width"] / 2, c["y"] + c["height"] / 2, steps=5); page.mouse.up()
    page.wait_for_function(f"{d}.S.lastLive && {d}.S.lastLive.dec3", timeout=20000)
    page.click("[data-ref=play]")
    page.wait_for_function("document.querySelector('[data-block=generation] .m-log .live').innerText.includes('Running')", timeout=20000)
    time.sleep(3)
    check("Running" in live(page), "running: " + live(page))
    page.evaluate(f"{d}.player.setParams({{nfe: 64, cfg: 3}})")
    time.sleep(8)
    s = live(page); print("stress:", s)
    under = int(re.search(r"underruns (\d+)", s).group(1)); target = float(re.search(r"target ([0-9.]+)", s).group(1))
    check(under > 0, f"too slow: underruns are counted ({under})")
    seen = set()
    for _ in range(30):
        seen.add(page.get_attribute("[data-block=generation] .light", "data-state")); time.sleep(0.1)
    check("late" in seen, f"too slow: the light goes red (saw {seen})")
    check(target > 0.4, f"too slow: the buffer target grew to {target:.2f} s")
    check("Running" in s, "too slow: it keeps running")
    page.evaluate(f"{d}.player.setParams({{nfe: 8, cfg: 1}})")
    time.sleep(5)
    u2 = int(re.search(r"underruns (\d+)", live(page)).group(1)); time.sleep(4)
    u3 = int(re.search(r"underruns (\d+)", live(page)).group(1))
    check(u3 == u2, f"back at NFE 8 it is stable again (underruns stay at {u3})")

    # Stop: the sound ends with its fade, the buttons come back; then a second run
    page.click("[data-ref=stop]")
    page.wait_for_function("document.querySelector('[data-block=generation] .m-log .live').innerText.includes('Stopped')", timeout=20000)
    page.wait_for_function(f"{d}.player.isDrained()", timeout=20000)
    check(page.is_enabled("[data-ref=play]"), "Play is enabled again after the sound has drained")
    check(page.get_attribute("[data-block=generation] .light", "data-state") == "off", "the light is off when stopped")
    page.click("[data-ref=play]")
    page.wait_for_function("document.querySelector('[data-block=generation] .m-log .live').innerText.includes('Running')", timeout=20000)
    time.sleep(2)
    page.click("[data-ref=stop]")
    page.wait_for_function(f"{d}.player.isDrained()", timeout=20000)
    check(True, "a second run starts and stops")
    check(not [e for e in errors if "favicon" not in e], f"no console errors {errors[:5]}")
    browser.close()

print("\nPROBLEMS:", problems if problems else "none")
sys.exit(1 if problems else 0)
