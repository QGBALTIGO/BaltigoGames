"""Real portal → signed API → isolated SQLite → visible ranking integration.

Only the Telegram SDK/identity is synthetic. API requests and the game runtime
are real; terminal-state fixtures exercise the game's native completion code.
Run against tests/load_app.py, never a public server or a production database.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from load_test import init_data
from audit_round_transitions import INSPECT, FIXTURE


async def run(args):
    parsed = urlparse(args.base)
    assert parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}, 'Loopback test fixture only'
    out = ROOT/args.out
    out.mkdir(parents=True, exist_ok=True)
    responses, errors = [], []
    sdk = """window.Telegram={WebApp:{initData:SIGNED,initDataUnsafe:{user:{id:IDENTITY,first_name:'Integração isolada'}},platform:'android',viewportHeight:innerHeight,viewportStableHeight:innerHeight,ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},setBottomBarColor(){},disableVerticalSwipes(){},enableVerticalSwipes(){},onEvent(){},BackButton:{onClick(){},show(){},hide(){}},HapticFeedback:{impactOccurred(){}}}};"""
    identity_index = int(time.time())
    sdk = sdk.replace('SIGNED', json.dumps(init_data(identity_index))).replace('IDENTITY', str(9_000_000_000+identity_index))
    result = {'scope':__doc__, 'base':args.base, 'passed':False, 'checks':[]}
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--use-angle=swiftshader-webgl', '--disable-background-timer-throttling'])
        context = await browser.new_context(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True, locale='pt-BR')
        await context.route('https://telegram.org/js/telegram-web-app.js', lambda route:route.fulfill(body=sdk, content_type='application/javascript'))
        page = await context.new_page()
        page.on('pageerror', lambda error:errors.append(str(error)))

        async def collect(response):
            path = urlparse(response.url).path
            if path.startswith('/api/') and path != '/api/catalog':
                body = await response.json()
                if path == '/api/session':
                    body = {'user':body.get('user'), 'guest':body.get('guest')}
                responses.append({'path':path, 'method':response.request.method, 'status':response.status, 'body':body})
        page.on('response', collect)

        async def await_count(suffix, count, timeout=20):
            deadline = time.monotonic()+timeout
            while time.monotonic() < deadline:
                matches = [r for r in responses if r['path'].endswith(suffix) and r['method']=='POST']
                if len(matches) >= count:
                    return matches
                await page.wait_for_timeout(100)
            raise AssertionError(f'Expected {count} real API responses ending {suffix}')

        async def click_target(target):
            box = await page.locator('#gameFrame').bounding_box()
            await page.touchscreen.tap(box['x']+target['x'], box['y']+target['y'])

        async def start():
            child = page.frames[-1]
            await child.wait_for_function("window.__baltigo?.games?.some(g=>g.scene.getScenes(true).some(s=>s.children.list.length&&!s.load.isLoading()))", timeout=30000)
            state = await child.evaluate(INSPECT)
            targets = [t for t in state['targets'] if any(k in t['label'].lower() for k in ['play', 'jogar', 'start']) and not any(k in t['label'].lower() for k in ['replay', 'restart', 'new_round'])]
            assert targets, state
            await click_target(targets[0])
            await child.wait_for_function('() => {const d=('+INSPECT+")();return d.scenes.length>0&&!d.scenes.some(s=>s.ended||s.playing===false)&&!d.targets.some(t=>/play|jogar|start/i.test(t.label)&&!/replay|restart|new_round/i.test(t.label));}", timeout=15000)
            return child

        try:
            await page.goto(args.base+'/?startapp=buttermilk', wait_until='domcontentloaded')
            await expect(page.locator('[data-help-action="start"]')).to_be_visible(timeout=20000)
            await page.screenshot(path=str(out/'tutorial.png'))
            await page.locator('[data-help-action="start"]').click()
            child = await start()
            await await_count('/api/runs', 1)
            await page.wait_for_timeout(16500)
            await child.evaluate(FIXTURE)
            await child.wait_for_function("window.__baltigo.status==='finished'", timeout=15000)
            finish = (await await_count('/finish', 1))[0]
            assert finish['status']==200 and finish['body']['accepted'] and finish['body']['points'] >= 1, finish
            first = await child.evaluate(INSPECT)
            next_target = next(t for t in first['targets'] if t['next'])
            await page.screenshot(path=str(out/'result.png'))
            await click_target(next_target)
            await child.wait_for_function('old=>performance.timeOrigin!==old&&window.__baltigo?.status', arg=first['boot'], timeout=20000)
            child = await start()
            await await_count('/api/runs', 2)
            second = await child.evaluate(INSPECT)
            assert second['boot'] != first['boot'] and second['status'] != 'finished' and not second['paused'], second
            await child.evaluate(FIXTURE)
            await await_count('/finish', 2)
            await page.locator('#playerBack').click()
            await page.locator('.bottom-nav [data-view-target="ranking"]').click()
            await expect(page.locator('#rankingEntries .ranking-row--me')).to_be_visible(timeout=15000)
            points = int(await page.locator('#rankingEntries .ranking-row--me .ranking-points').inner_text())
            assert points >= finish['body']['points']
            starts = [r['body']['run_id'] for r in responses if r['path']=='/api/runs' and r['method']=='POST']
            finishes = [r for r in responses if r['path'].endswith('/finish')]
            assert len(starts)==2 and len(set(starts))==2 and len(finishes)==2, (starts, finishes)
            assert all(r['status']==200 for r in responses), responses
            assert not errors, errors
            await page.screenshot(path=str(out/'persisted-ranking.png'))
            result.update(passed=True, points=points, checks=['signed synthetic Telegram identity accepted by real API', 'native tutorial and actual start gesture', 'real heartbeat intervals and durable participation point', 'native completion and one real finish request', 'actual Next gesture creates fresh playable document and distinct ranked run', 'second native finish remains single', 'persisted points visible in real ranking UI', 'zero API or JavaScript errors'])
        except Exception as error:
            result['error'] = repr(error)
            try:await page.screenshot(path=str(out/'FAIL.png'))
            except Exception:pass
        finally:
            result.update(errors=errors, responses=responses)
            (out/'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            await browser.close()
    print(json.dumps({k:v for k,v in result.items() if k not in {'responses', 'scope'}}, ensure_ascii=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8192')
    parser.add_argument('--out', default='artifacts/live-ranking-integration')
    raise SystemExit(asyncio.run(run(parser.parse_args())))
