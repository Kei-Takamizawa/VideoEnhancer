"""Synthetic R1c browser smoke; run directly, without the owner's service."""

from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def run(work):
    web = work / "repo/src/videoenhancer/remote/web"
    evidence = work / "evidence/VE-R1c"
    evidence.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(web))
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results = []
    try:
        with sync_playwright() as playwright:
            for engine in ("webkit", "chromium"):
                browser = getattr(playwright, engine).launch(
                    **({"channel": "msedge"} if engine == "chromium" else {})
                )
                for kind in ("mac", "ipad"):
                    context = browser.new_context(
                        service_workers="block",
                        viewport={
                            "width": 1440 if kind == "mac" else 1180,
                            "height": 900 if kind == "mac" else 820,
                        },
                        has_touch=kind == "ipad",
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "Version/26.0 Safari/605.1"
                        ),
                    )
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
                    page.add_init_script(
                        "Object.defineProperty(navigator,'maxTouchPoints',{get:()=>"
                        + ("5" if kind == "ipad" else "0")
                        + "}); Object.defineProperty(navigator,'standalone',{get:()=>"
                        + ("true" if kind == "ipad" else "false")
                        + "});"
                    )
                    item = dict(
                        id="a" * 64,
                        name="Synthetic landscape",
                        filename="clip.mp4",
                        duration=600,
                        size=1000,
                        width=1920,
                        height=1080,
                        codec="h264",
                    )

                    def route(request, _request=None, item=item):
                        path = request.request.url.split(f":{server.server_port}", 1)[-1]
                        value = {}
                        if path == "/api/session":
                            value = dict(
                                paired=True,
                                notifications_on=True,
                                pc_name="Synthetic PC",
                                share_limit_bytes=900000000,
                                devices=[dict(label="Mac, Safari 26", created="2026-11-03")],
                            )
                        elif path == "/api/library":
                            value = {
                                "items": [
                                    {**item, "id": f"{number:064x}", "name": f"Synthetic {number}"}
                                    for number in range(500)
                                ]
                            }
                        elif path == "/api/storage":
                            value = dict(
                                total=100000, free=50000, library_bytes=5000, drive_label="Test"
                            )
                        elif path.endswith("storyboard.json"):
                            value = dict(interval=3, width=160, height=90, frames=200, sheets=2)
                        elif path.endswith(".jpg"):
                            return request.fulfill(
                                body=(
                                    '<svg xmlns="http://www.w3.org/2000/svg" '
                                    'width="1600" height="900">'
                                    + "".join(
                                        f'<rect x="{n % 10 * 160}" y="{n // 10 * 90}" '
                                        f'width="160" height="90" fill="rgb({n * 2},80,140)"/>'
                                        f'<text x="{n % 10 * 160 + 20}" y="{n // 10 * 90 + 50}" '
                                        f'fill="white" font-size="30">{n}</text>'
                                        for n in range(100)
                                    )
                                    + "</svg>"
                                ),
                                content_type="image/svg+xml",
                            )
                        elif path.endswith("/video"):
                            return request.fulfill(status=404, body="")
                        request.fulfill(json=value)

                    page.route("**/api/**", route)
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    expect(page.locator(".video-row")).to_have_count(500)
                    expect(page.locator(".poster").first).to_be_visible()
                    assert page.locator(".poster").first.get_attribute("loading") == "lazy"
                    page.locator(".video-row").first.click()
                    expect(page.locator(".player-controls")).to_be_visible()
                    expect(page.get_by_role("slider", name="Volume")).to_have_count(
                        1 if kind == "mac" else 0
                    )
                    seek = page.get_by_role("slider", name="Seek")
                    seek.evaluate("el=>el.scrollIntoView({block: 'center'})")
                    box = seek.bounding_box()
                    assert box is not None
                    page.mouse.move(box["x"] + box["width"] * 0.51, box["y"] + box["height"] / 2)
                    expect(page.locator(".seek-preview")).to_be_visible()
                    expect(page.locator(".preview-image")).to_be_visible()
                    assert "storyboard/1.jpg" in page.locator(".preview-image").evaluate(
                        "el=>el.style.backgroundImage"
                    )
                    page.mouse.down()
                    page.mouse.move(box["x"] + box["width"] - 1, box["y"] + box["height"] / 2)
                    expect(page.locator(".seek-preview")).to_be_visible()
                    preview = page.locator(".seek-preview").bounding_box()
                    player = page.locator(".player").bounding_box()
                    assert preview["x"] >= player["x"] - 1
                    assert preview["x"] + preview["width"] <= player["x"] + player["width"] + 1
                    page.mouse.up()
                    if kind == "ipad":
                        # Dispatch a touch pointer through the actual control handlers.
                        seek.evaluate("el=>el.setPointerCapture=()=>{}")
                        seek.dispatch_event(
                            "pointerdown",
                            {"pointerId": 1, "pointerType": "touch", "clientX": box["x"] + 10},
                        )
                        expect(page.locator(".seek-preview")).to_be_visible()
                        seek.dispatch_event(
                            "pointercancel", {"pointerId": 1, "pointerType": "touch"}
                        )
                    if kind == "mac":
                        page.evaluate("""() => {
                          const v=document.querySelector('video'); window.keys=[];
                          Object.defineProperty(v,'readyState',{get:()=>1});
                          Object.defineProperty(v,'duration',{get:()=>600});
                          Object.defineProperty(v,'paused',{get:()=>!window.playing});
                          v.currentTime=20;
                          v.play=async()=>{window.playing=true; window.keys.push('play')};
                          v.pause=()=>{window.playing=false; window.keys.push('pause')}; }""")
                        page.locator(".player").focus()
                        page.keyboard.press("ArrowRight")
                        assert page.locator("video").evaluate("v=>v.currentTime") == 25
                        page.keyboard.press("ArrowLeft")
                        assert page.locator("video").evaluate("v=>v.currentTime") == 20
                        page.keyboard.press("Space")
                        page.keyboard.press("Space")
                        assert page.evaluate("window.keys") == ["play", "pause"]
                        seek.focus()
                        page.keyboard.press("ArrowRight")
                        assert page.locator("video").evaluate("v=>v.currentTime") == 25
                    page.screenshot(path=str(evidence / f"{engine}-{kind}.png"))
                    if kind == "mac":
                        page.route(
                            "**/api/session",
                            lambda route: route.fulfill(
                                json={"paired": False, "pairing_open": True}
                            ),
                        )
                        page.reload()
                        assert page.evaluate("navigator.standalone") is False
                        expect(
                            page.get_by_role("button", name="Pair this device", exact=True)
                        ).to_be_visible()
                    assert not errors, errors
                    results.append(
                        dict(
                            engine=engine,
                            platform=kind,
                            status="PASS",
                            playback="NOT_RUN: poster-only smoke",
                        )
                    )
                    context.close()
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        (evidence / "browser.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().work.resolve(strict=True)), indent=2))
