"""Run reproducible LAN WebKit checks and TLS-verified loopback baselines."""

import argparse
import asyncio
import hashlib
import json
import socket
import ssl
import time

import aiohttp
from playwright.async_api import async_playwright, expect
from server import WORK, private_addresses, serve


async def verify():
    home = WORK / "scratch" / "ipad-pc-check"
    evidence = WORK / "evidence" / "VE-R0b"
    report = {
        "device": "PC automation (iPad Pro 11 viewport)",
        "browser": "WebKit Windows",
        "checks": {},
    }
    if not (home / "media" / "1GB.mp4").is_file():
        raise SystemExit(
            "Generate samples with --home work/scratch/ipad-pc-check first (see README)"
        )
    # This fixed PC-test home is separate from the owner's default spike home.
    for path in (home / "uploads").glob("*"):
        path.unlink()
    lan = private_addresses()[0]
    task = asyncio.create_task(
        serve(
            argparse.Namespace(
                home=home,
                bind=[lan, "127.0.0.1"],
                redo_pairing=True,
                pair_seconds=120,
                no_mdns=False,
                automated=True,
            )
        )
    )
    try:
        for _ in range(100):
            if task.done():
                await task
            try:
                reader, writer = await asyncio.open_connection(lan, 8080)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(0.1)
        tls = ssl.create_default_context(cafile=str(home / "ca.crt"))

        def resolve_name(name):
            try:
                return socket.gethostbyname_ex(name)[2]
            except OSError as exc:
                return type(exc).__name__

        report["name_resolution"] = {
            name: await asyncio.to_thread(resolve_name, name)
            for name in ["videoenhancer.local", socket.gethostname().lower() + ".local"]
        }
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=tls)) as session:
            async with session.get(f"https://{lan}:8443/") as response:
                assert response.status == 200
            report["checks"]["python_CA_verified_LAN"] = "PASS"
        async with async_playwright() as p:
            browser = await p.webkit.launch(headless=True, downloads_path=str(home / "downloads"))
            strict = await browser.new_context(**p.devices["iPad Pro 11"])
            page = await strict.new_page()
            try:
                await page.goto(f"https://{lan}:8443/", timeout=15000)
                report["checks"]["browser_untrusted_CA"] = "Unexpectedly accepted"
            except Exception as exc:
                report["checks"]["browser_untrusted_CA"] = str(exc).split("\n")[0]
            await strict.close()
            # Playwright exposes ignore_https_errors, not a per-context root CA store.
            # Keep this diagnostic separate from certificate trust validation above.
            context = await browser.new_context(
                **{**p.devices["iPad Pro 11"], "user_agent": "VideoEnhancer PC automation"},
                ignore_https_errors=True,
                accept_downloads=True,
            )

            async def local_only(route):
                from urllib.parse import urlsplit

                if urlsplit(route.request.url).hostname != lan and not route.request.url.startswith(
                    f"blob:https://{lan}:8443/"
                ):
                    await route.abort()
                else:
                    await route.continue_()

            await context.route("**/*", local_only)
            page = await context.new_page()
            errors = []
            media_responses = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "requestfailed",
                lambda r: errors.append(
                    "requestfailed " + r.url.split("?")[0] + ": " + str(r.failure)
                ),
            )
            page.on(
                "response",
                lambda r: (
                    media_responses.append({"path": r.url.split("?")[0], "status": r.status})
                    if "/media/" in r.url
                    else None
                ),
            )
            report["page_errors"] = errors
            report["media_responses"] = media_responses
            await page.goto(f"https://{lan}:8443/")
            await page.locator("#pair-app").click()
            await expect(page.locator("#status")).to_contain_text("Ready", timeout=30000)
            assert (await context.cookies())[0]["secure"]
            report["checks"]["pairing"] = "PASS"
            await page.locator("#files").set_input_files(str(home / "media" / "h264.mp4"))
            await expect(page.locator("#results")).to_contain_text('"test": "T4"', timeout=120000)
            report["upload"] = json.JSONDecoder().raw_decode(
                await page.locator("#results").inner_text()
            )[0]
            assert report["upload"]["hash_matches"] and report["upload"]["resume_ok"]
            report["checks"]["T4"] = "PASS"
            for codec in ["h264", "hevc", "av1"]:
                await page.locator(f'[data-codec="{codec}"]').click()
                await expect(page.locator("#results")).to_contain_text(
                    f'"codec": "{codec}"', timeout=70000
                )
                report[f"playback_{codec}"] = json.JSONDecoder().raw_decode(
                    await page.locator("#results").inner_text()
                )[0]
            report["checks"]["T5_H264"] = "PASS" if report["playback_h264"].get("pass") else "FAIL"
            report["can_play_type"] = await page.locator("#video").evaluate(
                "v => ({h264:v.canPlayType('video/mp4; codecs=\"avc1.64002a\"'),"
                "hevc:v.canPlayType('video/mp4; codecs=\"hvc1\"'),"
                "av1:v.canPlayType('video/mp4; codecs=\"av01.0.08M.08\"')})"
            )
            start = time.perf_counter()
            try:
                async with page.expect_download(timeout=15000) as info:
                    await page.locator('[data-download="foreground"]').click()
                download = await info.value
                path = home / "downloads" / "1GB.mp4"
                await download.save_as(path)
                elapsed = time.perf_counter() - start
                with path.open("rb") as f:
                    actual = hashlib.file_digest(f, "sha256").hexdigest()
                with (home / "media" / "1GB.mp4").open("rb") as f:
                    expected = hashlib.file_digest(f, "sha256").hexdigest()
                assert actual == expected
                report["download"] = {
                    "bytes": path.stat().st_size,
                    "seconds": elapsed,
                    "MB_s": path.stat().st_size / 1e6 / elapsed,
                    "hash_matches": True,
                }
                report["checks"]["T6_foreground"] = "PASS"
            except Exception as exc:
                report["checks"]["T6_foreground"] = "FAIL"
                report["download_error"] = str(exc)
            await page.screenshot(path=str(evidence / "webkit.png"), full_page=True)
            report["page_errors"] = errors
            cookies = await context.cookies()
            token = next(c["value"] for c in cookies if c["name"] == "ve_device")
            await context.close()
            await browser.close()
        headers = {"Authorization": "Bearer " + token}
        async with aiohttp.ClientSession(
            headers=headers, connector=aiohttp.TCPConnector(ssl=tls)
        ) as session:
            origin = "https://127.0.0.1:8443"
            source = home / "media" / "50MB.mp4"
            with source.open("rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            start = time.perf_counter()
            offset = 0
            with source.open("rb") as f:
                while chunk := f.read(4 * 1024 * 1024):
                    async with session.put(
                        f"{origin}/api/upload/{digest}?offset={offset}", data=chunk
                    ) as r:
                        assert r.status == 200
                        offset = (await r.json())["offset"]
            async with session.post(
                f"{origin}/api/upload/{digest}/finish", json={"size": offset}
            ) as r:
                assert r.status == 200
            elapsed = time.perf_counter() - start
            report["loopback_upload"] = {
                "bytes": offset,
                "seconds": elapsed,
                "MB_s": offset / 1e6 / elapsed,
                "includes_hash_check": True,
            }
            start = time.perf_counter()
            received = 0
            async with session.get(origin + "/media/1GB.mp4?download=1&run=loopback") as r:
                assert r.status == 200
                async for chunk in r.content.iter_chunked(1024 * 1024):
                    received += len(chunk)
            elapsed = time.perf_counter() - start
            report["loopback_download"] = {
                "bytes": received,
                "seconds": elapsed,
                "MB_s": received / 1e6 / elapsed,
            }
            assert received == (home / "media" / "1GB.mp4").stat().st_size
        report["checks"]["loopback"] = "PASS"
        if any(report["checks"].get(k) != "PASS" for k in ["T5_H264", "T6_foreground"]):
            raise AssertionError(
                "Required Windows WebKit playback/download gate failed; see results"
            )
    except Exception as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        (evidence / "pc-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    asyncio.run(verify())
