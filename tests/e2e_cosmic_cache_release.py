"""Real browser disk cache for the V5 -> V6 Cosmic HUD update.

The GET-only HTTP proxy serves the immutable V5 shell plus actual public V5
games, then the real local candidate. No Playwright routes are installed.
Only the external Telegram SDK is removed from this isolated guest context.
"""
from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit

import httpx
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
GAME = 'games/3d/cosmic-cleaner/'
OLD_FRAME = '/play-v3/' + GAME + 'index.html?v=20261025-7'
NEW_FRAME = '/play-v3/' + GAME + 'index.html?v=20261025-8'
OLD_MODULE = '/play-v3/' + GAME + 'mechanics.js'
NEW_MODULE = OLD_MODULE + '?v=20261025-hud2'
OTHER_FRAME = '/play-v3/games/arcade/snake/index.html?v=20261025-7'
SCENE = """const game=window.__baltigo?.games?.[0];
const scene=game?.scene.getScenes(true).find(s=>s.sys.settings.key==='MechanicsScene');
if(!scene)throw Error('Actual Cosmic scene missing');"""


def source_hashes():
    return {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in [
        'app/main.py', 'app/game_runtime.py', 'app/source_repairs.py', 'web/app.js',
        'web/index.html', 'web/styles.css', 'web/game-runtime.js', 'web/game-localization.js',
    ]}


