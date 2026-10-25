"""Real browser integration checks. Telegram client hooks are simulated explicitly."""
import json
import os
import traceback
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from e2e_smoke import TG_MOCK

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8186").rstrip("/")
OUT = Path("artifacts")
OUT.mkdir(exist_ok=True)


def run():
    results = []
    with sync_playwright() as p:
        for engine in ["chromium", "firefox", "webkit"]:
            browser = getattr(p, engine).launch()
            for width, height in [(360, 800), (390, 844), (768, 1024), (1440, 1000)]:
                context = browser.new_context(viewport={"width": width, "height": height}, locale="pt-BR", has_touch=width < 800)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.route("https://telegram.org/js/telegram-web-app.js", lambda route: route.fulfill(status=200, content_type="application/javascript", body=""))
                page.add_init_script(TG_MOCK)
                try:
                    page.goto(BASE, wait_until="domcontentloaded")
                    page.wait_for_selector("#homeGrid .game-card")
                    assert page.locator("#homeGrid .game-card").count() == 142
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    page.locator('[data-category="board"]').click()
                    assert page.locator("#homeGrid .game-card").count() > 0
                    assert "TABULEIRO" in page.locator("#homeGrid .game-card").first.inner_text().upper()
                    page.locator('[data-category="all"]').click()
                    page.locator("#searchInput").fill("game-does-not-exist-999")
                    assert page.locator("#emptyState").is_visible()
                    page.locator("#clearSearch").click()
                    page.locator('#homeGrid [data-favorite="snake"]').click()
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_selector("#homeGrid .game-card")
                    page.locator('[data-view-target="favorites"]').click()
                    assert page.locator('#favoritesGrid [data-game="snake"]').count() == 1
                    page.locator('#favoritesGrid [data-game="snake"] .game-emoji').click()
                    page.wait_for_selector("#player:not([hidden])")
                    page.locator("#playerReload").click()
                    expect(page.locator("#gameFrame")).to_have_attribute("src", re.compile("/play/games/arcade/snake/"))
                    page.locator("#playerShare").click()
                    assert "switchInlineQuery:game:snake" in page.evaluate("window.__tgCalls")
                    page.evaluate("window.__tgBack()")
                    assert page.locator("#player").is_hidden()
                    page.locator('[data-view-target="recent"]').click()
                    assert page.locator('#recentGrid [data-game="snake"]').count() == 1
                    page.reload(wait_until="domcontentloaded")
                    page.wait_for_selector("#homeGrid .game-card")
                    page.locator('[data-view-target="recent"]').click()
                    assert page.locator('#recentGrid [data-game="snake"]').count() == 1
                    page.locator('[data-view-target="home"]').click()
                    page.locator('#homeGrid [data-favorite="snake"]').click()
                    page.locator('[data-view-target="favorites"]').click()
                    assert page.locator("#favoritesEmpty").is_visible()
                    page.goto(BASE + "/?startapp=2048", wait_until="domcontentloaded")
                    page.wait_for_selector("#player:not([hidden])")
                    assert page.locator("#playerTitle").inner_text() == "2048"
                    page.locator("#playerBack").click()
                    page.evaluate("dispatchEvent(new Event('offline'))")
                    assert page.locator("#offlineBanner").is_visible()
                    page.evaluate("dispatchEvent(new Event('online'))")
                    assert page.locator("#offlineBanner").is_hidden()
                    page.screenshot(path=str(OUT / f"{engine}-{width}.png"))
                    assert not errors, errors
                    results.append({"engine": engine, "viewport": width, "ok": True})
                except Exception as exc:
                    page.screenshot(path=str(OUT / f"FAIL-{engine}-{width}.png"))
                    results.append({"engine": engine, "viewport": width, "ok": False, "error": traceback.format_exc()})
                finally:
                    context.close()
            # A second Telegram identity must not inherit local preferences/history.
            context = browser.new_context()
            page = context.new_page()
            page.route("https://telegram.org/js/telegram-web-app.js", lambda route: route.fulfill(status=200, content_type="application/javascript", body=""))
            page.add_init_script(TG_MOCK.replace("424242", "999999"))
            page.goto(BASE, wait_until="domcontentloaded")
            page.wait_for_selector("#homeGrid .game-card")
            page.evaluate("localStorage.setItem('baltigogames:424242:favorites', '[\"snake\"]')")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_selector("#homeGrid .game-card")
            page.locator('[data-view-target="favorites"]').click()
            assert page.locator("#favoritesEmpty").is_visible()
            results.append({"engine": engine, "case": "user-isolation", "ok": True})
            context.close()
            browser.close()
    (OUT / "browser-matrix.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    assert all(result["ok"] for result in results), "browser matrix failed"


if __name__ == "__main__":
    run()
