"""Isolated R1b WebKit UI smoke with synthetic, browser-routed backend responses.

Invoke directly; this is deliberately outside CPU pytest collection.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

from videoenhancer.remote.gateway import Gateway

BROWSER_MOCKS = """
Object.defineProperty(navigator, 'standalone', {get: () => true});
Object.defineProperty(navigator, 'clipboard', {value: {
  readText: async () => { throw new DOMException('Denied', 'NotAllowedError'); }
}});
window.testPermissions = [];
window.Notification = {requestPermission: async () => {
  window.testPermissions.push('requested'); return 'granted';
}};
window.PushManager = function() {};
const nativeFetch = window.fetch.bind(window);
window.fetch = async (url, options) => {
  if (options?.method === 'PUT' && String(url).includes('/chunk?')) {
    if (!(options.body instanceof Blob) || options.body.size > 4194304) {
      throw new Error('Expected bounded Blob chunk.');
    }
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(options.body);
    });
    const result = await window.syntheticChunk(String(url), data);
    return new Response(JSON.stringify(result), {headers: {'Content-Type': 'application/json'}});
  }
  return nativeFetch(url, options);
};
const subscription = {toJSON: () => ({endpoint: 'https://web.push.apple.com/synthetic',
  keys: {p256dh: 'synthetic', auth: 'synthetic'}})};
