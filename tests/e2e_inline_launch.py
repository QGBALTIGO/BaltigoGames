"""Local Mini App routing/share protocol; no real Telegram account or message.

The portal/catalog/assets are real. Telegram SDK, browser share capabilities and
the small iframe player are explicit fixtures. This cannot prove BotFather setup,
Telegram photo retrieval, a physical client launch or a real inline message send.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlparse

import httpx
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8206').rstrip('/')
OUT = Path(os.getenv('TEST_OUTPUT_DIR', 'artifacts/inline-launch-e2e'))
TIMEOUT = 10000
FILES = ['web/app.js', 'web/index.html', 'web/styles.css', 'tests/e2e_inline_launch.py']
PLAYER = """<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Jogador isolado</title>
<body style="margin:0;background:#142139;color:white"><p>Jogador isolado do ensaio de abertura.</p>
<script>const slug=location.pathname.split('/').at(-2);parent.postMessage({type:'baltigo:ready',slug},location.origin);</script></body></html>"""
PLAN = [
    {'id': 'inline-header-catalog', 'mode': 'ios', 'share': 'inline'},
    {'id': 'url-startapp', 'mode': 'ios', 'query': {'startapp': 'snake'}, 'slug': 'snake', 'share': 'inline'},
    {'id': 'telegram-get-startparam-group', 'mode': 'ios', 'query': {'tgWebAppStartParam': 'chess'}, 'unsafe': {'chat_type': 'group', 'chat_instance': 'isolated-group-context'}, 'slug': 'chess', 'share': 'inline'},
    {'id': 'sdk-startparam-precedence', 'mode': 'ios', 'query': {'startapp': 'snake'}, 'unsafe': {'start_param': 'tetris', 'chat_type': 'supergroup', 'chat_instance': 'isolated-supergroup-context'}, 'slug': 'tetris', 'share': 'inline'},
    {'id': 'unknown-game-keeps-catalog', 'mode': 'ios', 'query': {'startapp': 'not-a-catalog-game'}, 'share': 'inline'},
    {'id': 'unknown-platform-native-share', 'mode': 'unknown', 'share': 'native'},
    {'id': 'older-sdk-native-share', 'mode': 'old', 'share': 'native'},
    {'id': 'missing-inline-method-native-share', 'mode': 'missing', 'share': 'native'},
    {'id': 'inline-method-failure-native-share', 'mode': 'throws', 'share': 'native', 'inline_attempts': 1},
    {'id': 'outside-telegram-clipboard', 'mode': 'browser', 'share': 'clipboard'},
]


def hashes():
    return {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in FILES}


def sdk_fixture(case):
    configuration = json.dumps({'mode': case['mode'], 'unsafe': case.get('unsafe', {})})
    return '''(()=>{
      const c=''' + configuration + ''';
      window.__inlineProof={inline:[],native:[],clipboard:[],fullscreen:[]};
      Object.defineProperty(navigator,'share',{configurable:true,value:c.mode==='browser'?undefined:async data=>{__inlineProof.native.push(data)}});
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{__inlineProof.clipboard.push(text)}}});
      if(c.mode==='browser'){window.Telegram=undefined;return;}
      window.__inlineEvents={};
      const version=c.mode==='old'?'6.6':'8.0';
      const app={initData:'',initDataUnsafe:c.unsafe,platform:c.mode==='unknown'?'unknown':'ios',version,
        isFullscreen:false,viewportHeight:innerHeight,
        safeAreaInset:{top:59,bottom:34,left:0,right:0},contentSafeAreaInset:{top:0,bottom:0,left:0,right:0},
        isVersionAtLeast(value){return Number.parseFloat(version)>=Number.parseFloat(value)},
        ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},setBottomBarColor(){},disableVerticalSwipes(){},enableVerticalSwipes(){},
        onEvent(name,fn){__inlineEvents[name]=fn},BackButton:{onClick(){},show(){},hide(){}},HapticFeedback:{impactOccurred(){}},
        requestFullscreen(){__inlineProof.fullscreen.push('enter');this.isFullscreen=true;__inlineEvents.fullscreenChanged?.()},
        exitFullscreen(){__inlineProof.fullscreen.push('exit');this.isFullscreen=false;__inlineEvents.fullscreenChanged?.()},
        switchInlineQuery(query,types){__inlineProof.inline.push({query,types});if(c.mode==='throws')throw new Error('Isolated SDK unsupported');}
      };
      if(c.mode==='missing')delete app.switchInlineQuery;
      window.Telegram={WebApp:app};
    })();'''


async def run_case(browser, engine, case, catalog):
    result = {'id': engine + '-' + case['id'], 'browser': engine, 'case': case,
              'passed': False, 'checks': [], 'writes': [], 'observed_non_get': [],
              'page_errors': [], 'api_requests': [], 'network': [], 'lifecycle': []}
    context, page = None, None
    started = time.perf_counter()
    pending = {}
    tracing = False
    def elapsed():
        return round(time.perf_counter() - started, 6)
    def request_started(request):
        info = {'url': request.url, 'method': request.method, 'type': request.resource_type, 'seconds': elapsed()}
        pending[id(request)] = info
        result['network'].append({'event': 'request', **info})
        if request.method != 'GET':
            result['observed_non_get'].append(info)
    def request_ended(request, failed=False):
        pending.pop(id(request), None)
        info = {'event': 'failed' if failed else 'finished', 'url': request.url, 'seconds': elapsed()}
        if failed:
            info['failure'] = request.failure
        else:
            info['timing'] = request.timing
        result['network'].append(info)
    try:
        context = await browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, locale='pt-BR')
        await context.tracing.start(screenshots=True, snapshots=True, sources=False)
        tracing = True
        context.on('request', request_started)
        context.on('requestfinished', request_ended)
        context.on('requestfailed', lambda request: request_ended(request, failed=True))
        context.on('response', lambda response: result['network'].append({'event': 'response', 'url': response.url, 'status': response.status, 'seconds': elapsed()}))
        async def guard(route):
            if route.request.method != 'GET':
                result['writes'].append({'method': route.request.method, 'url': route.request.url})
                await route.abort('blockedbyclient')
            else:
                await route.continue_()
        await context.route('**/*', guard)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT)
        page.on('pageerror', lambda error: result['page_errors'].append(error.stack or str(error)))
        page.on('domcontentloaded', lambda: result['lifecycle'].append({'event': 'domcontentloaded', 'seconds': elapsed()}))
        page.on('load', lambda: result['lifecycle'].append({'event': 'load', 'seconds': elapsed()}))
        page.on('close', lambda: result['lifecycle'].append({'event': 'page_close', 'seconds': elapsed()}))
        page.on('request', lambda request: result['api_requests'].append({'method': request.method, 'url': request.url}) if '/api/' in request.url else None)
        await page.route('https://telegram.org/js/telegram-web-app.js', lambda route: route.fulfill(status=200, content_type='application/javascript', body=sdk_fixture(case)))
        await page.route(re.compile(r'/play(?:-v[23])?/'), lambda route: route.fulfill(status=200, content_type='text/html', body=PLAYER))
        url = BASE + ('?' + urlencode(case['query']) if case.get('query') else '')
        await page.goto(url, wait_until='domcontentloaded')
        await expect(page.locator('#homeGrid .game-card').first).to_be_attached()
        if case.get('slug'):
            slug = case['slug']
            await expect(page.locator('#player')).to_be_visible()
            portrait = page.locator('[data-help-action="portrait-start"]')
            if await portrait.is_visible():
                await portrait.click()
            await expect(page.locator('#helpDialog')).to_be_visible()
            await expect(page.locator('#helpContent h2')).to_have_text(catalog[slug]['name'])
            await expect(page.locator('#playerFullscreen')).to_have_attribute('aria-pressed', 'true')
            assert await page.locator('#helpDialog').evaluate('el=>{const r=el.getBoundingClientRect();return r.top>=114&&r.bottom<=innerHeight-33}')
            await page.screenshot(path=str(OUT / (result['id'] + '-tutorial.png')), timeout=TIMEOUT)
            await page.locator('[data-help-action="start"]').click()
            await expect(page.locator('#playerLoader')).to_be_hidden()
            await expect(page.locator('#gameFrame')).to_have_attribute('src', '/play-v3/' + catalog[slug]['path'] + '?v=20261025-7')
            assert not await page.locator('.player-stage').evaluate('el=>el.classList.contains("is-rotated")')
            header = await page.locator('.player-bar').bounding_box()
            frame = await page.locator('#gameFrame').bounding_box()
            assert header and frame and header['y'] >= 115 and frame['y'] >= header['y'] + header['height'] - 1, (header, frame)
            assert header['x'] >= -1 and header['x'] + header['width'] <= 391 and frame['y'] + frame['height'] <= 811, (header, frame)
            for control in await page.locator('.player-bar button:visible').all():
                box = await control.bounding_box()
                assert box and box['width'] >= 44 and box['height'] >= 44
            await page.locator('#playerBack').click()
            await expect(page.locator('#player')).to_be_hidden()
            assert not await page.evaluate('Telegram.WebApp.isFullscreen')
            result['checks'].extend(['requested_slug_opens_exact_tutorial', 'exact_game_iframe_path', 'guest_fullscreen_safe115px', '44px_controls_without_forced_rotation', 'close_restores_catalog_and_exits_fullscreen'])
        else:
            await expect(page.locator('#homeGrid .game-card').first).to_be_visible()
            await expect(page.locator('#player')).to_be_hidden()
            await expect(page.locator('#helpDialog')).to_be_hidden()
            result['checks'].append('catalog_or_invalid_slug_does_not_open_arbitrary_game')
        await expect(page.locator('#profileName')).to_have_text('visitante')
        if case['mode'] != 'browser':
            assert await page.evaluate('Telegram.WebApp.initData===""&&!Telegram.WebApp.initDataUnsafe.user')
        result['checks'].append('inline_mode_without_user_identity_remains_guest')
        before_share = await page.evaluate('__inlineProof')
        assert not before_share['inline'] and not before_share['native'] and not before_share['clipboard'], before_share
        await page.locator('#shareCatalogButton').click()
        result['protocol'] = await page.evaluate('__inlineProof')
        protocol = result['protocol']
        expected_inline = 1 if case['share'] == 'inline' else case.get('inline_attempts', 0)
        assert len(protocol['inline']) == expected_inline, protocol
        for call in protocol['inline']:
            assert call == {'query': '', 'types': ['users', 'groups', 'channels']}, call
        if case['share'] == 'inline':
            assert not protocol['native'] and not protocol['clipboard'], protocol
            result['checks'].append('telegram_inline_guest_prefers_chat_picker_before_browser_share')
        elif case['share'] == 'native':
            assert len(protocol['native']) == 1 and protocol['native'][0]['url'] == BASE and not protocol['clipboard'], protocol
            result['checks'].append('unsupported_or_unknown_telegram_preserves_browser_native_share')
        else:
            assert protocol['clipboard'] == [BASE] and not protocol['native'] and not protocol['inline'], protocol
            await expect(page.locator('#toast')).to_contain_text('Link copiado')
            result['checks'].append('outside_telegram_preserves_clipboard_fallback')
        assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
        assert not result['writes'] and not result['observed_non_get'] and not result['page_errors'], result
        assert not any('/api/session' in call['url'] or '/api/runs' in call['url'] for call in result['api_requests']), result['api_requests']
        result['checks'].extend(['no_authenticated_session_or_ranking_write', 'no_horizontal_overflow_or_page_error', 'share_protocol_called_only_after_real_button_click'])
        result.update(passed=True, status='passed')
    except Exception as error:
        result.update(status='failed', error=str(error), error_type=type(error).__name__, failure_seconds=elapsed(),
                      pending_at_failure=list(pending.values()))
        if page:
            try:
                result['failure_dom'] = await asyncio.wait_for(page.evaluate('''()=>{
                  const b=document.querySelector('#shareCatalogButton'),p=document.querySelector('#player'),h=document.querySelector('#helpDialog');
                  return {url:location.href,ready:document.readyState,fonts:document.fonts.status,
                    shareCount:document.querySelectorAll('#shareCatalogButton').length,shareHTML:b?.outerHTML,shareRect:b?.getBoundingClientRect().toJSON(),
                    homeGames:document.querySelectorAll('#homeGrid .game-card').length,scrollY,
                    playerVisible:p?!p.hidden:null,helpOpen:h?.open,protocol:window.__inlineProof,
                    pendingImages:[...document.images].filter(x=>!x.complete).length};
                }'''), 3)
            except Exception as diagnostic:
                result['failure_dom_error'] = f'{type(diagnostic).__name__}: {diagnostic}'
            try:
                await asyncio.wait_for(page.screenshot(path=str(OUT / ('FAIL-' + result['id'] + '.png')), timeout=TIMEOUT), 10)
            except Exception as diagnostic:
                result['screenshot_error'] = f'{type(diagnostic).__name__}: {diagnostic}'
    finally:
        if context:
            if tracing:
                try:
                    keep_trace = not result['passed'] or (engine == 'firefox' and case['id'] == 'inline-header-catalog')
                    trace_path = OUT / (result['id'] + '-trace.zip') if keep_trace else None
                    await asyncio.wait_for(context.tracing.stop(path=str(trace_path) if trace_path else None), 10)
                    if trace_path:
                        result['trace'] = str(trace_path)
                except Exception as diagnostic:
                    result.update(passed=False, status='failed', trace_error=f'{type(diagnostic).__name__}: {diagnostic}')
            result['lifecycle'].append({'event': 'context_close_start', 'seconds': elapsed(), 'pending': list(pending.values())})
            try:
                await asyncio.wait_for(context.close(), 10)
                result['lifecycle'].append({'event': 'context_close_done', 'seconds': elapsed()})
            except Exception as error:
                result.update(passed=False, status='failed', cleanup_error=f'{type(error).__name__}: {error}')
                result['lifecycle'].append({'event': 'context_close_failed', 'seconds': elapsed(), 'pending': list(pending.values())})
    (OUT / (result['id'] + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result.get(key) for key in ['id', 'status', 'checks', 'error']}, ensure_ascii=False), flush=True)
    return result


async def main():
    assert urlparse(BASE).hostname in {'127.0.0.1', 'localhost', '::1'}, 'This SDK fixture suite is restricted to the isolated local server'
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'report.json').exists(), 'Preserve earlier evidence with a new TEST_OUTPUT_DIR'
    async with httpx.AsyncClient() as client:
        response = await client.get(BASE + '/api/catalog', timeout=30)
        response.raise_for_status()
        catalog = {game['slug']: game for game in response.json()['games']}
    engines = [value.strip() for value in os.getenv('TEST_BROWSERS', 'chromium,firefox,webkit').split(',') if value.strip()]
    report = {'base': BASE, 'prepared': len(PLAN) * len(engines), 'results': [], 'hashes_before': hashes(),
              'scope': 'Real local portal/catalog/assets; explicit guest SDK, browser-share and iframe fixtures. No BotFather/getMe claim, real Telegram account/message, production request, game playthrough or write.'}
    async with async_playwright() as playwright:
        for engine in engines:
            browser = None
            try:
                browser = await getattr(playwright, engine).launch(headless=True)
                for case in PLAN:
                    if not browser.is_connected():
                        raise RuntimeError('Browser disconnected before next scenario')
                    result = await run_case(browser, engine, case, catalog)
                    report['results'].append(result)
                    if 'cleanup_error' in result:
                        raise RuntimeError('Context isolation unavailable after cleanup failure')
            except Exception as error:
                already = sum(r['browser'] == engine for r in report['results'])
                for case in PLAN[already:]:
                    report['results'].append({'browser': engine, 'case': case, 'status': 'blocked', 'passed': False, 'checks': [], 'error': str(error)})
            finally:
                if browser:
                    try:
                        await asyncio.wait_for(browser.close(), 10)
                    except Exception as error:
                        report.setdefault('infrastructure_errors', []).append({'browser': engine, 'error': str(error)})
    report['hashes_after'] = hashes()
    report['source_unchanged'] = report['hashes_before'] == report['hashes_after']
    report['executed'] = sum(r['status'] != 'blocked' for r in report['results'])
    report['passed_scenarios'] = sum(r['passed'] for r in report['results'])
    report['failed'] = sum(r['status'] == 'failed' for r in report['results'])
    report['blocked'] = sum(r['status'] == 'blocked' for r in report['results'])
    report['checks'] = sum(len(r['checks']) for r in report['results'])
    report['passed'] = bool(report['prepared']) and len(report['results']) == report['prepared'] == report['passed_scenarios'] and report['source_unchanged'] and not report.get('infrastructure_errors')
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['passed', 'prepared', 'executed', 'passed_scenarios', 'failed', 'blocked', 'checks', 'source_unchanged']}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
