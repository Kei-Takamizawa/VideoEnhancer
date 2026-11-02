"""Scratch-only Windows WebKit smoke; invoke directly, outside CPU pytest collection."""

from __future__ import annotations

import argparse
import json
import os
import struct
import zlib
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from videoenhancer import proc
from videoenhancer.config import executable
from videoenhancer.remote.gateway import Gateway


def first_pixel(path: Path) -> list[int]:
    """Measure the first actual screenshot pixel without a graphics dependency."""
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    offset, compressed = 8, b""
    depth = color = None
    while offset < len(raw):
        size = struct.unpack(">I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        data = raw[offset + 8 : offset + 8 + size]
        if kind == b"IHDR":
            _, _, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", data)
            assert depth == 8 and color in {2, 6} and interlace == 0
        if kind == b"IDAT":
            compressed += data
        offset += size + 12
    decoded = zlib.decompress(compressed)
    # Every PNG filter has zero left/up neighbours for the first pixel.
    assert decoded[0] in {0, 1, 2, 3, 4}
    return list(decoded[1:4])


def run(work: Path, ffmpeg: str | None = None) -> dict:
    work = work.resolve(strict=True)
    scratch = (work / "scratch" / "r1a-browser").resolve()
    evidence = (work / "evidence" / "VE-R1a").resolve()
    assert scratch.is_relative_to(work / "scratch")
    assert evidence.is_relative_to(work / "evidence")
    home, library = scratch / "home", scratch / "library"
    home.mkdir(parents=True, exist_ok=True)
    library.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    os.environ["VE_HOME"] = str(home)
    os.environ["TEMP"] = os.environ["TMP"] = str(scratch / "tmp")
    (scratch / "tmp").mkdir(exist_ok=True)
    if ffmpeg is None:
        try:
            ffmpeg = executable("ffmpeg")
        except FileNotFoundError:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for name, color in [("R1a sample A.mp4", "blue"), ("R1a sample B.mp4", "green")]:
        proc.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=640x360:r=24",
                "-t",
                "2",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(library / name),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
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
        "browser": "Playwright WebKit on Windows",
        "checks": {},
        "limitations": [
            "Standalone pairing is emulated; actual Home Screen pairing is an owner check.",
            "Disposable browser context ignores TLS errors; iPad CA trust is an owner check.",
            "Cookie retention after restart and 24 hours, and 1 GB iPad sharing are NOT_RUN.",
        ],
    }
    gateway.start()
    gateway.open_pairing()
    # Use a certificate hostname as Host while routing only to loopback.
    address = gateway.certificates.addresses[0] if gateway.certificates.addresses else None
    if not address:
        raise RuntimeError("Browser smoke needs one certificate IPv4 address.")
    base = f"https://{address}:{gateway.https_port}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.webkit.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 834, "height": 1194},
                device_scale_factor=1,
                is_mobile=True,
                has_touch=True,
                ignore_https_errors=True,
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'standalone', {get: () => true})"
            )

            def local_only(route):
                if urlsplit(route.request.url).netloc == urlsplit(base).netloc:
                    route.continue_()
                else:
                    route.abort()

            context.route("**/*", local_only)
            page = context.new_page()
            errors = []
            media_requests = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "response",
                lambda result: (
                    media_requests.append(
                        {"status": result.status, "range": result.request.headers.get("range")}
                    )
                    if urlsplit(result.url).path.endswith("/video")
                    else None
                ),
            )
            page.goto(base + "/")
            print("Loaded pairing page", flush=True)
            expect(page.get_by_role("heading", name="Pair your iPad")).to_be_visible()
            page.get_by_role("button", name="Pair this iPad", exact=True).click()
            expect(page.get_by_role("heading", name="Library", exact=True)).to_be_visible()
            expect(page.locator(".video-row")).to_have_count(2)
            expect(page.locator(".storage-bar")).to_be_visible()
            initial_storage = page.locator(".storage-bar").get_attribute("aria-label")
            initial_bytes = page.evaluate(
                "fetch('/api/storage').then(r => r.json()).then(s => s.library_bytes)"
            )
            library_image = evidence / "library.png"
            page.screenshot(path=str(library_image), full_page=True)
            report["checks"]["pair_and_library"] = "PASS"
            print("Paired; library screenshot saved", flush=True)
            page.get_by_role("button", name="R1a sample A", exact=False).click()
            expect(page.locator("video")).to_be_visible()
            item_image = evidence / "item.png"
            page.screenshot(path=str(item_image), full_page=True)
            print("Item screenshot saved; starting playback", flush=True)
            try:
                page.locator("video").evaluate(
                    """video => {
                        video.muted = true;
                        return Promise.race([video.play(), new Promise((_, reject) =>
                            setTimeout(() => reject(new Error('Playback timeout')), 15000))]);
                    }"""
                )
                page.wait_for_function(
                    "document.querySelector('video').currentTime > 0.1", timeout=15000
                )
                report["checks"]["playback"] = "PASS"
                print("Playback started", flush=True)
            except Exception as error:
                report["checks"]["playback"] = "FAIL"
                report["playback_error"] = str(error)
                report["media_diagnostics"] = page.locator("video").evaluate(
                    """video => ({readyState: video.readyState, networkState: video.networkState,
                        error: video.error ? {
                            code: video.error.code, message: video.error.message} : null,
                        h264Baseline: video.canPlayType('video/mp4; codecs="avc1.42E01E"'),
                        h264High: video.canPlayType('video/mp4; codecs="avc1.64001E"'),
                        mp4: video.canPlayType('video/mp4')})"""
                )
                report["media_requests"] = list(media_requests)
                print(
                    "Playback FAIL; retaining diagnostics and continuing independent checks",
                    flush=True,
                )
            # Close the video resource before deleting; the in-use refusal is separately tested.
            page.locator("video").evaluate(
                "video => { video.pause(); video.removeAttribute('src'); video.load(); }"
            )
            page.evaluate(
                """() => {
                    window.testShares = [];
                    Object.defineProperty(navigator, 'canShare', {configurable: true,
                        value: () => true});
                    Object.defineProperty(navigator, 'share', {configurable: true,
                        value: async ({files}) => {
                            window.testShares.push({name: files[0].name, size: files[0].size});
                            throw new DOMException('Cancelled', 'AbortError');
                        }});
                }"""
            )
            before_download = len(media_requests)
            page.get_by_role("button", name="Download", exact=True).click()
            expect(page.get_by_role("button", name="Save video", exact=True)).to_be_visible()
            page.get_by_role("button", name="Save video", exact=True).click()
            expect(page.get_by_role("button", name="Download", exact=True)).to_be_visible()
            assert page.evaluate("window.testShares.length") == 1
            assert (
                page.evaluate("window.testShares[0].size")
                == initial_bytes - (library / "R1a sample B.mp4").stat().st_size
            )
            assert len(media_requests) == before_download + 1
            expect(page.get_by_text("This video could not be shared.", exact=False)).to_have_count(
                0
            )
            report["checks"]["blob_download_and_simulated_share_cancel"] = "PASS"
            page.get_by_role("button", name="Delete", exact=True).click()
            expect(page.locator("#delete-description")).to_contain_text("R1a sample A")
            page.get_by_role("button", name="Delete permanently").click()
            expect(page.locator(".video-row")).to_have_count(1)
            expect(page.locator(".storage-bar")).to_be_visible()
            final_bytes = page.evaluate(
                "fetch('/api/storage').then(r => r.json()).then(s => s.library_bytes)"
            )
            assert final_bytes < initial_bytes
            report["checks"]["delete_and_storage_refresh"] = "PASS"
            report["storage"] = {
                "initial_bytes": initial_bytes,
                "final_bytes": final_bytes,
                "initial_text": initial_storage,
                "final_text": page.locator(".storage-bar").get_attribute("aria-label"),
            }
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.set_viewport_size({"width": 1194, "height": 834})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            report["checks"]["portrait_landscape_no_horizontal_scroll"] = "PASS"
            page.get_by_role("button", name="Settings", exact=True).click()
            expect(page.get_by_role("heading", name="Settings", exact=True)).to_be_visible()
            expect(page.locator("dl")).to_contain_text("This iPad is paired since")
            report["checks"]["settings"] = "PASS"
            report["background_pixels"] = {
                "library": first_pixel(library_image),
                "item": first_pixel(item_image),
            }
            assert all(pixel == [0, 0, 0] for pixel in report["background_pixels"].values())
            report["checks"]["screenshot_black_background"] = "PASS"
            assert not errors, errors
            report["checks"]["page_errors"] = "PASS"
            context.close()
            browser.close()
        if report["checks"].get("playback") != "PASS":
            raise AssertionError("WebKit playback gate failed; see media diagnostics.")
        return report
    except Exception as error:
        report["failure"] = f"{type(error).__name__}: {error}"
        print(report["failure"], flush=True)
        raise
    finally:
        (evidence / "browser-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--ffmpeg")
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.work, arguments.ffmpeg), indent=2))