Object.defineProperty(navigator, 'serviceWorker', {value: {
  register: async () => ({}),
  ready: Promise.resolve({pushManager: {
    getSubscription: async () => null,
    subscribe: async () => subscription,
  }}),
}});
"""


def run(work: Path) -> dict:
    work = work.resolve(strict=True)
    scratch = (work / "scratch/r1b-browser" / uuid.uuid4().hex[:12]).resolve()
    evidence = (work / "evidence/VE-R1b").resolve()
    assert scratch.is_relative_to(work / "scratch")
    assert evidence.is_relative_to(work / "evidence")
    home, library, temporary = scratch / "home", scratch / "library", scratch / "temp"
    for folder in (home, library, temporary, evidence):
        folder.mkdir(parents=True, exist_ok=True)
    os.environ.update(VE_HOME=str(home), TEMP=str(temporary), TMP=str(temporary))
    gateway = Gateway(
        None,
        home,
        {
            "remote_https_port": 0,
            "remote_setup_port": 0,
            "library_folder": str(library),
        },
    )
    report = {
        "browser": "Playwright WebKit on Windows, 834x1194 touch viewport",
        "backend": "Real isolated TLS/static gateway and pairing; R1b APIs browser-mocked",
        "checks": {},
        "limitations": [
            "Synthetic API responses do not establish engine, estimator or upload correctness.",
            "Notification permission and PushManager are browser mocks; no push service contacted.",
            "iPad Home Screen, CA trust, Apple permission and push delivery are owner checks.",
        ],
    }
    checks = report["checks"]
    state = {"paired": False, "notifications": False, "offset": 0, "size": 0, "ready": False}
    calls, errors, console_errors, external = [], [], [], []
    screenshot_warnings = []
    upload_bytes = bytearray()
    finish = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    entry = {
        "key": "sample",
        "title": "Synthetic link video",
        "duration": 12,
        "width": 1920,
        "height": 1080,
        "format_id": "test",
        "estimate": {"finish": finish, "seconds": 300, "low": 250, "high": 350},
    }
    gateway.start()
    gateway.open_pairing()
    address = gateway.certificates.addresses[0]
    base = f"https://{address}:{gateway.https_port}"
    previous_cwd = Path.cwd()
    try:
        # Windows WebKit also writes networking databases relative to its process cwd.
        os.chdir(scratch)
        with sync_playwright() as playwright:
            context = playwright.webkit.launch_persistent_context(
                str(scratch / "profile"),
                headless=True,
                viewport={"width": 834, "height": 1194},
                device_scale_factor=1,
                is_mobile=True,
                has_touch=True,
                ignore_https_errors=True,
            )

            def synthetic_chunk(path, encoded):
                offset = int(parse_qs(urlsplit(path).query)["offset"][0])
                assert offset == state["offset"]
                chunk = base64.b64decode(encoded, validate=True)
                assert 0 < len(chunk) <= 4194304
                upload_bytes.extend(chunk)
                state["offset"] += len(chunk)
                calls.append(("PUT", "/api/uploads/upload1/chunk"))
                return {"offset": state["offset"]}

            context.expose_function("syntheticChunk", synthetic_chunk)
            context.add_init_script(BROWSER_MOCKS)

            def routes(route):
                request = route.request
                url = urlsplit(request.url)
                if url.netloc != urlsplit(base).netloc:
                    external.append(request.url)
                    return route.abort()
                path = url.path
                if not path.startswith("/api/"):
                    return route.continue_()
                calls.append((request.method, path))
                body = request.post_data_json if request.method == "POST" else None
                status = 200
                value = {}
                if path == "/api/pair/claim":
                    state["paired"] = True
                    return route.continue_()
                if path == "/api/session":
                    value = {
                        "paired": state["paired"],
                        "pairing_open": True,
                        "pc_name": "Synthetic PC",
                        "addresses": [address],
                        "paired_at": "2026-11-02T12:00:00Z",
                        "push_key": "BAAA",
                        "notifications_on": state["notifications"],
                    }
                elif path == "/api/library":
                    value = {"items": []}
                elif path == "/api/storage":
                    value = {
                        "total": 100_000_000_000,
                        "free": 80_000_000_000,
                        "library_bytes": 0,
                        "drive_label": "Test",
                    }
                elif path == "/api/jobs/active":
                    value = {"jobs": []}
                elif path == "/api/link-tools":
                    value = {"available": True}
                elif path == "/api/links/check":
                    assert body == {"url": "https://example.test/synthetic"}
                    value = {"id": "check1", "state": "running"}
                elif path == "/api/links/check/check1":
                    value = {"id": "check1", "state": "done", "entries": [entry]}
                elif path == "/api/estimate":
                    upload = "upload_id" in body
                    value = {
                        "entries": [
                            {
                                **entry,
                                "key": "upload1" if upload else "sample",
                                "title": "Synthetic upload" if upload else entry["title"],
                            }
                        ]
                    }
                elif path == "/api/jobs":
                    assert body in (
                        {"check_id": "check1", "entry_keys": ["sample"]},
                        {"upload_id": "upload1"},
                    )
                    value = {"added": [{"id": "job1"}]}
                elif path == "/api/uploads":
                    state["size"] = body["size"]
                    value = {
                        "id": "upload1",
                        "name": body["name"],
                        "size": state["size"],
                        "offset": 0,
                        "ready": False,
                    }
                elif path == "/api/uploads/upload1":
                    value = {
                        "id": "upload1",
                        "size": state["size"],
                        "offset": state["offset"],
                        "ready": state["ready"],
                    }
                elif path == "/api/uploads/upload1/chunk":
                    offset = int(parse_qs(url.query)["offset"][0])
                    assert offset == state["offset"]
                    chunk = request.post_data_buffer
                    assert 0 < len(chunk) <= 4 * 1024 * 1024
                    upload_bytes.extend(chunk)
                    state["offset"] += len(chunk)
                    value = {"offset": state["offset"]}
                elif path == "/api/uploads/upload1/finish":
                    assert state["offset"] == state["size"]
                    assert body["sha256"] == hashlib.sha256(upload_bytes).hexdigest()
                    state["ready"] = True
                    value = {"id": "upload1", "offset": state["offset"], "ready": True}
                elif path == "/api/push/subscribe":
                    assert body["endpoint"] == "https://web.push.apple.com/synthetic"
                    state["notifications"] = True
                    value = {"ok": True}
                elif path == "/api/push/test":
                    assert state["notifications"]
                    value = {"ok": True, "status": 201}
                else:
                    status, value = 404, {"error": "Unexpected synthetic API request."}
                route.fulfill(
                    status=status, content_type="application/json", body=json.dumps(value)
                )

            context.route("**/*", routes)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )

            def capture(name):
                before = len(console_errors)
                page.screenshot(path=str(evidence / name), full_page=True, caret="initial")
                added = console_errors[before:]
                # WebKit screenshot synchronization injects `style {body {}}`.
                # The shipped CSP must reject it; keep and account for that diagnostic.
                expected = (
                    "Refused to apply a stylesheet because its hash, its nonce, "
                    "or 'unsafe-inline' does not appear in the style-src directive "
                    "of the Content Security Policy."
                )
                assert added in ([], [expected]), added
                screenshot_warnings.extend(added)

            page.goto(base + "/")
            expect(page.get_by_role("heading", name="Pair your iPad")).to_be_visible()
            page.get_by_role("button", name="Pair this iPad", exact=True).click()
            expect(page.get_by_role("heading", name="Library", exact=True)).to_be_visible()
            assert len(gateway.devices.devices) == 1
            checks["isolated_pairing"] = "PASS"
            expect(page.get_by_role("button", name="Add", exact=True)).to_be_visible()
            page.get_by_role("button", name="Add", exact=True).click()
            expect(page.get_by_role("heading", name="Paste a link")).to_be_visible()
            expect(page.get_by_role("heading", name="Upload a video")).to_be_visible()
            checks["add_tab_and_cards"] = "PASS"
            page.get_by_role("button", name="Paste", exact=True).click()
            expect(
                page.get_by_text("Touch and hold the Video URL field, then tap Paste.")
            ).to_be_visible()
            checks["clipboard_denial_fallback"] = "PASS"
            page.get_by_label("Video URL").fill("https://example.test/synthetic")
            page.get_by_role("button", name="Check link", exact=True).click()
            expect(page.get_by_text("Synthetic link video", exact=True)).to_be_visible()
            expect(page.get_by_role("checkbox")).to_be_checked()
            expect(page.locator(".playlist-row")).to_contain_text("1920 × 1080")
            expect(page.locator(".playlist-row")).to_contain_text("Ready about")
            expect(page.get_by_role("button", name="Add", exact=True).first).to_be_enabled()
            capture("r1b-add-link.png")
            page.get_by_role("button", name="Add", exact=True).first.click()
            expect(
                page.get_by_text("Added. You'll get a notification when it's ready.")
            ).to_be_visible()
            checks["link_check_estimate_add_banner"] = "PASS"
            capture("r1b-library-banner.png")
            page.get_by_role("button", name="Add", exact=True).click()
            payload = b"synthetic upload bytes\x00" * 250000
            page.get_by_label("Choose from Photos or Files").set_input_files(
                {
                    "name": "Synthetic upload.mp4",
                    "mimeType": "video/mp4",
                    "buffer": payload,
                }
            )
            expect(page.get_by_text("Synthetic upload.mp4 ·", exact=False)).to_be_visible(
                timeout=30000
            )
            expect(page.get_by_role("button", name="Add", exact=True).first).to_be_enabled()
            assert bytes(upload_bytes) == payload
            assert sum(path.endswith("/chunk") for _, path in calls) == 2
            checks["two_chunk_upload_hash_estimate"] = "PASS"
            capture("r1b-add-upload.png")
            expect(
                page.get_by_text("Keep this app open. This iPad could not save", exact=False)
            ).to_have_count(0)
            page.reload()
            expect(page.get_by_role("heading", name="Library", exact=True)).to_be_visible()
            page.get_by_role("button", name="Add", exact=True).click()
            page.get_by_role("button", name="Resume upload", exact=False).click()
            expect(page.get_by_text("Synthetic upload.mp4 ·", exact=False)).to_be_visible()
            assert bytes(upload_bytes) == payload
            checks["indexeddb_file_survives_reload_and_resumes"] = "PASS"
            page.get_by_role("button", name="Add", exact=True).first.click()
            expect(page.get_by_role("heading", name="Library", exact=True)).to_be_visible()
            expect(
                page.get_by_text("Added. You'll get a notification when it's ready.")
            ).to_be_visible()
            checks["upload_add_banner"] = "PASS"
            page.get_by_role("button", name="Turn on notifications", exact=True).click()
            expect(
                page.get_by_role("button", name="Turn on notifications", exact=True)
            ).to_have_count(0)
            assert page.evaluate("window.testPermissions") == ["requested"]
            checks["tap_permission_subscribe_card_hidden_mocked"] = "PASS"
            page.get_by_role("button", name="Settings", exact=True).click()
            expect(page.get_by_text("Notifications are on for this iPad.")).to_be_visible()
            page.get_by_role("button", name="Send a test notification", exact=True).click()
            expect(page.get_by_text("Test notification sent.")).to_be_visible()
            checks["settings_notification_test_mocked"] = "PASS"
            for width, height in [(834, 1194), (1194, 834), (320, 800)]:
                page.set_viewport_size({"width": width, "height": height})
                page.get_by_role("button", name="Add", exact=True).click()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            checks["add_portrait_landscape_narrow_no_horizontal_scroll"] = "PASS"
            assert not errors, errors
            assert console_errors == screenshot_warnings, console_errors
            assert not external, external
            checks["no_application_errors_no_external_requests"] = "PASS"
            report["expected_screenshot_csp_rejections"] = len(screenshot_warnings)
            report["upload"] = {
                "bytes": len(upload_bytes),
                "chunks": 2,
                "sha256": hashlib.sha256(upload_bytes).hexdigest(),
            }
            report["screenshots"] = [
                str(evidence / name)
                for name in ("r1b-add-link.png", "r1b-library-banner.png", "r1b-add-upload.png")
            ]
            context.close()
        return report
    except Exception as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["page_errors"] = errors
        report["console_errors"] = console_errors
        (evidence / "r1b-browser-smoke.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        gateway.close()
        os.chdir(previous_cwd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.work), indent=2))
