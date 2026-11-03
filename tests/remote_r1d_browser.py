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
    evidence = work / "evidence/VE-R1d"
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
                            value = {
                                "items": [
                                    {**item, "id": str(n), "name": f"Synthetic {n}"}
                                    for n in range(36)
                                ]
                            }
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
                    expect(page.locator("header")).to_have_count(0)
                    expect(page.locator(".video-row")).to_have_count(36)
                    assert page.locator(".video-row").first.inner_text() == ""
                    page.wait_for_function("""() => [...document.querySelectorAll('.videos img')]
                      .slice(0, 12).every(img=>img.complete && img.naturalWidth>0)""")
                    page.screenshot(path=str(evidence / f"{engine}-{kind}-library.png"))
                    page.evaluate("window.scrollTo(0, 250)")
                    page.evaluate(
                        "window.savedScroll=scrollY; "
                        "window.savedImages=[...document.querySelectorAll('.videos img')]"
                    )
                    page.locator(".video-row").nth(8).click()
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
                    page.keyboard.press("Space")
                    assert page.locator("video").evaluate("v=>v.paused") is False
                    page.keyboard.press("ArrowRight")
                    assert page.locator("video").evaluate("v=>v.currentTime") == 65
                    player = page.locator(".player")
                    expect(page.locator(".player-controls button")).to_have_count(0)
                    expect(page.locator(".player-title")).to_have_count(0)
                    page.mouse.move(1, 1)
                    page.wait_for_timeout(2800)
                    expect(player).to_have_class("player controls-hidden")
                    box = player.bounding_box()
                    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                    if kind == "ipad":
                        page.touchscreen.tap(x, y)
                        page.wait_for_timeout(300)
                        assert page.locator("video").evaluate("v=>v.paused") is False
                        page.touchscreen.tap(x, y)
                        page.wait_for_timeout(300)
                        assert page.locator("video").evaluate("v=>v.paused") is True
                        page.evaluate("""() => {
                          window.nativeCalls=0;
                          document.querySelector('video').webkitEnterFullscreen=()=>window.nativeCalls++;
                        }""")
                        page.touchscreen.tap(x, y)
                        page.touchscreen.tap(x, y)
                        assert page.evaluate("window.nativeCalls") == 1
                    else:
                        page.mouse.move(x, y)
                        page.keyboard.press("Space")
                    expect(page.locator(".player-remaining")).to_have_text("-8:55")
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
                    assert (
                        page.locator(".seek-preview").evaluate(
                            "e=>getComputedStyle(e).borderTopWidth"
                        )
                        == "0px"
                    )
                    assert (
                        page.locator(".seek-preview").evaluate(
                            "e=>getComputedStyle(e).backgroundColor"
                        )
                        == "rgba(0, 0, 0, 0)"
                    )
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
                    page.evaluate("""() => {
                      window.samples=[]; window.sampling=true;
                      function sample(){
                        const images=[...document.querySelectorAll('.videos img')];
                        samples.push({count:images.length,
                          same:images.every((img,i)=>img===savedImages[i])});
                        if(window.sampling)requestAnimationFrame(sample);
                      }
                      document.querySelector('.back').addEventListener('click',()=>requestAnimationFrame(sample),{once:true});
                    }""")
                    page.get_by_role("button", name="Library", exact=False).first.click()
                    page.wait_for_timeout(500)
                    samples = page.evaluate("window.sampling=false; window.samples")
                    assert len(samples) >= 2 and all(
                        v["count"] == 36 and v["same"] for v in samples
                    ), samples
                    assert abs(page.evaluate("scrollY-savedScroll")) < 2
                    page.get_by_role("button", name="Settings", exact=True).click()
                    expect(page.locator(".storage")).to_be_visible()
                    page.get_by_role("button", name="Library", exact=True).click()
                    assert page.evaluate(
                        "[...document.querySelectorAll('.videos img')]"
                        ".every((img,i)=>img===savedImages[i])"
                    )
                    assert not errors, errors
                    results.append(
                        dict(
                            engine=engine,
                            viewport=kind,
                            status="PASS",
                            return_frames=len(samples),
                            native_fullscreen="stubbed dispatch only; physical iPad NOT_RUN",
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
