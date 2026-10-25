"""Real mobile controls through the portal's rotated iframe, without game fixtures.

Only Telegram's external SDK is replaced, as an unauthenticated guest with native
safe areas. Catalog, API, game documents, assets, physics and inputs are real.
Run: python tests/e2e_rotated_gameplay.py --base http://127.0.0.1:8195
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SLUGS = ["cannon-blaster", "abhita", "football", "table-tennis"]
SDK = """window.Telegram={WebApp:{initData:'',initDataUnsafe:{},platform:'android',
viewportHeight:844,isFullscreen:false,safeAreaInset:{top:60,bottom:20,left:0,right:0},
contentSafeAreaInset:{top:38,bottom:14,left:0,right:0},ready(){},expand(){},
setHeaderColor(){},setBackgroundColor(){},setBottomBarColor(){},
disableVerticalSwipes(){},enableVerticalSwipes(){},onEvent(){},
BackButton:{onClick(){},show(){},hide(){}},HapticFeedback:{impactOccurred(){}},
requestFullscreen(){},exitFullscreen(){}}};"""
SCENE = """const games=window.__baltigo?.games||[];
const scene=games.flatMap(g=>g.scene.getScenes(true)).find(s=>s.sys.settings.key===key);
if(!scene)throw Error('Active scene missing: '+key);"""


def hashes():
    paths = ["app/main.py", "app/game_runtime.py", "web/game-runtime.js", "web/app.js",
             "web/index.html", "web/styles.css", "data/config-overrides.json",
             "web/covers/planet-visitor.webp"]
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


async def main(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    before_hashes = hashes()
    report = {"base": args.base, "viewport": {"width": 390, "height": 844},
              "scope": "Real portal rotation dialog, real touch/CDP gestures and read-only source state; no game/API mocks, outcome fixtures, handler invocation or score writes.",
              "sdk": "Guest SDK presentation only; initData empty; top safe area 98px, bottom 34px.",
              "results": [], "cleanup_errors": [], "source_hashes_before": before_hashes}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--use-angle=swiftshader-webgl"])
        try:
            for slug in args.slugs:
                result = {"slug": slug, "passed": False, "checks": [], "gestures": []}
                context = await browser.new_context(viewport={"width": 390, "height": 844},
                                                    is_mobile=True, has_touch=True, device_scale_factor=2)
                page = await context.new_page()
                page.set_default_timeout(30000)
                errors, failed_requests, writes = [], [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("requestfailed", lambda request: failed_requests.append({"url": request.url, "failure": request.failure}))
                page.on("request", lambda request: writes.append({"method": request.method, "url": request.url}) if request.method not in {"GET", "HEAD"} else None)
                await page.route("https://telegram.org/js/telegram-web-app.js", lambda route: route.fulfill(content_type="application/javascript", body=SDK))
                try:
                    await page.goto(args.base, wait_until="domcontentloaded")
                    await page.locator('[data-view-target="explore"]:visible').first.tap()
                    card = page.locator('#exploreGrid [data-game="' + slug + '"]')
                    await card.scroll_into_view_if_needed()
                    await card.tap()
                    await page.locator('[data-help-action="rotate-start"]').tap()
                    await page.locator('[data-help-action="start"]').tap()
                    await page.locator("#playerLoader").wait_for(state="hidden")
                    await page.locator(".player-stage.is-rotated").wait_for()
                    frame = await page.locator("#gameFrame").element_handle()
                    frame = await frame.content_frame()
                    assert frame is not None and "/play-v3/" in frame.url, frame.url if frame else None
                    await frame.wait_for_function("document.querySelector('meta[name=\"baltigo-adapter\"]')!==null")
                    cdp = await context.new_cdp_session(page)

                    async def local_point(x, y):
                        box = await page.locator("#gameFrame").bounding_box()
                        assert box
                        point = {"x": box["x"] + box["width"] - y, "y": box["y"] + x}
                        assert 0 <= point["x"] <= 390 and 0 <= point["y"] <= 844, point
                        return point

                    async def object_point(key, expression):
                        local = await frame.evaluate("""({key,expression})=>{""" + SCENE + """
                          const object=eval(expression), b=object.getBounds();
                          const c=scene.cameras.main,r=scene.game.canvas.getBoundingClientRect();
                          const p=c.matrix.transformPoint(b.centerX-c.scrollX,b.centerY-c.scrollY);
                          return{x:r.x+p.x/scene.scale.gameSize.width*r.width,y:r.y+p.y/scene.scale.gameSize.height*r.height};
                        }""", {"key": key, "expression": expression})
                        return await local_point(local["x"], local["y"])

                    async def world_point(key, x, y):
                        local = await frame.evaluate("""({key,x,y})=>{""" + SCENE + """
                          const c=scene.cameras.main,r=scene.game.canvas.getBoundingClientRect();
                          const p=c.matrix.transformPoint(x-c.scrollX,y-c.scrollY);
                          return{x:r.x+p.x/scene.scale.gameSize.width*r.width,y:r.y+p.y/scene.scale.gameSize.height*r.height};
                        }""", {"key": key, "x": x, "y": y})
                        return await local_point(local["x"], local["y"])

                    async def dom_point(selector):
                        local = await frame.locator(selector).evaluate("el=>{const r=el.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}}")
                        return await local_point(local["x"], local["y"])

                    async def tap(point, description):
                        await page.touchscreen.tap(point["x"], point["y"])
                        result["gestures"].append({"action": "tap", "description": description, **point})

                    async def touch(point, event):
                        await cdp.send("Input.dispatchTouchEvent", {"type": event, "touchPoints": [] if event == "touchEnd" else [{**point, "id": 1, "radiusX": 1, "radiusY": 1, "force": 1}]})

                    async def hold(point, milliseconds, read):
                        started = asyncio.get_running_loop().time()
                        await touch(point, "touchStart")
                        try:
                            await page.wait_for_timeout(milliseconds)
                            state = await read()
                        finally:
                            await touch(point, "touchEnd")
                        result["gestures"].append({"action": "hold", "requested_delay_ms": milliseconds,
                                                   "observed_duration_ms": round((asyncio.get_running_loop().time() - started) * 1000), **point})
                        return state

                    async def drag(start, end):
                        await touch(start, "touchStart")
                        try:
                            for step in range(1, 13):
                                t = step / 12
                                await touch({"x": start["x"] + (end["x"] - start["x"]) * t,
                                             "y": start["y"] + (end["y"] - start["y"]) * t}, "touchMove")
                                await page.wait_for_timeout(20)
                        finally:
                            await touch(end, "touchEnd")
                        result["gestures"].append({"action": "drag", "from": start, "to": end, "steps": 12})

                    async def scene_state(key, expression):
                        return await frame.evaluate("""({key,expression})=>{""" + SCENE + "return eval(expression)}", {"key": key, "expression": expression})

                    async def wait_scene(key):
                        await frame.wait_for_function("key=>(window.__baltigo?.games||[]).some(g=>g.loop.frame>3&&g.scene.getScenes(true).some(s=>s.sys.settings.key===key))", arg=key)
                        await page.wait_for_timeout(150)

                    geometry = await page.locator("#gameFrame").bounding_box()
                    result.update(iframe_url=frame.url, rotated_iframe_box=geometry)
                    result["checks"].append("real_orientation_dialog_rotates_v3_iframe")
                    await page.screenshot(path=str(out / f"{slug}-rotated-menu.png"))

                    if slug == "cannon-blaster":
                        key = "GameScene"
                        await wait_scene(key)
                        await tap(await object_point(key, "scene.playButton"), "Iniciar canhão pelo botão real")
                        await frame.wait_for_function("()=>window.__baltigo.games.some(g=>g.scene.getScenes(true).some(s=>s.isGameStarted))")
                        read = lambda: scene_state(key, "({started:scene.isGameStarted,ended:scene.hasEnded,paused:scene.isPaused,x:scene.cannon.x,score:scene.score,lives:scene.lives,frame:scene.game.loop.frame})")
                        before = await read()
                        await drag(await world_point(key, 650, 800), await world_point(key, 1450, 800))
                        after = await read()
                        assert after["started"] and not after["paused"] and not after["ended"] and after["x"] > before["x"] + 150, (before, after)
                        result.update(before=before, after=after)
                        result["checks"].append("rotated_real_drag_moves_cannon_in_live_round")
                    elif slug == "abhita":
                        key = "GamePlayScene"
                        await wait_scene(key)
                        await tap(await object_point(key, "scene.startOverlay.list.find(o=>o.input?.enabled)"), "Iniciar quebra-cabeça no botão real")
                        await frame.wait_for_function("()=>window.__baltigo.games.some(g=>g.scene.getScenes(true).some(s=>s.state==='playing'))")
                        read = lambda: scene_state(key, "({state:scene.state,pieces:scene.pieces.map(p=>({idx:p.puzzle.idx,x:p.x,y:p.y,width:p.displayWidth,height:p.displayHeight,...p.puzzle})),frame:scene.game.loop.frame})")
                        before = await read()
                        piece = before["pieces"][-1]
                        start = await object_point(key, "scene.pieces.at(-1)")
                        end = await world_point(key, piece["targetX"] + piece["width"] / 2, piece["targetY"] + piece["height"] / 2)
                        await drag(start, end)
                        await page.wait_for_timeout(250)
                        after = await read()
                        placed = after["pieces"][-1]
                        assert placed["placed"] and abs(placed["x"] - placed["targetX"]) < 2 and abs(placed["y"] - placed["targetY"]) < 2, (piece, placed)
                        assert sum(p["placed"] for p in after["pieces"]) == 1 and after["state"] == "playing"
                        result.update(before=before, after=after)
                        result["checks"].append("rotated_real_drag_places_one_puzzle_piece_with_camera_zoom")
                    elif slug == "football":
                        await frame.locator("#startOverlay .btns button").wait_for()
                        await tap(await dom_point("#startOverlay .btns button"), "Iniciar futebol pelo botão real")
                        await frame.wait_for_function("()=>gameStarted===true")
                        async def read():
                            return await frame.evaluate("()=>({started:gameStarted,x:player.x,y:player.y,vx:player.vx,vy:player.vy,left:keys.ArrowLeft,right:keys.ArrowRight,scoreLeft,scoreRight})")
                        before = await read()
                        right = await hold(await dom_point('[data-action="right"]'), 240, read)
                        left = await hold(await dom_point('[data-action="left"]'), 240, read)
                        assert right["x"] > before["x"] + 30 and left["x"] < right["x"] - 30 and right["right"] and left["left"], (before, right, left)
                        result.update(before=before, right_held=right, after=left)
                        result["checks"].append("rotated_real_direction_buttons_move_football_player_both_ways")
                    else:
                        await wait_scene("MainMenuScene")
                        await tap(await object_point("MainMenuScene", "scene.children.list.find(o=>o.input?.enabled&&(o.texture?.key==='playbtn'||/jogar|play/i.test(o.text||'')))"), "Iniciar tênis de mesa pelo botão real")
                        key = "GameScene"
                        await wait_scene(key)
                        read = lambda: scene_state(key, "({y:scene.player.y,bodyY:scene.player.body.y,bodyPrevY:scene.player.body.prev.y,bodyHeight:scene.player.body.height,displayHeight:scene.player.displayHeight,top:scene.gp.arenaInset+scene.player.displayHeight/2,bottom:scene.H-scene.gp.arenaInset-scene.player.displayHeight/2,mobile:{...scene._mobile},score:{...scene.state},frame:scene.game.loop.frame})")
                        before = await read()
                        traces = {}
                        async def trace(direction):
                            samples = []
                            for _ in range(20):
                                await page.wait_for_timeout(50)
                                samples.append(await read())
                            traces[direction] = samples
                            return samples[-1]
                        up = await hold(await object_point(key, "scene.children.list.find(o=>o.texture?.key==='btn_left'&&o.input?.enabled)"), 0, lambda: trace("up"))
                        await frame.wait_for_function("()=>window.__baltigo.games.some(g=>g.scene.getScenes(true).some(s=>s._mobile&&!s._mobile.up&&!s._mobile.down))")
                        down = await hold(await object_point(key, "scene.children.list.find(o=>o.texture?.key==='btn_right'&&o.input?.enabled)"), 0, lambda: trace("down"))
                        await frame.wait_for_function("()=>window.__baltigo.games.some(g=>g.scene.getScenes(true).some(s=>s._mobile&&!s._mobile.up&&!s._mobile.down))")
                        released = await read()
                        result.update(before=before, up_held=up, after=down, released=released, movement_samples=traces)
                        for direction, sign in [("up", -1), ("down", 1)]:
                            samples = traces[direction]
                            assert all(s["mobile"][direction] for s in samples), samples
                            assert all(s["top"] - 1 <= s["y"] <= s["bottom"] + 1 for s in samples), samples
                            deltas = [sign * (b["y"] - a["y"]) for a, b in zip(samples, samples[1:])]
                            body_deltas = [sign * (b["bodyY"] - a["bodyY"]) for a, b in zip(samples, samples[1:])]
                            assert sum(delta > 0 for delta in deltas) >= 5 and sum(deltas) > 100, (direction, deltas)
                            assert sum(delta > 0 for delta in body_deltas) >= 5 and sum(body_deltas) > 100, (direction, body_deltas)
                            assert all(delta >= -1 for delta in deltas + body_deltas), (direction, deltas, body_deltas)
                        assert up["y"] < before["y"] - 100 and down["y"] > up["y"] + 100, (before, up, down)
                        assert not released["mobile"]["up"] and not released["mobile"]["down"]
                        result["checks"].append("rotated_real_direction_buttons_move_table_tennis_paddle_both_ways")
                    await page.screenshot(path=str(out / f"{slug}-rotated-active.png"))
                    assert not errors, errors
                    assert not writes, writes
                    assert not failed_requests, failed_requests
                    result["checks"].extend(["no_javascript_or_network_failures", "guest_has_no_session_or_ranking_writes"])
                    result["passed"] = True
                except Exception as error:
                    result.update(error=f"{type(error).__name__}: {error}")
                    try:
                        await asyncio.wait_for(page.screenshot(path=str(out / f"FAIL-{slug}.png"), timeout=10000), 12)
                    except Exception as diagnostic_error:
                        result["diagnostic_error"] = f"{type(diagnostic_error).__name__}: {diagnostic_error}"
                finally:
                    result.update(javascript_errors=errors, request_failures=failed_requests, writes=writes)
                    try:
                        await asyncio.wait_for(context.close(), 10)
                    except Exception as error:
                        result["passed"] = False
                        result["cleanup_error"] = f"{type(error).__name__}: {error}"
                    report["results"].append(result)
                    (out / f"{slug}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(json.dumps({"slug": slug, "passed": result["passed"], "error": result.get("error")}), flush=True)
        finally:
            try:
                await asyncio.wait_for(browser.close(), 10)
            except Exception as error:
                report["cleanup_errors"].append(f"{type(error).__name__}: {error}")
    report["source_hashes_after"] = hashes()
    report["source_unchanged"] = before_hashes == report["source_hashes_after"]
    report["passed"] = len(report["results"]) == len(args.slugs) and all(r["passed"] for r in report["results"]) and report["source_unchanged"] and not report["cleanup_errors"]
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8195")
    parser.add_argument("--out", default="artifacts/rotated-gameplay-v3")
    parser.add_argument("--slugs", nargs="+", choices=SLUGS, default=SLUGS, help="Narrow retests; default runs all four games")
    raise SystemExit(asyncio.run(main(parser.parse_args())))

