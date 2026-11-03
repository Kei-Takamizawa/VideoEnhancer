"""Synthetic player interactions; never connects to the owner's service."""

from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def run():
    work = Path(__file__).resolve().parents[2]
    evidence = work / "evidence/VE-R1c-3"
    evidence.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(
            SimpleHTTPRequestHandler, directory=str(work / "repo/src/videoenhancer/remote/web")
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    item = dict(
        id="a" * 64, name="Synthetic landscape", filename="clip.mp4", duration=600, size=1000
    )
    try:
        with sync_playwright() as pw:
            for engine in ("webkit", "chromium"):
                browser = getattr(pw, engine).launch(
                    **({"channel": "msedge"} if engine == "chromium" else {})
                )
                for kind, width, height in (("mac", 1440, 900), ("ipad", 1180, 820)):
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        has_touch=kind == "ipad",
                        service_workers="block",
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "Version/26.0 Safari/605.1"
                        ),
                    )
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    page.add_init_script(
                        "Object.defineProperty(navigator,'maxTouchPoints',{get:()=>"
                        + ("5" if kind == "ipad" else "0")
                        + "});document.addEventListener('error',e=>{"
                        "if(e.target.tagName==='VIDEO')e.stopImmediatePropagation()},true);"
                    )

                    def route(route):
                        path = route.request.url.split(f":{server.server_port}", 1)[-1]
                        value = {}
                        if path == "/api/session":
                            value = dict(
                                paired=True, notifications_on=True, share_limit_bytes=900000000
                            )
                        elif path == "/api/library":
                            value = {"items": [item]}
                        elif path == "/api/storage":
                            value = dict(
                                total=10000, free=5000, library_bytes=1000, drive_label="Test"
                            )
                        elif path.endswith("storyboard.json"):
                            value = dict(interval=3, width=160, height=90, frames=200, sheets=2)
                        elif path.endswith(".jpg"):
                            return route.fulfill(
                                content_type="image/svg+xml",
                                body=(
                                    '<svg xmlns="http://www.w3.org/2000/svg" '
                                    'width="1920" height="1080">'
                                    '<rect width="1920" height="1080" fill="#355b66"/>'
                                    '<path d="M0 1080L700 300L1100 800L1500 100L1920 1080" '
                                    'fill="#244049"/></svg>'
                                ),
                            )
                        elif path.endswith("/video"):
                            return route.fulfill(status=204)
                        route.fulfill(json=value)

                    page.route("**/api/**", route)
                    origin = f"http://127.0.0.1:{server.server_port}/"
                    page.goto(origin)
                    page.locator(".video-row").first.click()
                    expect(page.locator(".player")).to_be_visible()
                    # Windows WebKit cannot decode the target media. Stub only media state.
                    stub = """() => {
                      const v=document.querySelector('video'); v.dataset.stub='true';
                      let paused=true, position=60;
                      Object.defineProperties(v, {
                        paused:{configurable:true,get:()=>paused},
                        duration:{configurable:true,get:()=>600},
                        readyState:{configurable:true,get:()=>1},
                        currentTime:{configurable:true,get:()=>position,set:x=>position=x}});
                      v.play=async()=>{paused=false; v.dispatchEvent(new Event('play'))};
                      v.pause=()=>{paused=true; v.dispatchEvent(new Event('pause'))};
                      v.dispatchEvent(new Event('timeupdate'));
                    }"""
                    page.evaluate(stub)
                    # Do not focus or click anything between opening and these keys.
                    page.keyboard.press("Space")
                    assert page.locator("video").evaluate("v=>v.paused") is False
                    page.keyboard.press("ArrowRight")
                    assert page.locator("video").evaluate("v=>v.currentTime") == 65
                    page.keyboard.press("Space")
                    player = page.locator(".player")
                    box = player.bounding_box()
                    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                    if kind == "mac":
                        page.mouse.click(x, y)
                        page.wait_for_timeout(300)
                        assert page.locator("video").evaluate("v=>v.paused") is False
                        page.mouse.dblclick(x, y, delay=60)
                        page.wait_for_timeout(300)
                        assert page.locator("video").evaluate("v=>v.paused") is False
                        # WebKit on Windows may not implement fullscreen. Record actual outcome.
                        fullscreen = page.evaluate("!!document.fullscreenElement")
                        if fullscreen:
                            page.keyboard.press("Escape")
                            page.wait_for_function("!document.fullscreenElement")
                        else:
                            assert (
                                "Full screen is unavailable"
                                in page.locator(".player-time").first.inner_text()
                            )
                        page.mouse.move(1, 1)
                        page.wait_for_timeout(2800)
                        expect(player).to_have_class("player controls-hidden")
                        assert player.evaluate("e=>getComputedStyle(e).cursor") == "none"
                        page.mouse.move(x, y)
                        expect(player).to_have_class("player")
                        page.keyboard.press("Space")
                    else:
                        page.touchscreen.tap(x, y)
                        expect(player).to_have_class("player controls-hidden")
                        page.touchscreen.tap(x, y)
                        expect(player).to_have_class("player")
                        assert page.locator("video").evaluate("v=>v.paused") is True
                        fullscreen = "NOT_RUN: physical iPad native fullscreen"
                    expect(page.locator(".player-remaining")).to_have_text("-8:55")
                    expect(page.get_by_role("slider", name="Volume")).to_have_count(
                        1 if kind == "mac" else 0
                    )
                    seek = page.get_by_role("slider", name="Seek")
                    seekbox = seek.bounding_box()
                    if kind == "mac":
                        page.mouse.move(
                            seekbox["x"] + seekbox["width"] / 2,
                            seekbox["y"] + seekbox["height"] / 2,
                        )
                    else:
                        seek.evaluate("el=>el.setPointerCapture=()=>{}")
                        seek.dispatch_event(
                            "pointerdown",
                            {
                                "pointerId": 1,
                                "pointerType": "touch",
                                "clientX": seekbox["x"] + seekbox["width"] / 2,
                            },
                        )
                    expect(page.locator(".seek-preview")).to_be_visible()
                    panel = page.locator(".player-controls").bounding_box()
                    nav = page.locator("#tabs").bounding_box()
                    assert panel["y"] + panel["height"] <= nav["y"], (panel, nav)
                    page.wait_for_timeout(600)
                    page.screenshot(path=str(evidence / f"{engine}-{kind}.png"))
                    if kind == "ipad":
                        seek.dispatch_event(
                            "pointercancel", {"pointerId": 1, "pointerType": "touch"}
                        )
                    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                    assert not errors, errors
                    # Notification deep link and browser history must mount fresh listeners.
                    page.goto(origin)
                    expect(page.locator(".video-row")).to_be_visible()
                    page.goto(origin + "#item=" + item["id"])
                    page.wait_for_function(
                        "document.querySelector('video') && "
                        "!document.querySelector('video').dataset.stub"
                    )
                    expect(player).to_be_visible()
                    page.evaluate(stub)
                    page.keyboard.press("Space")
                    assert page.locator("video").evaluate("v=>v.paused") is False
                    page.get_by_role("button", name="Library", exact=False).first.click()
                    expect(page.locator(".video-row")).to_be_visible()
                    page.go_back()
                    expect(player).to_be_visible()
                    page.evaluate(stub)
                    page.keyboard.press("Space")
                    assert page.locator("video").evaluate("v=>v.paused") is False
                    page.go_forward()
                    expect(page.locator(".video-row")).to_be_visible()
                    page.go_back()
                    expect(player).to_be_visible()
                    page.wait_for_function(
                        "document.querySelector('video') && "
                        "!document.querySelector('video').dataset.stub"
                    )
                    page.evaluate(stub)
                    page.keyboard.press("Space")
                    assert page.locator("video").evaluate("v=>v.paused") is False
                    results.append(
                        dict(
                            engine=engine,
                            viewport=kind,
                            status="PASS",
                            fullscreen=fullscreen,
                            media="stubbed",
                        )
                    )
                    context.close()
                browser.close()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        (evidence / "browser.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results))


if __name__ == "__main__":
    run()
