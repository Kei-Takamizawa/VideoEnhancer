"""Isolate WebKit media transport versus Blob playback without changing product behavior."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from videoenhancer.remote.gateway import Gateway


def diagnose(work: Path) -> dict:
    work = work.resolve(strict=True)
    scratch = (work / "scratch" / "r1a-browser").resolve(strict=True)
    evidence = (work / "evidence" / "VE-R1a").resolve(strict=True)
    assert scratch.is_relative_to(work / "scratch")
    assert evidence.is_relative_to(work / "evidence")
    original = evidence / "browser-smoke-original.json"
    if not original.exists():
        original.write_bytes((evidence / "browser-smoke.json").read_bytes())
    gateway = Gateway(
        None,
        scratch / "home",
        {
            "remote_https_port": 0,
            "remote_setup_port": 0,
            "library_folder": str(scratch / "library"),
        },
    )
    result = {
        "time": datetime.now(UTC).isoformat(),
        "browser": "Windows Playwright WebKit",
        "context_routing": False,
        "ignore_https_errors": True,
        "original_required_stream_gate": "FAIL (unchanged)",
    }
    gateway.start()
    gateway.open_pairing()
    address = gateway.certificates.addresses[0]
    base = f"https://{address}:{gateway.https_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.webkit.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 834, "height": 1194},
                is_mobile=True,
                has_touch=True,
                ignore_https_errors=True,
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'standalone', {get: () => true})"
            )
            page = context.new_page()
            media_events = []
            page.on(
                "response",
                lambda response: (
                    media_events.append(
                        {
                            "event": "response",
                            "status": response.status,
                            "range": response.request.headers.get("range"),
                        }
                    )
                    if response.url.endswith("/video")
                    else None
                ),
            )
            page.on(
                "requestfailed",
                lambda request: (
                    media_events.append({"event": "requestfailed", "failure": request.failure})
                    if request.url.endswith("/video")
                    else None
                ),
            )
            page.goto(base + "/")
            page.get_by_role("button", name="Pair this iPad", exact=True).click()
            expect(page.locator(".video-row")).to_have_count(1)
            page.locator(".video-row").click()
            expect(page.locator("video")).to_be_visible()
            result["stream_without_routing"] = page.locator("video").evaluate(
                """async video => {
                    video.muted = true;
                    const snapshot = () => ({currentTime: video.currentTime,
                        readyState: video.readyState, networkState: video.networkState,
                        error: video.error ? {code: video.error.code,
                            message: video.error.message} : null});
                    try {
                        await Promise.race([video.play(), new Promise((_, reject) =>
                            setTimeout(() => reject(new Error('Playback timeout')), 15000))]);
                        await new Promise(resolve => setTimeout(resolve, 500));
                        return {status: video.currentTime > 0.1 ? 'PASS' : 'FAIL', ...snapshot()};
                    } catch (error) {
                        return {status: 'FAIL', failure: error.name + ': ' + error.message,
                            ...snapshot()};
                    }
                }"""
            )
            result["stream_events"] = list(media_events)
            media_events.clear()
            result["blob_playback"] = page.locator("video").evaluate(
                """async video => {
                    const original = video.currentSrc || video.src;
                    video.pause(); video.removeAttribute('src'); video.load();
                    let objectURL;
                    const abort = new AbortController();
                    const timer = setTimeout(() => abort.abort(), 15000);
                    try {
                        const response = await fetch(original, {
                            cache: 'no-store', signal: abort.signal});
                        if (!response.ok) throw new Error('HTTP ' + response.status);
                        const blob = await response.blob();
                        objectURL = URL.createObjectURL(blob);
                        video.src = objectURL;
                        video.muted = true;
                        await Promise.race([video.play(), new Promise((_, reject) =>
                            setTimeout(() => reject(new Error('Blob playback timeout')), 15000))]);
                        await new Promise(resolve => setTimeout(resolve, 500));
                        return {status: video.currentTime > 0.1 ? 'PASS' : 'FAIL',
                            currentTime: video.currentTime, bytes: blob.size, type: blob.type,
                            readyState: video.readyState};
                    } catch (error) {
                        return {status: 'FAIL', failure: error.name + ': ' + error.message,
                            readyState: video.readyState, networkState: video.networkState,
                            error: video.error ? {code: video.error.code,
                                message: video.error.message} : null};
                    } finally {
                        clearTimeout(timer);
                        video.pause(); video.removeAttribute('src'); video.load();
                        if (objectURL) URL.revokeObjectURL(objectURL);
                    }
                }"""
            )
            result["blob_events"] = list(media_events)
            context.close()
            browser.close()
        return result
    finally:
        output = evidence / "browser-playback-diagnostics.json"
        previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else []
        previous.append(result)
        output.write_text(json.dumps(previous, indent=2), encoding="utf-8")
        gateway.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(diagnose(args.work), indent=2))
