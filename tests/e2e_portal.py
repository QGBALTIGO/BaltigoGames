"""Repeatable portal UI checks, isolated from real Telegram accounts and ranking writes.

Run with TEST_BASE_URL=http://127.0.0.1:8190 python tests/e2e_portal.py.
The catalog and portal assets are real. Telegram's SDK, authenticated session/run
responses, and the small player fixture are intercepted only inside test contexts.
The actual 142-game mechanics audit is scripts/audit_games.py, not this UI suite.
"""
from __future__ import annotations

import asyncio
from functools import wraps
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8190").rstrip("/")
OUTPUT_DIR = Path(os.getenv("TEST_OUTPUT_DIR", "artifacts/portal-e2e"))
VIEWPORTS = [(360, 740), (390, 844), (844, 390), (1440, 1000)]
DIAGNOSTIC_TIMEOUT_SECONDS = 10
PLAY_ROUTE = re.compile(r"/play(?:-v[23])?/")


async def capture_failure(page, filename: str) -> dict:
    """A failed diagnostic must never replace the failed interaction."""
    try:
        await asyncio.wait_for(page.screenshot(path=str(OUTPUT_DIR / filename), timeout=10000), DIAGNOSTIC_TIMEOUT_SECONDS)
        return {"failure_screenshot": filename}
    except Exception as error:
        return {"screenshot_error": f"{type(error).__name__}: {error}"}


def isolated_contexts(function):
    """Close every context created by a serial scenario, preserving its result."""
    @wraps(function)
    async def wrapped(browser, *args):
        previous = list(browser.contexts)
        result = None
        try:
            result = await function(browser, *args)
        except Exception as error:
            result = {"passed": False, "checks": [], "error": str(error), "error_type": type(error).__name__}
        finally:
            cleanup_errors = []
            for context in [context for context in browser.contexts if context not in previous]:
                try:
                    await asyncio.wait_for(context.close(), DIAGNOSTIC_TIMEOUT_SECONDS)
                except Exception as error:
                    cleanup_errors.append(f"{type(error).__name__}: {error}")
            if cleanup_errors and result is not None:
                result["cleanup_errors"] = cleanup_errors
                result["passed"] = False
        return result
    return wrapped

