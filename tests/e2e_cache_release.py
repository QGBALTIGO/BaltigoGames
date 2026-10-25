"""Exercise a real warm HTTP cache across the v2 -> v3 portal release.

The local GET-only proxy delivers the previous immutable portal and public v2
game, then the candidate portal/v3 game. It reproduces the deployed cache TTLs.
No Playwright routes are installed: routing would disable the browser cache.
Telegram's external SDK is removed only from this isolated guest context.
Actual Nginx MISS/HIT headers still require a separate post-deployment check.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
from urllib.parse import urlsplit

import httpx
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
GAME = "games/arcade/snake/"


@asynccontextmanager
async def cache_browser(playwright, cleanup_errors):
    browser = await playwright.chromium.launch(args=["--use-angle=swiftshader-webgl"])
    try:
        yield browser
    finally:
        try:
            await asyncio.wait_for(browser.close(), 10)
        except Exception as error:
            cleanup_errors.append({"operation": "browser.close", "type": type(error).__name__, "error": str(error)})


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    old_html = subprocess.check_output(["git", "show", args.old_commit + ":web/index.html"], cwd=ROOT)
    old_app = subprocess.check_output(["git", "show", args.old_commit + ":web/app.js"], cwd=ROOT)
    old_localization = subprocess.check_output(["git", "show", args.old_commit + ":web/game-localization.js"], cwd=ROOT)
    assert b"/play-v2/" in old_app
    assert b"app.js?v=20261025-arcade-4" in old_html
    upstream = httpx.Client(timeout=40, follow_redirects=True, headers={"Accept-Encoding": "identity"})
    served, proxy_errors, cleanup_errors = [], [], []
    mode = {"release": "old"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.send_error(405, "This isolated cache proof never forwards writes")

        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                if path == "/" and mode["release"] == "old":
                    body, content_type = old_html, "text/html; charset=utf-8"
                elif self.path == "/static/app.js?v=20261025-arcade-4":
                    body, content_type = old_app, "application/javascript"
                elif self.path == "/static/game-localization.js?v=20261025-7":
                    body, content_type = old_localization, "application/javascript"
                else:
                    previous_asset = path.startswith("/play-v2/") or self.path == "/static/covers/planet-visitor.webp"
                    base = args.old_base if previous_asset else args.base
                    response = upstream.get(base.rstrip("/") + self.path)
                    response.raise_for_status()
                    body, content_type = response.content, response.headers.get("content-type", "application/octet-stream")
                if path == "/":
                    body = body.replace(b'<script src="https://telegram.org/js/telegram-web-app.js"></script>', b'<script>window.Telegram=undefined;</script>')
                served.append({"release": mode["release"], "path": self.path, "sha256": hashlib.sha256(body).hexdigest()})
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache" if path == "/" else "public, max-age=3600")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:
                proxy_errors.append({"path": self.path, "type": type(error).__name__})
                self.send_error(502, "Cache proof upstream failed")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    report = {"candidate": args.base, "previous": args.old_base, "previous_commit": args.old_commit,
              "passed": False, "checks": [], "scope": "Real prior/candidate portal and Snake sources through a GET-only cache-header proxy; no account, ranking writes, game-result fixture, or Playwright request routing. Nginx configuration is verified separately."}
    try:
        async with async_playwright() as playwright:
            async with cache_browser(playwright, cleanup_errors) as browser:
                context = await browser.new_context(viewport={"width": 1440, "height": 1000})
                page = await context.new_page()
                page.set_default_timeout(20000)
                await page.add_init_script("localStorage.setItem('baltigogames:guest:tutorials','[\"snake\"]');")
                cdp = await context.new_cdp_session(page)
                await cdp.send("Network.enable")
                requests, by_id, cached = [], {}, set()
                cdp.on("Network.requestWillBeSent", lambda event: by_id.update({event["requestId"]: event["request"]["url"]}))
                cdp.on("Network.requestServedFromCache", lambda event: cached.add(event["requestId"]))
                cdp.on("Network.responseReceived", lambda event: cached.add(event["requestId"]) if event["response"].get("fromDiskCache") else None)
                page.on("request", lambda request: requests.append(request.url))

                async def open_snake(prefix):
                    await page.locator('#featuredRail [data-game="snake"]').click()
                    start = page.locator('[data-help-action="start"]')
                    if await start.is_visible():
                        await start.click()
                    await expect(page.locator("#playerLoader")).to_be_hidden(timeout=40000)
                    frame = page.frame_locator("#gameFrame")
                    assert await frame.locator('meta[name="baltigo-adapter"]').get_attribute("content")
                    assert await frame.locator("#homeGrid").count() == 0
                    source = await page.locator("#gameFrame").get_attribute("src")
                    assert source.startswith("/" + prefix + "/" + GAME), source
                    await page.wait_for_load_state("networkidle", timeout=40000)
                    return frame, source

                await page.goto(origin, wait_until="domcontentloaded")
                await expect(page.locator("#homeGrid .game-card").first).to_be_visible()
                old_frame, old_src = await open_snake("play-v2")
                report["checks"].append("previous_portal_opens_real_adapted_v2_game")
                old_asset = "/play-v2/" + GAME + "mechanics.js"
                await page.evaluate("async path=>{for(let i=0;i<2;i++){const response=await fetch(path);if(!response.ok)throw Error('warm fetch failed');await response.text();}}", old_asset)
                await page.wait_for_timeout(100)
                old_cache_hits = [by_id.get(request_id) for request_id in cached if old_asset in by_id.get(request_id, "")]
                assert old_cache_hits, "The previous v2 source was not served from the real browser HTTP cache"
                report["checks"].append("previous_v2_source_confirmed_in_browser_cache")
                image_digest = "async path=>{const response=await fetch(path);if(!response.ok)throw Error('cover fetch failed');const digest=await crypto.subtle.digest('SHA-256',await response.arrayBuffer());return [...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,'0')).join('');}"
                old_dictionary_path = "/static/game-localization.js?v=20261025-7"
                previous_dictionary_hash = await page.evaluate(image_digest, old_dictionary_path)
                assert await page.evaluate(image_digest, old_dictionary_path) == previous_dictionary_hash
                await page.wait_for_timeout(100)
                dictionary_cache_hits = [by_id.get(request_id) for request_id in cached if by_id.get(request_id) == origin + old_dictionary_path]
                assert dictionary_cache_hits, "The previous dictionary was not in the real browser HTTP cache"
                report["checks"].append("previous_localization7_confirmed_in_browser_cache")
                old_cover = "/static/covers/planet-visitor.webp"
                previous_cover_hash = await page.evaluate(image_digest, old_cover)
                assert await page.evaluate(image_digest, old_cover) == previous_cover_hash
                await page.wait_for_timeout(100)
                cover_cache_hits = [by_id.get(request_id) for request_id in cached if by_id.get(request_id) == origin + old_cover]
                assert cover_cache_hits, "The previous Planet cover was not in the real browser HTTP cache"
                old_time = await old_frame.locator("body").evaluate("()=>performance.timeOrigin")
                mode["release"] = "new"
                await page.wait_for_timeout(500)
                assert await page.locator("#gameFrame").get_attribute("src") == old_src
                assert await old_frame.locator("body").evaluate("()=>performance.timeOrigin") == old_time
                report["checks"].append("open_round_is_not_forcibly_reloaded")

                await page.locator("#playerBack").click()
                start_index = len(requests)
                await page.goto(origin, wait_until="domcontentloaded")
                await expect(page.locator("#homeGrid .game-card").first).to_be_visible()
                assert await page.locator('script[src*="/static/app.js"]').get_attribute("src") == "/static/app.js?v=20261025-arcade-6"
                assert await page.locator('link[rel="stylesheet"]').get_attribute("href") == "/static/styles.css?v=20261025-arcade-5"
                report["checks"].append("new_home_loads_app6_and_styles5")
                covers = await page.locator('img[src^="/static/covers/"]').evaluate_all("images=>images.map(image=>image.getAttribute('src'))")
                planet = [url for url in covers if url.startswith("/static/covers/planet-visitor.webp")]
                assert planet and all(url.endswith("?v=20261025-arcade-5") for url in planet), planet
                assert all("?v=20261025-arcade-5" not in url for url in covers if not url.startswith("/static/covers/planet-visitor.webp"))
                report["checks"].append("only_replaced_planet_cover_receives_new_cache_key")
                new_cover_hash = await page.evaluate(image_digest, planet[0])
                expected_cover_hash = hashlib.sha256((ROOT / "web/covers/planet-visitor.webp").read_bytes()).hexdigest()
                assert new_cover_hash == expected_cover_hash and new_cover_hash != previous_cover_hash
                report["checks"].append("cached_previous_planet_cover_is_replaced_with_actual_new_bytes")
                new_frame, new_src = await open_snake("play-v3")
                new_dictionary_path = "/static/game-localization.js?v=20261025-8"
                assert await new_frame.locator('script[src*="/static/game-localization.js"]').get_attribute('src') == new_dictionary_path
                new_dictionary_hash = await page.evaluate(image_digest, new_dictionary_path)
                expected_dictionary_hash = hashlib.sha256((ROOT / 'web/game-localization.js').read_bytes()).hexdigest()
                assert new_dictionary_hash == expected_dictionary_hash and new_dictionary_hash != previous_dictionary_hash
                dictionary = json.loads((ROOT / 'data/localization-pt.json').read_text(encoding='utf8'))
                key = 'Avoid obstacles like        ,      .\nSwipe up to jump, swipe twice for\nan extra bounce'
                assert await new_frame.locator('body').evaluate('(element,key)=>window.__BALTIGO_PT[key]', key) == dictionary[key]
                report['checks'].extend(['new_game_uses_localization8_cache_key', 'new_dictionary_actual_bytes_and_correct_forest_instructions'])
                observed = [urlsplit(url).path for url in requests[start_index:]]
                required = ["/play-v3/" + GAME + filename for filename in ["index.html", "mechanics.js", "config.json"]]
                assert all(path in observed for path in required), (required, observed)
                assert not any(path.startswith("/play-v2/" + GAME) for path in observed), observed
                assert not proxy_errors, proxy_errors
                report["checks"].extend(["new_iframe_is_real_adapted_v3_game", "new_relative_js_and_config_use_v3", "no_new_game_request_reuses_v2_cache_key"])
                report.update(passed=True, previous_iframe=old_src, new_iframe=new_src, old_browser_cache_hits=old_cache_hits,
                              previous_planet_cache_hits=cover_cache_hits, previous_planet_sha256=previous_cover_hash,
                              new_planet_sha256=new_cover_hash,
                              previous_dictionary_sha256=previous_dictionary_hash, new_dictionary_sha256=new_dictionary_hash,
                              previous_dictionary_cache_hits=dictionary_cache_hits,
                              new_game_paths=[path for path in observed if path.startswith("/play-v3/")])
                await page.screenshot(path=str(out / "v3-player-after-warm-v2.png"))
                await context.close()
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        server.shutdown()
        server.server_close()
        upstream.close()
        report.update(passed=report["passed"] and not cleanup_errors, proxy_errors=proxy_errors,
                      cleanup_errors=cleanup_errors, served=served)
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"served", "new_game_paths"}}, ensure_ascii=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8195")
    parser.add_argument("--old-base", default="https://games.187-77-255-164.sslip.io")
    parser.add_argument("--old-commit", default="601ee7f351e9aae5471ae35716d5058d423bccae")
    parser.add_argument("--out", default="artifacts/cache-v3")
    raise SystemExit(asyncio.run(run(parser.parse_args())))