async def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    old_html = subprocess.check_output(['git', 'show', args.old_commit + ':web/index.html'], cwd=ROOT)
    old_app = subprocess.check_output(['git', 'show', args.old_commit + ':web/app.js'], cwd=ROOT)
    assert b'app.js?v=20261025-arcade-6' in old_html
    assert b"els.frame.src=`/play-v3/${game.path}?v=20261025-7`" in old_app
    client = httpx.Client(timeout=45, follow_redirects=True, headers={'Accept-Encoding': 'identity'})
    served, proxy_errors, rejected_writes, cleanup_errors = [], [], [], []
    release = {'mode': 'old'}
    expected = {}
    report = {'passed': False, 'checks': [], 'previous': args.old_base, 'candidate': args.base,
              'previous_commit': args.old_commit, 'scope': 'Actual public V5 and candidate Cosmic through a GET-only HTTP cache proxy; a persistent Chromium profile proves fromDiskCache. No API, auth or game mocks; no game state assignments or outcome fixtures; external SDK removed only for this guest context.',
              'source_hashes_before': before}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            rejected_writes.append({'method': 'POST', 'path': self.path})
            self.send_error(405, 'GET-only cache proof never forwards writes')

        def do_GET(self):
            path = urlsplit(self.path).path
            try:
                mode = release['mode']
                if path == '/' and mode == 'old':
                    body, mime, base = old_html, 'text/html; charset=utf-8', 'git:' + args.old_commit
                elif self.path == '/static/app.js?v=20261025-arcade-6':
                    body, mime, base = old_app, 'application/javascript', 'git:' + args.old_commit
                else:
                    base = args.old_base if mode == 'old' else args.base
                    response = client.get(base.rstrip('/') + self.path)
                    response.raise_for_status()
                    body, mime = response.content, response.headers.get('content-type', 'application/octet-stream')
                if path == '/':
                    sdk = b'<script src="https://telegram.org/js/telegram-web-app.js"></script>'
                    assert sdk in body
                    body = body.replace(sdk, b'<script>window.Telegram=undefined;</script>')
                cache = 'no-cache' if path == '/' else ('no-store' if path.startswith('/api/') and path != '/api/catalog' else 'public, max-age=3600')
                served.append({'mode': mode, 'base': base, 'path': self.path, 'sha256': sha256(body).hexdigest(), 'bytes': len(body), 'cache_control': cache})
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', cache)
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:
                proxy_errors.append({'path': self.path, 'type': type(error).__name__})
                self.send_error(502, 'Cache proof upstream unavailable')

    server = None
    try:
        for label, base, path in [('old_html', args.old_base, OLD_FRAME), ('old_module', args.old_base, OLD_MODULE),
                                  ('new_html', args.base, NEW_FRAME), ('new_module', args.base, NEW_MODULE),
                                  ('old_other', args.old_base, OTHER_FRAME), ('new_other', args.base, OTHER_FRAME)]:
            response = client.get(base.rstrip('/') + path)
            response.raise_for_status()
            expected[label] = {'sha256': sha256(response.content).hexdigest(), 'bytes': len(response.content)}
            if label == 'old_html':
                assert b"from './mechanics.js'" in response.content and b'20261025-hud2' not in response.content
            if label == 'new_html':
                assert b"from './mechanics.js?v=20261025-hud2'" in response.content
            if label == 'new_module':
                assert b'this.__baltigoHudPlate.setDepth(1);' in response.content
                assert b'label => label.setDepth(2)' in response.content
        assert expected['old_module']['sha256'] != expected['new_module']['sha256']
        assert expected['old_other'] == expected['new_other'], 'Unrelated Snake HTML changed'
        report['checks'].append('actual_public_v5_and_candidate_sources_confirmed_before_browser')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        async with async_playwright() as playwright:
            with tempfile.TemporaryDirectory(prefix='baltigo-cosmic-browser-cache-') as profile:
                async def browser_context():
                    context = await playwright.chromium.launch_persistent_context(
                        profile, viewport={'width': 1440, 'height': 1000},
                        args=['--use-angle=swiftshader-webgl'])
                    return context

                async def close_context(context):
                    try:
                        await asyncio.wait_for(context.close(), 15)
                    except Exception as error:
                        cleanup_errors.append({'operation': 'context.close', 'type': type(error).__name__, 'error': str(error)})

                async def capture_failure(page, phase, error):
                    report['primary_error'] = {'phase': phase, 'type': type(error).__name__, 'error': str(error)}
                    try:
                        await page.screenshot(path=str(out / (phase + '-failed.png')), timeout=5000)
                    except Exception as capture_error:
                        report['failure_capture_error'] = type(capture_error).__name__

                async def open_game(page, slug, expected_src):
                    await page.locator('[data-view-target="explore"]:visible').first.click()
                    card = page.locator('#exploreGrid [data-game="' + slug + '"]')
                    await card.scroll_into_view_if_needed()
                    await card.click()
                    await page.wait_for_function("()=>document.querySelector('#helpDialog')?.open || document.querySelector('#gameFrame')?.getAttribute('src')?.startsWith('/play-v3/')")
                    help_start = page.locator('[data-help-action="start"]')
                    if await help_start.is_visible():
                        await page.locator('#skipGameTutorial').check()
                        await help_start.click()
                    await expect(page.locator('#playerLoader')).to_be_hidden(timeout=60000)
                    assert await page.locator('#gameFrame').get_attribute('src') == expected_src
                    frame = await (await page.locator('#gameFrame').element_handle()).content_frame()
                    assert frame is not None
                    await frame.wait_for_function("()=>window.__baltigo?.games?.some(g=>g.loop.frame>3&&g.scene.getScenes(true).some(s=>s.children.list.length&&!s.load?.isLoading()))", timeout=60000)
                    return frame

                async def digest(page, path):
                    return await page.evaluate("async path=>{const r=await fetch(path);if(!r.ok)throw Error('GET failed');const b=await crypto.subtle.digest('SHA-256',await r.arrayBuffer());return Array.from(new Uint8Array(b),v=>v.toString(16).padStart(2,'0')).join('');}", path)

                # Close/reopen the browser with the same profile, making the
                # old source's disk-cache evidence stronger than memory cache.
                context = await browser_context()
                try:
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.bring_to_front()
                    page.set_default_timeout(30000)
                    await page.goto(origin, wait_until='domcontentloaded')
                    await expect(page.locator('#homeGrid .game-card').first).to_be_visible()
                    await open_game(page, 'cosmic-cleaner', OLD_FRAME)
                    assert await digest(page, OLD_MODULE) == expected['old_module']['sha256']
                    await page.wait_for_load_state('networkidle')
                except Exception as error:
                    await capture_failure(page, 'warm-old', error)
                    raise
                finally:
                    await close_context(context)
                report['checks'].append('previous_cosmic_v7_plain_module_warmed_in_persistent_browser_profile')

                context = await browser_context()
                try:
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.bring_to_front()
                    page.set_default_timeout(30000)
                    errors, writes, responses = [], [], []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('request', lambda request: writes.append({'method': request.method, 'url': request.url}) if request.method not in {'GET', 'HEAD'} else None)
                    cdp = await context.new_cdp_session(page)
                    await cdp.send('Network.enable')
                    cdp.on('Network.responseReceived', lambda event: responses.append({'url': event['response']['url'], 'fromDiskCache': event['response'].get('fromDiskCache', False), 'status': event['response']['status']}))
                    await page.goto(origin, wait_until='domcontentloaded')
                    await expect(page.locator('#homeGrid .game-card').first).to_be_visible()
                    old_frame = await open_game(page, 'cosmic-cleaner', OLD_FRAME)
                    disk_hits = [item for item in responses if item['url'] == origin + OLD_MODULE and item['fromDiskCache']]
                    assert disk_hits, 'Old Cosmic module was not loaded from the actual disk cache'
                    assert await digest(page, OLD_MODULE) == expected['old_module']['sha256']
                    report['checks'].append('cdp_fromDiskCache_confirms_actual_previous_cosmic_js_bytes')

                    async def snapshot(frame):
                        return await frame.evaluate('()=>{' + SCENE + "return {timeOrigin:performance.timeOrigin,frame:game.loop.frame,started:scene.gameStarted,plate:scene.__baltigoHudPlate.depth,labels:[scene.batteryBar,scene.scoreText,scene.shieldBar].map(t=>({text:t.text,depth:t.depth}))};}")

                    async def real_start(frame):
                        point = await frame.evaluate('()=>{' + SCENE + "const walk=o=>[o,...(o.list||[]).flatMap(walk)];const btn=scene.children.list.flatMap(walk).find(o=>(o.texture?.key==='playbtn'||o.name==='playbtn')&&o.input?.enabled);if(!btn)throw Error('Native Play control missing');const b=btn.getBounds(),c=game.canvas.getBoundingClientRect();return {x:c.x+(b.x+b.width/2)*c.width/game.scale.gameSize.width,y:c.y+(b.y+b.height/2)*c.height/game.scale.gameSize.height};}")
                        box = await page.locator('#gameFrame').bounding_box()
                        assert box
                        await page.mouse.click(box['x'] + point['x'], box['y'] + point['y'])
                        await frame.wait_for_function('()=>{' + SCENE + 'return scene.gameStarted===true;}')

                    await real_start(old_frame)
                    old_state = await snapshot(old_frame)
                    assert old_state['plate'] == 0 and all(row['depth'] == 0 for row in old_state['labels'])
                    release['mode'] = 'new'
                    served_before = len(served)
                    await page.wait_for_timeout(500)
                    kept = await snapshot(old_frame)
                    assert kept['timeOrigin'] == old_state['timeOrigin'] and kept['started']
                    assert kept['frame'] > old_state['frame']
                    assert await page.locator('#gameFrame').get_attribute('src') == OLD_FRAME
                    assert not any('20261025-hud2' in item['path'] for item in served[served_before:])
                    report['checks'].append('existing_actual_round_keeps_same_document_and_advances_after_server_switch')
                    await page.screenshot(path=str(out / 'v5-cached-cosmic-preserved.png'))
                    await page.locator('#playerBack').click()
                    await page.goto(origin, wait_until='domcontentloaded')
                    await expect(page.locator('#homeGrid .game-card').first).to_be_visible()
                    assert await page.locator('script[src*="/static/app.js"]').get_attribute('src') == '/static/app.js?v=20261025-arcade-7'
                    assert await page.locator('link[rel="stylesheet"]').get_attribute('href') == '/static/styles.css?v=20261025-arcade-5'
                    report['checks'].append('new_home_fetches_app7_while_styles5_remains_unchanged')
                    start_index = len(responses)
                    new_frame = await open_game(page, 'cosmic-cleaner', NEW_FRAME)
                    assert await new_frame.locator('script[src*="game-localization.js"]').get_attribute('src') == '/static/game-localization.js?v=20261025-8'
                    assert await new_frame.locator('script[src*="game-runtime.js"]').get_attribute('src') == '/static/game-runtime.js?v=20261025-7'
                    await real_start(new_frame)
                    new_state = await snapshot(new_frame)
                    assert new_state['plate'] == 1 and all(row['depth'] == 2 for row in new_state['labels'])
                    assert new_state['timeOrigin'] != old_state['timeOrigin']
                    assert await digest(page, NEW_FRAME) == expected['new_html']['sha256']
                    assert await digest(page, NEW_MODULE) == expected['new_module']['sha256']
                    fetched = responses[start_index:]
                    for path in [NEW_FRAME, NEW_MODULE]:
                        actual = [item for item in fetched if item['url'] == origin + path]
                        assert actual and not actual[0]['fromDiskCache'], ('New version reused an old cache entry', path, actual)
                    assert any(item['path'] == NEW_FRAME and item['base'] == args.base for item in served)
                    assert any(item['path'] == NEW_MODULE and item['base'] == args.base for item in served)
                    report['checks'].extend(['new_cosmic_frame_v8_and_hud2_module_fetch_actual_new_sha', 'new_actual_round_has_hud_plate_depth1_and_all_labels_depth2', 'runtime7_and_dictionary8_preserved'])
                    await page.screenshot(path=str(out / 'v6-new-cosmic-hud2.png'))
                    await page.locator('#playerBack').click()
                    other = await open_game(page, 'snake', OTHER_FRAME)
                    assert await other.locator('meta[name="baltigo-adapter"]').get_attribute('content') == '20261025-7'
                    assert await digest(page, OTHER_FRAME) == expected['old_other']['sha256']
                    assert not any('20261025-hud2' in item['url'] for item in responses if '/games/arcade/snake/' in item['url'])
                    report['checks'].append('unrelated_game_keeps_frame_v7_and_byte_identical_html')
                    assert not errors and not writes and not rejected_writes and not proxy_errors, (errors, writes, rejected_writes, proxy_errors)
                    report['checks'].append('no_javascript_errors_or_forwarded_writes_or_api_auth_mocks')
                    report.update(passed=True, old_state=old_state, preserved_state=kept, new_state=new_state,
                                  disk_cache_hits=disk_hits, browser_responses=responses, browser_errors=errors, writes=writes)
                except Exception as error:
                    await capture_failure(page, 'cache-transition', error)
                    raise
                finally:
                    await close_context(context)
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        client.close()
        after = source_hashes()
        report.update(expected_bodies=expected, source_hashes_after=after, source_unchanged=before == after,
                      served=served, proxy_errors=proxy_errors, rejected_writes=rejected_writes, cleanup_errors=cleanup_errors)
        report['passed'] = report['passed'] and before == after and not cleanup_errors and not proxy_errors and not rejected_writes
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in {'served', 'browser_responses', 'expected_bodies', 'source_hashes_before', 'source_hashes_after'}}, ensure_ascii=True))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8197')
    parser.add_argument('--old-base', default='https://games.187-77-255-164.sslip.io')
    parser.add_argument('--old-commit', default='0f9519c69df473e8ecd5ffe6dce5e5122fd0c5f9')
    parser.add_argument('--out', default='artifacts/cosmic-cache-v6')
    raise SystemExit(asyncio.run(run(parser.parse_args())))
