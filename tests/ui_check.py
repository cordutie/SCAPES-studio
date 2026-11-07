"""Drives the page in headless Chromium against a running server (app_live.py --model NAME --port 7871): panels, knobs, edit mode, rename, reorder, record. Run: python tests/ui_check.py"""
import glob, sys, time
from playwright.sync_api import sync_playwright
chrome = glob.glob("/home/esteban/.cache/ms-playwright/chromium-*/chrome-linux64/chrome")[0]
S = "/tmp/claude-1000/-home-esteban-Documents-projects-dev-SCAPES/17e16bba-b74e-4935-98d2-635dc558b3d5/scratchpad/"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome, args=["--autoplay-policy=no-user-gesture-required"])
    page = b.new_page(viewport={"width": 1900, "height": 1300})
    errs = []
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto("http://127.0.0.1:7871/")
    page.wait_for_function("window.__demo && window.__demo.player && window.__demo.player.connected()", timeout=90000)
    d = "window.__demo"
    def drop(i, fx, fy):
        bb = page.locator("[data-block=clusters] .blocks button").nth(i).bounding_box()
        c = page.locator("[data-block=plane] canvas").bounding_box()
        page.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2); page.mouse.down()
        page.mouse.move(c["x"] + fx * c["width"], c["y"] + fy * c["height"], steps=6); page.mouse.up()
    drop(0, 0.3, 0.4); drop(2, 0.7, 0.6); drop(5, 0.5, 0.8)
    page.wait_for_function(f"{d}.S.lastLive && {d}.S.lastLive.dec3", timeout=20000)
    time.sleep(2)
    print("defaults", page.evaluate(f"[{d}.S.glideT, {d}.S.hz]"))
    print("buttons:", page.inner_text("[data-block=clusters] .top"), "|", page.inner_text("[data-block=disk] .top"))
    # the (i) of each panel: hidden until hovered, then a text inside the screen
    for blk_name in ["clusters", "view3d", "effects", "plane", "disk", "generation"]:
        icon = page.locator(f"[data-block={blk_name}] .info"); icon.hover(); time.sleep(0.2)
        tip = icon.locator(".info-tip"); r = tip.bounding_box()
        print("info", blk_name, tip.is_visible(), r and (0 <= r["x"] and r["x"] + r["width"] <= 1920 and 0 <= r["y"] and r["y"] + r["height"] <= 1080),
              page.evaluate("(e) => getComputedStyle(e).color", icon.element_handle()))
        if blk_name == "plane": page.screenshot(path=S + "info.png")
    page.mouse.move(5, 5); time.sleep(0.2)
    page.click("[data-block=view3d] [data-ref=rotate]")
    page.click("[data-ref=play]"); time.sleep(3)
    page.screenshot(path=S + "ui1.png")
    # rename
    blk = page.locator("[data-block=clusters] .blocks button").nth(0)
    old = blk.inner_text(); blk.dblclick()
    page.fill("input.rename", "my sound"); page.press("input.rename", "Enter"); time.sleep(1)
    print("rename:", old, "->", page.locator("[data-block=clusters] .blocks button").nth(0).inner_text())
    page.locator("[data-block=clusters] .blocks button").nth(0).dblclick(); page.fill("input.rename", ""); page.press("input.rename", "Enter"); time.sleep(0.5)   # put the name back: the test must leave the model folder as it was
    # knob: double click resets, type value
    nfe = page.locator("[data-block=generation] .knob").nth(0)
    print("nfe before", nfe.locator(".num").inner_text())
    page.evaluate(f"(() => {{ const o = {d}.player.setParams.bind({d}.player); window.__calls = []; {d}.player.setParams = (p) => {{ window.__calls.push(p); o(p); }}; }})()")
    nfe.locator("svg").hover(); page.mouse.down(); page.mouse.move(*(lambda r: (r["x"] + r["width"] / 2, r["y"] + r["height"] / 2 - 40))(nfe.locator("svg").bounding_box()), steps=10)
    print("nfe dragged, still held: shown", nfe.locator(".num").inner_text(), "applied calls", page.evaluate("window.__calls.length"))
    page.mouse.up(); time.sleep(0.2)
    print("after release: applied calls", page.evaluate("window.__calls"))
    nfe.locator("svg").dblclick(); print("nfe reset", nfe.locator(".num").inner_text())
    nfe.locator(".num").click(); page.fill(".num-edit", "24"); page.press(".num-edit", "Enter"); print("nfe typed", nfe.locator(".num").inner_text())
    # fx: drag cell 0 onto cell 3
    c0 = page.locator("[data-block=effects] .fx").nth(0).locator(".fx-head").bounding_box(); c3 = page.locator("[data-block=effects] .fx").nth(3).bounding_box()
    page.mouse.move(c0["x"] + 60, c0["y"] + 10); page.mouse.down(); page.mouse.move(c3["x"] + 100, c3["y"] + 100, steps=8); page.mouse.up()
    print("order", page.evaluate(f"{d}.player.chain.state().order"))
    page.locator("[data-block=effects] .fx").nth(0).locator("[data-act=power]").click()
    # saturator at 0 dB passes quiet signal; level to -inf
    page.screenshot(path=S + "ui2.png")
    page.click("[data-ref=rec]"); time.sleep(1.5)
    with page.expect_download() as dl:
        page.click("[data-ref=rec]")
    print("wav", dl.value.suggested_filename)
    print("log:", page.inner_text("[data-block=generation] .m-log")[:400])
    page.click("[data-ref=stop]"); time.sleep(1)
    print("footer visible:", page.locator("footer").first.is_visible() if page.locator("footer").count() else "no footer")
    print("errors:", errs[:5])
    b.close()
