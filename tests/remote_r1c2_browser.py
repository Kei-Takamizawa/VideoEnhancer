"""Synthetic Settings pairing smoke; no connection to the owner's service."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def run():
    work = Path(__file__).resolve().parents[2]
    evidence = work / "evidence/VE-R1c-2"
    web = work / "repo/src/videoenhancer/remote/web"
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
                for kind, width, height in (("ipad", 820, 1180), ("mac", 1440, 900)):
                    context = browser.new_context(
                        service_workers="block",
                        viewport={"width": width, "height": height},
                        has_touch=kind == "ipad",
                    )
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
                    page.add_init_script(
                        "Object.defineProperty(navigator, 'clipboard', {value: "
                        "{writeText: async value => { window.copiedAddress = value; }}});"
                    )
                    state = dict(
                        paired=True,
                        pairing_open=False,
                        closes_at="1970-01-01T00:00:00+00:00",
                        setup_address="http://synthetic.local:8080/",
                        pc_name="Synthetic PC",
                        notifications_on=True,
                        devices=[dict(id="first", label="iPad", created="2026-11-03T12:00:00Z")],
                    )
                    opens = []

                    def route(route, _request=None, *, state=state, opens=opens):
                        path = route.request.url.split(f":{server.server_port}", 1)[-1]
                        value = {}
                        if path == "/api/session":
                            value = state
                        elif path == "/api/pair/open":
                            assert route.request.method == "POST"
                            assert route.request.post_data == "{}"
                            opens.append(True)
                            state["pairing_open"] = True
                            state["closes_at"] = (
                                datetime.now(UTC) + timedelta(seconds=120)
                            ).isoformat()
                            value = {"closes_at": state["closes_at"]}
                        elif path == "/api/library":
                            value = {"items": []}
                        elif path == "/api/storage":
                            value = dict(total=1000, free=500, library_bytes=0, drive_label="Test")
                        route.fulfill(json=value)

                    page.route("**/api/**", route)
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    page.get_by_role("button", name="Settings", exact=True).click()
                    opening = page.get_by_role("button", name="Add a new device", exact=True)
                    opening.click()
                    expect(
                        page.get_by_text("Pairing is open for 2:00.", exact=True)
                    ).to_be_visible()
                    expect(
                        page.get_by_text("Pairing is open for 1:59.", exact=True)
                    ).to_be_visible()
                    page.get_by_role("button", name="Copy address", exact=True).click()
                    expect(page.get_by_text("Address copied.", exact=True)).to_be_visible()
                    assert page.evaluate("window.copiedAddress") == state["setup_address"]
                    page.screenshot(
                        path=str(evidence / f"{engine}-{kind}-open.png"), full_page=True
                    )
                    page.reload()
                    page.get_by_role("button", name="Settings", exact=True).click()
                    expect(
                        page.get_by_role("button", name="Copy address", exact=True)
                    ).to_be_visible()
                    state["pairing_open"] = False
                    state["devices"].append(
                        dict(id="new", label="Mac, Safari 26", created="2026-11-03T12:00:00Z")
                    )
                    expect(
                        page.get_by_text("New device added: Mac, Safari 26.", exact=True)
                    ).to_be_visible()
                    expect(
                        page.get_by_text("Mac, Safari 26 · Paired November 3, 2026", exact=True)
                    ).to_be_visible()
                    opening = page.get_by_role("button", name="Add a new device", exact=True)
                    opening.click()
                    expect(opening).to_be_disabled()
                    expect(
                        page.get_by_text("Pairing is open for 2:00.", exact=True)
                    ).to_be_visible()
                    state["pairing_open"] = False
                    expect(page.get_by_text("Pairing closed.", exact=True)).to_be_visible()
                    expect(opening).to_be_enabled()
                    assert len(opens) == 2
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert not errors, errors
                    results.append(dict(engine=engine, viewport=kind, status="PASS"))
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