TELEGRAM_FIXTURE = """
window.__tgHandlers = {};
window.Telegram = {WebApp:{
  initData:'synthetic-isolated-ui-test',
  initDataUnsafe:{user:{id:424242,first_name:'Jogador de teste'}},
  isFullscreen:false,viewportHeight:innerHeight,
  safeAreaInset:{top:44,bottom:34,left:0,right:0},
  contentSafeAreaInset:{top:54,bottom:0,left:0,right:0},
  ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},
  setBottomBarColor(){},disableVerticalSwipes(){},enableVerticalSwipes(){},
  onEvent(name,fn){window.__tgHandlers[name]=fn},
  BackButton:{onClick(){},show(){},hide(){}},
  HapticFeedback:{impactOccurred(){}},
  requestFullscreen(){this.isFullscreen=true;window.__tgHandlers.fullscreenChanged?.()},
  exitFullscreen(){this.isFullscreen=false;window.__tgHandlers.fullscreenChanged?.()}
}};
"""
GAME_FIXTURE = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Partida sintética para testar o portal</title>
<body style="background:#162530;color:#fff;margin:0;overflow:hidden">
<canvas width="100" height="100" aria-label="Área de teste"></canvas>
<script>
parent.postMessage({type:'baltigo:ready',slug:'snake'},location.origin);
addEventListener('message',event=>{window.lastPause=event.data});
</script></body></html>"""


async def intercept_telegram(page, authenticated: bool):
    requests: list[dict] = []
    sdk = TELEGRAM_FIXTURE if authenticated else "window.Telegram=undefined;"
    await page.route("https://telegram.org/js/telegram-web-app.js", lambda route: route.fulfill(
        status=200, content_type="application/javascript", body=sdk))

    async def session(route):
        requests.append({"path": "session", "body": route.request.post_data_json})
        await route.fulfill(json={"token": "isolated-test-token", "guest": False,
                                  "user": {"id": "test-user", "display_name": "Jogador de teste"}})

    async def runs(route):
        path = route.request.url.split("/api/")[-1]
        body = route.request.post_data_json
        requests.append({"path": path, "body": body})
        if not authenticated:
            await route.fulfill(status=401, json={"detail": "Visitante"})
        elif path == "runs":
            await route.fulfill(json={"run_id": "isolated-test-run", "heartbeat_interval_seconds": 10})
        elif path.endswith("/heartbeat"):
            await route.fulfill(json={"active": body["active"], "active_seconds": 0})
        else:
            await route.fulfill(json={"accepted": False, "points": 0, "reason": "atividade_insuficiente"})

    await page.route("**/api/session", session)
    await page.route("**/api/runs**", runs)
    await page.route(PLAY_ROUTE, lambda route: route.fulfill(
        status=200, content_type="text/html", body=GAME_FIXTURE))
    return requests


async def choose_view(page, view: str):
    await page.locator(f'[data-view-target="{view}"]:visible').first.click()
    await expect(page.locator(f'[data-view="{view}"]')).to_be_visible()


async def continue_without_rotation(page):
    button = page.locator('[data-help-action="portrait-start"]')
    if await button.is_visible():
        await button.click()


async def assert_box_inside(page, selector: str, top: int, bottom: int):
    box = await page.locator(selector).bounding_box()
    assert box is not None, selector
    assert box["y"] >= top - 1, (selector, "overlaps native header", box)
    assert box["y"] + box["height"] <= bottom + 1, (selector, "overlaps native bottom", box)
    return box


@isolated_contexts
async def run_viewport(browser, name: str, width: int, height: int):
    context = await browser.new_context(viewport={"width": width, "height": height})
    page = await context.new_page()
    page.set_default_timeout(10000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    requests = await intercept_telegram(page, True)
    await page.add_init_script("""
      localStorage.setItem('baltigogames:424242:favorites',JSON.stringify(['chess']));
      localStorage.setItem('baltigogames:424242:recent',JSON.stringify(['tetris']));
    """)
    checks: list[str] = []
    try:
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await expect(page.locator("#homeGrid .game-card").first).to_be_visible()
        assert await page.locator("#homeGrid .game-card").count() >= 1
        assert await page.locator("#helpDialog").is_hidden(), "No unsolicited opening modal"
        assert not await page.evaluate("document.documentElement.scrollWidth>innerWidth")
        checks.extend(["catalog_loaded", "no_unsolicited_modal", "no_horizontal_overflow"])

        await choose_view(page, "favorites")
        await expect(page.locator('#favoritesGrid [data-game="chess"]')).to_be_visible()
        await page.locator('#favoritesGrid [data-favorite="chess"]').click()
        await expect(page.locator("#favoritesEmpty")).to_be_visible()
        checks.extend(["legacy_favorites_preserved", "favorite_remove_and_empty_state"])

        await choose_view(page, "explore")
        await page.locator("#exploreSearch").fill("XADREZ")
        await expect(page.locator("#exploreGrid .game-card")).to_have_count(1)
        await page.locator('#exploreGrid [data-favorite="chess"]').click()
        await page.locator("#exploreSearch").fill("um-jogo-que-nao-existe-qa")
        await expect(page.locator("#exploreEmpty")).to_be_visible()
        await page.locator("#exploreReset").click()
        assert await page.locator("#exploreGrid .game-card").count() > 1
        await page.locator('#exploreCategories [data-category="board"]').click()
        await expect(page.locator('#exploreCategories [data-category="board"]')).to_have_attribute("aria-pressed", "true")
        checks.extend(["portuguese_search", "favorite_add", "empty_search", "reset_filters", "category_filter"])

        await choose_view(page, "home")
        await page.locator('#recentRail [data-game="tetris"]').click()
        await continue_without_rotation(page)
        await expect(page.locator("#helpDialog")).to_be_visible()
        await page.locator('[data-help-action="cancel"]').click()
        await page.locator('#featuredRail [data-game="snake"]').click()
        await continue_without_rotation(page)
        await expect(page.locator("#helpDialog")).to_be_visible()
        dialog = await assert_box_inside(page, "#helpDialog", 98, height - 34)
        checks.extend(["legacy_recent_preserved", "tutorial_cancel", "tutorial_in_safe_area"])
        await page.locator('[data-help-action="start"]').click()
        await expect(page.locator("#playerLoader")).to_be_hidden()
        header = await page.locator(".player-bar").bounding_box()
        frame = await assert_box_inside(page, "#gameFrame", 98, height - 34)
        assert header and header["y"] >= 98
        assert frame["y"] >= header["y"] + header["height"] - 1
        for control in await page.locator(".player-bar button:visible").all():
            target = await control.bounding_box()
            assert target["width"] >= 44 and target["height"] >= 44, target
        category_size = await page.locator("#playerCategory").evaluate("el=>parseFloat(getComputedStyle(el).fontSize)")
        title_size = await page.locator("#playerTitle").evaluate("el=>parseFloat(getComputedStyle(el).fontSize)")
        assert category_size >= 9 and title_size >= 12
        checks.extend(["fullscreen_safe_insets", "iframe_below_player_controls", "44px_player_touch_targets", "readable_player_name_category"])

        await page.locator("#playerPause").click()
        await expect(page.locator("#pausePanel")).to_be_visible()
        for selector in ["#resumeGame", "#playerReload", "#pauseExit"]:
            box = await page.locator(selector).bounding_box()
            assert box and box["y"] >= frame["y"] and box["y"] + box["height"] <= frame["y"] + frame["height"] + 1
        await page.locator("#resumeGame").click()
        await expect(page.locator("#pausePanel")).to_be_hidden()
        await page.locator("#playerHelp").click()
        await expect(page.locator("#helpDialog")).to_be_visible()
        await page.locator('[data-help-action="resume"]').click()
        checks.extend(["pause_resume", "pause_controls_fit_landscape", "reopen_tutorial"])

        # Same-origin messages from a wrong source or slug must not finish a run.
        await page.evaluate("postMessage({type:'baltigo:score',slug:'snake',score:999,event:'finish'},location.origin)")
        frame_context = page.frames[1]
        await frame_context.evaluate("parent.postMessage({type:'baltigo:score',slug:'wrong-game',score:999,event:'finish'},location.origin)")
        await page.wait_for_timeout(150)
        assert not any(request["path"].endswith("/finish") for request in requests)
        if width == 1440:
            await frame_context.evaluate("parent.postMessage({type:'baltigo:score',slug:'snake',score:125,event:'finish',outcome:'win'},location.origin)")
            await frame_context.evaluate("parent.postMessage({type:'baltigo:result',slug:'snake',score:125,outcome:'win'},location.origin)")
        else:
            await frame_context.evaluate("parent.postMessage({type:'baltigo:result',slug:'snake',score:null,outcome:'win'},location.origin)")
        await page.wait_for_timeout(150)
        await page.locator("#playerBack").click()
        await expect(page.locator("#player")).to_be_hidden()
        await page.wait_for_timeout(150)
        assert len([request for request in requests if request["path"] == "session"]) == 1
        assert any(request["path"].endswith("/heartbeat") and request["body"]["active"] is False for request in requests)
        finishes = [request for request in requests if request["path"].endswith("/finish")]
        assert len(finishes) == 1 and finishes[0]["body"]["outcome"] == "completed", finishes
        checks.extend(["session_once", "inactive_pause_heartbeat", "score_message_source_checks", "win_score_finish_completed" if width == 1440 else "finish_without_score", "duplicate_finish_prevented", "exit_restores_library"])
        if width == 1440:
            assert finishes[0]["body"]["score"] == 125
        assert not errors, errors
        await page.screenshot(path=str(OUTPUT_DIR / f"{name}-{width}x{height}.png"))
        return {"browser": name, "viewport": f"{width}x{height}", "passed": True,
                "checks": checks, "safe_top": header["y"], "frame_bottom": frame["y"] + frame["height"],
                "tutorial_top": dialog["y"], "errors": errors}
    except Exception as error:
        diagnostic = await capture_failure(page, f"FAIL-{name}-{width}x{height}.png")
        return {"browser": name, "viewport": f"{width}x{height}", "passed": False,
                "checks": checks, "error": str(error), "error_type": type(error).__name__, "errors": errors, **diagnostic}


@isolated_contexts
async def run_guest_and_ranking(browser):
    context = await browser.new_context(viewport={"width": 390, "height": 844})
    page = await context.new_page()
    page.set_default_timeout(10000)
    requests = await intercept_telegram(page, False)
    checks: list[str] = []
    try:
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await expect(page.locator("#homeGrid .game-card").first).to_be_visible()
        await page.locator("#profileButton").click()
        await expect(page.locator("#helpContent")).to_contain_text("visitante")
        await expect(page.locator("#helpContent")).to_contain_text("Telegram")
        await page.locator("#closeHelp").click()
        await page.locator('#featuredRail [data-game="snake"]').click()
        await continue_without_rotation(page)
        await page.locator('[data-help-action="start"]').click()
        await expect(page.locator("#playerLoader")).to_be_hidden()
        await page.locator("#playerBack").click()
        assert not requests, "Guests must not create sessions or ranking writes"
        checks.extend(["honest_guest_profile", "guest_can_play", "guest_has_no_ranking_writes"])

        ranking_calls: list[str] = []

        async def ranking(route):
            ranking_calls.append(route.request.url)
            mode = len(ranking_calls)
            if mode == 1:
                await route.fulfill(status=503, json={"detail": "Synthetic outage"})
            elif mode == 2:
                await route.fulfill(json={"entries": [], "me": None, "metric": "activity", "verified": False})
            else:
                await route.fulfill(json={"entries": [{"rank": 1, "display_name": "<img src=x onerror=alert(1)>", "points": 1234,
                                                       "games_played": 12, "is_me": False}],
                                          "me": {"rank": None, "display_name": "Visitante", "points": 0,
                                                 "games_played": 0, "is_me": True},
                                          "metric": "activity", "verified": False})

        await page.route("**/api/leaderboard?**", ranking)
        await choose_view(page, "ranking")
        await expect(page.locator("#rankingStatus")).to_contain_text("indisponível")
        await page.locator("[data-retry-ranking]").click()
        await expect(page.locator("#rankingStatus")).to_contain_text("Ainda não há partidas")
        await page.locator('[data-period="week"]').click()
        await expect(page.locator("#rankingEntries .ranking-row")).to_have_count(1)
        await expect(page.locator(".ranking-name")).to_have_text("<img src=x onerror=alert(1)>")
        assert await page.locator("#rankingEntries img").count() == 0
        await expect(page.locator("#rankingMe")).to_contain_text("primeira posição")
        assert "0º lugar" not in await page.locator("#rankingMe").inner_text()
        await page.locator("#rankingGame").select_option("snake")
        await page.wait_for_timeout(150)
        assert "period=week" in ranking_calls[-1] and "game=snake" in ranking_calls[-1]
        checks.extend(["ranking_error", "ranking_retry", "real_empty_state", "ranking_week_filter", "safe_player_names", "unranked_me_label", "ranking_game_filter"])
        return {"scenario": "guest_and_ranking", "passed": True, "checks": checks,
                "isolation": "SDK, player and ranking responses mocked; no real database writes"}
    except Exception as error:
        diagnostic = await capture_failure(page, "FAIL-guest-and-ranking.png")
        return {"scenario": "guest_and_ranking", "passed": False, "checks": checks, "error": str(error), "error_type": type(error).__name__, **diagnostic}


@isolated_contexts
async def run_orientation(browser, name):
    context = await browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
    page = await context.new_page()
    page.set_default_timeout(10000)
    await intercept_telegram(page, True)
    touch_fixture = GAME_FIXTURE.replace('<canvas width="100" height="100" aria-label="Área de teste"></canvas>',
        '<button id="touchTarget" style="position:absolute;left:20px;top:20px;width:60px;height:60px" '
        'onpointerdown="window.lastTouch={x:event.clientX,y:event.clientY};window.touchCount=(window.touchCount||0)+1">Toque</button>')
    await page.route(PLAY_ROUTE, lambda route: route.fulfill(status=200, content_type="text/html", body=touch_fixture))

    async def catalog_with_orientation(route):
        response = await route.fetch()
        data = await response.json()
        for game in data["games"]:
            if game["slug"] == "snake":
                game.update(orientation="landscape", logical_width=1920, logical_height=1080)
        await route.fulfill(json=data)

    await page.route("**/api/catalog**", catalog_with_orientation)
    checks = []
    try:
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await page.locator('#featuredRail [data-game="snake"]').click()
        await expect(page.locator('[data-help-action="rotate-start"]')).to_be_visible()
        await expect(page.locator("#helpContent")).to_contain_text("horizontal")
        checks.append("landscape_game_rotation_hint")
        await page.locator('[data-help-action="rotate-start"]').click()
        await page.locator("#skipGameTutorial").check()
        await page.locator('[data-help-action="start"]').click()
        await expect(page.locator("#playerLoader")).to_be_hidden()
        await expect(page.locator("#playerRotate")).to_have_attribute("aria-pressed", "true")
        stage = await page.locator(".player-stage").bounding_box()
        header = await page.locator(".player-bar").bounding_box()
        game_frame = page.frames[1]
        dimensions = await game_frame.evaluate("({width:innerWidth,height:innerHeight})")
        assert abs(dimensions["width"] - stage["height"]) <= 1
        assert abs(dimensions["height"] - stage["width"]) <= 1
        assert header["y"] >= 98 and stage["y"] >= header["y"] + header["height"] - 1
        assert stage["y"] + stage["height"] <= 811
        checks.extend(["iframe_receives_real_landscape_viewport", "toolbar_upright_and_safe", "rotated_stage_fits_available_area"])
        # CSS iframe rotation must map real touch coordinates back into the game correctly.
        await page.touchscreen.tap(stage["x"] + stage["width"] - 50, stage["y"] + 50)
        await page.wait_for_timeout(100)
        touch = await game_frame.evaluate("({count:window.touchCount||0,last:window.lastTouch})")
        assert touch["count"] == 1 and abs(touch["last"]["x"] - 50) <= 2 and abs(touch["last"]["y"] - 50) <= 2, touch
        checks.append("rotated_iframe_real_touch_coordinates")
        # A raw source preference cannot override the reviewed catalog orientation.
        await game_frame.evaluate("parent.postMessage(JSON.stringify({type:'orientation',value:'portrait'}),location.origin)")
        await expect(page.locator("#playerRotate")).to_have_attribute("aria-pressed", "true")
        checks.append("catalog_orientation_wins_over_legacy_source_message")
        await page.locator("#playerRotate").click()
        dimensions = await game_frame.evaluate("({width:innerWidth,height:innerHeight})")
        assert abs(dimensions["width"] - stage["width"]) <= 1
        await page.locator("#playerRotate").click()
        await page.locator("#playerPause").click()
        await expect(page.locator("#pausePanel")).to_be_visible()
        assert await page.locator("#pausePanel").evaluate("e=>getComputedStyle(e).transform") == "none"
        await page.locator("#resumeGame").click()
        checks.extend(["manual_rotation_toggle", "pause_controls_remain_upright"])
        await page.screenshot(path=str(OUTPUT_DIR / f"{name}-rotated-player.png"))
        await page.set_viewport_size({"width": 844, "height": 390})
        await page.evaluate("Telegram.WebApp.viewportHeight=innerHeight;window.__tgHandlers.viewportChanged?.()")
        await expect(page.locator("#playerRotate")).to_be_hidden()
        assert not await page.locator(".player-stage").evaluate("e=>e.classList.contains('is-rotated')")
        landscape = await page.locator(".player-stage").bounding_box()
        dimensions = await game_frame.evaluate("({width:innerWidth,height:innerHeight})")
        assert abs(dimensions["width"] - landscape["width"]) <= 1
        assert abs(dimensions["height"] - landscape["height"]) <= 1
        assert landscape["y"] + landscape["height"] <= 357
        checks.append("actual_device_landscape_removes_virtual_rotation")
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.evaluate("Telegram.WebApp.viewportHeight=innerHeight;window.__tgHandlers.viewportChanged?.()")
        await expect(page.locator("#playerRotate")).to_have_attribute("aria-pressed", "true")
        await page.locator("#playerBack").click()
        await page.locator('#featuredRail [data-game="snake"]').click()
        await expect(page.locator("#helpDialog")).to_be_hidden()
        await expect(page.locator("#playerRotate")).to_have_attribute("aria-pressed", "true")
        checks.append("rotation_preference_and_tutorial_preference_persist")
        await page.locator("#playerBack").click()
        return {"browser": name, "scenario": "landscape_rotation", "passed": True, "checks": checks,
                "scope": "Real CSS iframe dimensions and real touch events with isolated game fixture"}
    except Exception as error:
        diagnostic = await capture_failure(page, f"FAIL-{name}-orientation.png")
        return {"browser": name, "scenario": "landscape_rotation", "passed": False, "checks": checks, "error": str(error), "error_type": type(error).__name__, **diagnostic}


@isolated_contexts
async def run_desktop_orientation(browser, name):
    """A narrow mouse window must not inherit a sideways mobile preference."""
    context = await browser.new_context(viewport={"width": 430, "height": 880}, has_touch=False)
    page = await context.new_page()
    page.set_default_timeout(10000)
    await intercept_telegram(page, True)
    await page.add_init_script("""
      localStorage.setItem('baltigogames:424242:rotations',JSON.stringify({snake:true}));
      localStorage.setItem('baltigogames:424242:tutorials',JSON.stringify(['snake']));
    """)

    async def desktop_catalog(route):
        response = await route.fetch()
        data = await response.json()
        for game in data["games"]:
            if game["slug"] == "snake":
                game.update(orientation="landscape", logical_width=1920, logical_height=1080)
        await route.fulfill(json=data)

    await page.route("**/api/catalog**", desktop_catalog)
    checks = []
    try:
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await page.locator('#featuredRail [data-game="snake"]').click()
        await expect(page.locator("#helpDialog")).to_be_hidden()
        await expect(page.locator("#playerLoader")).to_be_hidden()
        await expect(page.locator("#playerRotate")).to_have_attribute("aria-pressed", "false")
        assert not await page.locator(".player-stage").evaluate("e=>e.classList.contains('is-rotated')")
        checks.extend(["mouse_window_no_device_rotation_prompt", "mouse_window_ignores_mobile_rotation_preference"])
        stage = await page.locator(".player-stage").bounding_box()
        dimensions = await page.frames[1].evaluate("({width:innerWidth,height:innerHeight})")
        assert abs(dimensions["width"] - stage["width"]) <= 1
        assert abs(dimensions["height"] - stage["height"]) <= 1
        checks.append("mouse_window_game_viewport_upright")
        await page.locator("#playerRotate").click()
        await expect(page.locator("#playerRotate")).to_have_attribute("aria-pressed", "true")
        checks.append("mouse_manual_rotation_available")
        await page.locator("#playerBack").click()
        await page.locator('#featuredRail [data-game="snake"]').click()
        await expect(page.locator("#playerRotate")).to_have_attribute("aria-pressed", "false")
        checks.append("mouse_reopen_never_defaults_sideways")
        await page.screenshot(path=str(OUTPUT_DIR / f"{name}-desktop-upright-player.png"))
        await page.locator("#playerBack").click()
        return {"browser": name, "scenario": "desktop_orientation", "passed": True, "checks": checks}
    except Exception as error:
        diagnostic = await capture_failure(page, f"FAIL-{name}-desktop-orientation.png")
        return {"browser": name, "scenario": "desktop_orientation", "passed": False, "checks": checks, "error": str(error), "error_type": type(error).__name__, **diagnostic}


@isolated_contexts
async def run_cover_focus(browser):
    context = await browser.new_context(viewport={"width": 390, "height": 844})
    page = await context.new_page()
    await intercept_telegram(page, True)
    response = await page.request.get(BASE_URL + "/api/catalog?v=20261025-arcade")
    catalog = await response.json()
    values = {"car-race": "50% 100%", "snake": "12.5% 87.5%", "tetris": "50% 120%",
              "chess": "50% 10%; display:none", "2048": ["50%", "100%"],
              "fruit-merge": "-1% 50%", "bubble-pop": " 50%    0% "}
    for game in catalog["games"]:
        if game["slug"] in values:
            game["cover_position"] = values[game["slug"]]
        else:
            game.pop("cover_position", None)
    await page.route("**/api/catalog**", lambda route: route.fulfill(json=catalog))
    checks = []
    try:
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await choose_view(page, "explore")
        expected = {"car-race": "50% 100%", "snake": "12.5% 87.5%", "tetris": "50% 50%",
                    "chess": "50% 50%", "2048": "50% 50%", "fruit-merge": "50% 50%",
                    "bubble-pop": "50% 0%", "carrom": "50% 50%"}
        for slug, position in expected.items():
            image = page.locator('#exploreGrid [data-game-card="' + slug + '"] img')
            assert await image.evaluate("el=>el.style.objectPosition") == position
            assert await image.evaluate("el=>getComputedStyle(el).display") != "none"
            checks.append("safe_cover_focus_" + slug)
        await choose_view(page, "home")
        await page.locator('[data-hero-index="1"]').click()
        assert await page.locator("#heroImage").evaluate("el=>el.style.objectPosition") == "50% 100%"
        assert await page.locator('.cartridge-right img').evaluate("el=>el.style.objectPosition") == "50% 100%"
        checks.append("cover_focus_applies_to_hero")
        await page.locator('#heroPlayButton').click()
        await continue_without_rotation(page)
        await expect(page.locator("#helpDialog")).to_be_visible()
        assert await page.locator(".help-cover img").evaluate("el=>el.style.objectPosition") == "50% 100%"
        checks.append("cover_focus_applies_to_tutorial_art")
        await page.locator('[data-help-action="cancel"]').click()
        return {"scenario": "cover_focus_validation", "passed": True, "checks": checks,
                "scope": "Real catalog; only focus values overridden inside isolated browser. Invalid CSS, types and out-of-range percentages must fall back."}
    except Exception as error:
        return {"scenario": "cover_focus_validation", "passed": False, "checks": checks, "error": str(error), "error_type": type(error).__name__}


def scenario_plan(name):
    plan = [({"browser": name, "viewport": f"{width}x{height}"}, run_viewport, (name, width, height)) for width, height in VIEWPORTS]
    if name == "chromium":
        plan.extend([({"browser": name, "scenario": "cover_focus_validation"}, run_cover_focus, ()),
                     ({"browser": name, "scenario": "guest_and_ranking"}, run_guest_and_ranking, ())])
    plan.extend([({"browser": name, "scenario": "landscape_rotation"}, run_orientation, (name,)),
                 ({"browser": name, "scenario": "desktop_orientation"}, run_desktop_orientation, (name,))])
    return plan


async def run_engine(browser_type, name):
    plan = scenario_plan(name)
    browser = None
    results = []
    infrastructure_errors = []
    unavailable_reason = None
    try:
        browser = await browser_type.launch(headless=True)
        for identity, function, arguments in plan:
            if unavailable_reason or not browser.is_connected():
                result = {**identity, "passed": False, "status": "blocked", "checks": [],
                          "error": unavailable_reason or "Browser disconnected before this scenario started"}
            else:
                try:
                    result = {**identity, **await function(browser, *arguments)}
                except Exception as error:
                    result = {**identity, "passed": False, "checks": [],
                              "error": str(error), "error_type": type(error).__name__}
                result["status"] = "passed" if result["passed"] else "failed"
                if result.get("cleanup_errors"):
                    unavailable_reason = "Previous context could not close; clean scenario isolation is unavailable"
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as error:
        # A browser that could not launch, or stopped responding, must not turn
        # the scenarios abandoned afterward into successful/omitted results.
        for identity, _, _ in plan[len(results):]:
            results.append({**identity, "passed": False, "status": "blocked", "checks": [],
                            "error": str(error), "error_type": type(error).__name__})
    finally:
        if browser is not None:
            try:
                await asyncio.wait_for(browser.close(), DIAGNOSTIC_TIMEOUT_SECONDS)
            except Exception as error:
                infrastructure_errors.append({"browser": name, "operation": "browser.close",
                                              "error": str(error), "error_type": type(error).__name__})
    return results, infrastructure_errors


def summarize(results, prepared, infrastructure_errors):
    executed = sum(result["status"] != "blocked" for result in results)
    failed = sum(result["status"] == "failed" for result in results)
    blocked = sum(result["status"] == "blocked" for result in results)
    return {"base_url": BASE_URL, "passed": bool(prepared) and len(results) == prepared and not failed and not blocked and not infrastructure_errors,
              "prepared": prepared, "executed": executed, "passed_scenarios": sum(result["status"] == "passed" for result in results),
              "failed": failed, "blocked": blocked,
              "scenarios": len(results), "checks": sum(len(result.get("checks", [])) for result in results),
              "infrastructure_errors": infrastructure_errors,
              "scope": "Portal UI and isolated Telegram integration; no physical Telegram or 142-game mechanics claim",
              "results": results}


async def main():
    assert urlparse(BASE_URL).scheme in {"http", "https"}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    infrastructure_errors = []
    engines = [name.strip() for name in os.getenv("TEST_BROWSERS", "chromium,firefox,webkit").split(",") if name.strip()]
    prepared = sum(len(scenario_plan(name)) for name in engines)
    async with async_playwright() as playwright:
        for name in engines:
            records, errors = await run_engine(getattr(playwright, name, None), name)
            results.extend(records)
            infrastructure_errors.extend(errors)
            report = summarize(results, prepared, infrastructure_errors)
            (OUTPUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report = summarize(results, prepared, infrastructure_errors)
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
