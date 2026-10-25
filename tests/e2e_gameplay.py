"""Load actual game frames and their assets, one representative per category."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8186").rstrip("/")
OUT = Path("artifacts")
OUT.mkdir(exist_ok=True)
SAMPLES = ["snake", "2048", "chess", "car-race", "basketball", "doodle-jump",
           "bubble-shooter", "alien-battle", "wordle", "stack-tower", "fruit-merge"]


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for slug in SAMPLES:
            context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
            page = context.new_page()
            failures, errors, responses = [], [], {}
            page.on("response", lambda response: responses.update({response.url: response.status}))
            page.on("requestfailed", lambda request: failures.append({"url": request.url, "error": request.failure}))
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("https://telegram.org/js/telegram-web-app.js", lambda route: route.fulfill(status=200, content_type="application/javascript", body=""))
            try:
                page.goto(BASE + "/?startapp=" + slug, wait_until="domcontentloaded")
                page.wait_for_selector("#player:not([hidden])")
                frame = page.locator("#gameFrame").element_handle().content_frame()
                frame.wait_for_load_state("load", timeout=45000)
                frame.wait_for_selector("canvas, button, input, .game, #game, #game-container", state="attached", timeout=30000)
                page.wait_for_timeout(1800)
                body = frame.locator("body").inner_text()
                assert "game asset not found" not in body and "upstream game unavailable" not in body
                assert not errors, errors
                bad_responses = {url: status for url, status in responses.items() if status >= 400}
                # Browsers may cancel a media preload after receiving a successful response.
                bad_requests = [request for request in failures if responses.get(request["url"]) != 200]
                assert not bad_responses, bad_responses
                assert not bad_requests, bad_requests
                page.screenshot(path=str(OUT / f"game-{slug}.png"))
                results.append({"slug": slug, "ok": True, "canvases": frame.locator("canvas").count()})
            except Exception as exc:
                page.screenshot(path=str(OUT / f"FAIL-game-{slug}.png"))
                results.append({"slug": slug, "ok": False, "error": str(exc), "requests": failures, "javascript": errors})
            print(json.dumps(results[-1]), flush=True)
            context.close()
        browser.close()
    (OUT / "gameplay.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    assert all(result["ok"] for result in results), "one or more games failed to render"


if __name__ == "__main__":
    main()
