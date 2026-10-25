from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
ARTIFACTS = Path("artifacts")
ARTIFACTS.mkdir(exist_ok=True)

TG_MOCK = r"""
window.__tgCalls = [];
window.Telegram = {
  WebApp: {
    initDataUnsafe: { user: { id: 424242, first_name: "Teste", username: "teste" } },
    isFullscreen: false,
    ready() { window.__tgCalls.push("ready"); },
    expand() { window.__tgCalls.push("expand"); },
    setHeaderColor() {},
    setBackgroundColor() {},
    setBottomBarColor() {},
    disableVerticalSwipes() { window.__tgCalls.push("disableVerticalSwipes"); },
    enableVerticalSwipes() { window.__tgCalls.push("enableVerticalSwipes"); },
    requestFullscreen() { this.isFullscreen = true; window.__tgCalls.push("requestFullscreen"); },
    exitFullscreen() { this.isFullscreen = false; window.__tgCalls.push("exitFullscreen"); },
    switchInlineQuery(query, chats) { window.__tgCalls.push("switchInlineQuery:" + query); },
    HapticFeedback: { impactOccurred(kind) { window.__tgCalls.push("haptic:" + kind); } },
    BackButton: {
      onClick(cb) { window.__tgBack = cb; window.__tgCalls.push("BackButton.onClick"); },
      show() { window.__tgCalls.push("BackButton.show"); },
      hide() { window.__tgCalls.push("BackButton.hide"); }
    }
  }
};
"""


def prepare(page):
    page.route("https://telegram.org/js/telegram-web-app.js", lambda route: route.fulfill(status=200, content_type="application/javascript", body=""))
    page.add_init_script(TG_MOCK)
    response = page.goto(BASE + "/", wait_until="domcontentloaded")
    assert response and response.ok, f"home returned {response.status if response else 'no response'}"
    page.wait_for_selector("#homeGrid .game-card", timeout=15_000)
    assert page.locator("#homeGrid .game-card").count() == 142
    assert page.locator("#categoryStrip .category-chip").count() == 11
    assert page.locator("#profileName").inner_text() == "Teste"


def mobile_flow(browser):
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        locale="pt-BR",
    )
    page = context.new_page()
    prepare(page)

    page.screenshot(path=str(ARTIFACTS / "mobile-home.png"))

    page.locator("#searchInput").fill("snake")
    assert page.locator('#homeGrid [data-game="snake"]').count() == 1
    assert page.locator("#homeGrid .game-card").count() >= 1
    page.locator("#clearSearch").click()
    assert page.locator("#homeGrid .game-card").count() == 142

    fav = page.locator('#homeGrid [data-game="snake"] [data-favorite="snake"]')
    fav.click()
    page.locator('button[data-view-target="favorites"]').click()
    assert page.locator('#favoritesGrid [data-game="snake"]').count() == 1

    page.locator('button[data-view-target="home"]').click()
    page.locator('#homeGrid [data-game="snake"] .game-emoji').click()
    page.wait_for_selector("#player:not([hidden])")
    assert "/play/games/arcade/snake/index.html" in page.locator("#gameFrame").get_attribute("src")

    for path in [
        "games/arcade/snake/index.html",
        "games/puzzle/2048/index.html",
        "games/board/chess/index.html",
        "games/racing/car-race/index.html",
        "games/sports/basketball/index.html",
        "games/platformer/doodle-jump/index.html",
        "games/casual/bubble-shooter/index.html",
        "games/shooter/alien-battle/index.html",
        "games/word-quiz/wordle/index.html",
        "games/3d/stack-tower/index.html",
        "games/casual/fruit-merge/inex.html",
    ]:
        response = page.request.get(f"{BASE}/play/{path}", timeout=30_000)
        assert response.ok, f"proxy failed for {path}: {response.status}"

    page.wait_for_timeout(1200)
    page.screenshot(path=str(ARTIFACTS / "mobile-player-snake.png"))
    page.locator("#playerShare").click()
    calls = page.evaluate("window.__tgCalls")
    assert "ready" in calls
    assert "expand" in calls
    assert "BackButton.show" in calls
    assert "disableVerticalSwipes" in calls
    assert "requestFullscreen" in calls
    assert "switchInlineQuery:game:snake" in calls

    page.locator("#playerBack").click()
    assert page.locator("#player").is_hidden()
    calls = page.evaluate("window.__tgCalls")
    assert "BackButton.hide" in calls
    assert "enableVerticalSwipes" in calls

    page.locator('button[data-view-target="recent"]').click()
    assert page.locator('#recentGrid [data-game="snake"]').count() == 1
    page.locator('button[data-view-target="home"]').click()
    page.locator("#games, #homeGrid").first.scroll_into_view_if_needed()
    page.screenshot(path=str(ARTIFACTS / "mobile-catalog.png"))
    context.close()


def desktop_flow(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="pt-BR")
    page = context.new_page()
    prepare(page)
    page.screenshot(path=str(ARTIFACTS / "desktop-home.png"))
    cards = page.locator("#homeGrid .game-card")
    boxes = [cards.nth(i).bounding_box() for i in range(6)]
    assert all(boxes[:6])
    y0 = round(boxes[0]["y"])
    assert all(abs(round(boxes[i]["y"]) - y0) <= 2 for i in range(5)), "desktop should render five cards per row"
    assert boxes[5]["y"] > boxes[0]["y"]
    context.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        mobile_flow(browser)
        desktop_flow(browser)
        browser.close()
    print("E2E OK: mobile + desktop + player + Telegram hooks + 11 proxy samples")


if __name__ == "__main__":
    main()
