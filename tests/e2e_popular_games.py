"""Top10 UI journeys with real local portal/catalog/covers and explicit API fixtures.

Only the popularity response, guest Telegram SDK and tiny player are isolated.
No real account, ranking write, 142-game playthrough or physical Telegram claim.
Run with TEST_BASE_URL=http://127.0.0.1:<bot-free-port> python tests/e2e_popular_games.py.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8190').rstrip('/')
OUT = Path(os.getenv('TEST_OUTPUT_DIR', 'artifacts/popular-games-e2e'))
TIMEOUT = 10000
PLAY_ROUTE = re.compile(r'/play(?:-v[23])?/')
SLUGS = ['snake', 'tetris', 'chess', '2048', 'car-race', 'bubble-shooter',
         'pacman', 'crossy-road', 'fruit-merge', 'spaceman']
PLAYS = [1234, 300, 99, 80, 60, 35, 20, 10, 3, 1]
CATEGORIES = {'puzzle': 'Quebra-cabeças', 'arcade': 'Fliperama', 'shooter': 'Tiro',
              'racing': 'Corrida', 'sports': 'Esportes', 'platformer': 'Plataforma',
              'casual': 'Casuais', 'board': 'Tabuleiro', 'word-quiz': 'Palavras e perguntas',
              '3d': 'Jogos em 3D'}
FILES = ['web/app.js', 'web/index.html', 'web/styles.css', 'app/main.py',
         'app/leaderboard.py', 'data/catalog-pt.json', 'tests/e2e_popular_games.py']
SDK = """
window.__popularFullscreenCalls=[];window.__popularTgHandlers={};
window.Telegram={WebApp:{initData:'',initDataUnsafe:{},version:'8.0',platform:'ios',
isFullscreen:false,viewportHeight:innerHeight,
safeAreaInset:{top:44,bottom:34,left:0,right:0},contentSafeAreaInset:{top:54,bottom:0,left:0,right:0},
ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},setBottomBarColor(){},
disableVerticalSwipes(){},enableVerticalSwipes(){},isVersionAtLeast(){return true},
onEvent(name,fn){__popularTgHandlers[name]=fn},BackButton:{onClick(){},show(){},hide(){}},
HapticFeedback:{impactOccurred(){}},
requestFullscreen(){__popularFullscreenCalls.push('enter');this.isFullscreen=true;__popularTgHandlers.fullscreenChanged?.()},
exitFullscreen(){__popularFullscreenCalls.push('exit');this.isFullscreen=false;__popularTgHandlers.fullscreenChanged?.()}
}};
"""
PLAYER = """<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Jogador isolado do ensaio Top10</title><body style="margin:0;background:#0b1830;color:white">
<p>Partida isolada para verificar abertura do portal.</p><script>
parent.postMessage({type:'baltigo:ready',slug:'snake'},location.origin);
addEventListener('message',event=>window.__lastPause=event.data);
</script></body></html>"""


def hashes():
    return {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in FILES}


def payload(entries):
    return {'games': [{'slug': slug, 'plays': plays} for slug, plays in entries],
            'updated_at': '2026-10-26T03:00:00Z', 'period': 'all',
            'total_plays': sum(plays for _, plays in entries),
            'minimum_active_seconds': 15, 'verified': False,
            'trust_policy': 'Partidas registradas após pelo menos 15 segundos de atividade. A atividade informada pelo navegador não é verificada de forma independente.'}


class PopularFixture:
    def __init__(self, data=None, status=200, hold=False):
        self.data = data if data is not None else payload(list(zip(SLUGS, PLAYS)))
        self.status = status
        self.calls = []
        self.gate = asyncio.Event()
        if not hold:
            self.gate.set()

    async def route(self, route):
        request = route.request
        self.calls.append({'method': request.method, 'url': request.url,
                           'authorization': request.headers.get('authorization')})
        if request.method != 'GET':
            await route.abort('blockedbyclient')
            return
        status, body = self.status, self.data
        await self.gate.wait()
        await route.fulfill(status=status, json=body if status == 200 else {'detail': 'Falha isolada do ensaio'})


async def no_overflow(page):
    value = await page.evaluate('({document:document.documentElement.scrollWidth,viewport:innerWidth})')
    assert value['document'] <= value['viewport'] + 1, value
    return value


async def safe_target(locator):
    box = await locator.bounding_box()
    assert box and box['width'] >= 44 and box['height'] >= 44, box
    return box


async def expect_ready(page, fixture, checks, count=10):
    section = page.locator('#popularSection')
    await expect(section).to_have_attribute('data-state', 'ready')
    await expect(section).to_have_attribute('aria-busy', 'false')
    await expect(page.locator('#popularList')).to_be_visible()
    await expect(page.locator('#popularList > li[data-popular-game]')).to_have_count(count)
    assert len(fixture.calls) == 1, fixture.calls
    assert all(call['method'] == 'GET' and 'limit=10' in call['url'] and not call['authorization'] for call in fixture.calls)
    assert await section.get_attribute('aria-labelledby') == 'popularTitle' or await section.get_attribute('aria-label')
    assert not await section.evaluate('el=>/\\p{Extended_Pictographic}/u.test(el.innerText)')
    checks.extend(['public_get_limit10_without_authorization', 'ready_state_not_busy', 'exact_api_card_count', 'named_section_without_text_emojis'])


async def cards(page, entries, catalog, checks):
    section, rail = page.locator('#popularSection'), page.locator('#popularList')
    actual = await rail.locator('li[data-popular-game]').evaluate_all('(els)=>els.map(el=>el.dataset.popularGame)')
    assert actual == [slug for slug, _ in entries], actual
    await expect(rail).to_have_js_property('tagName', 'OL')
    if await rail.get_attribute('role') is not None:
        await expect(rail).to_have_attribute('role', 'list')
    metrics = []
    for index, (slug, plays) in enumerate(entries, 1):
        card = rail.locator(f'li[data-popular-game="{slug}"]')
        launch = card.locator(f'button[data-game="{slug}"]')
        catalog_name = catalog[slug].get('name_pt') or catalog[slug]['name']
        # Existing portal aliases can differ from the localized catalog name.
        # The visible and spoken names must agree; slug/order/counts remain exact.
        name = (await card.locator('.popular-name').inner_text()).strip()
        assert name
        await expect(card).to_contain_text(CATEGORIES[catalog[slug]['category']])
        await expect(card.locator('[data-popular-rank]')).to_have_text(f'{index:02}')
        formatted = f'{plays:,}'.replace(',', '.')
        label = f'{formatted} partida registrada' if plays == 1 else f'{formatted} partidas registradas'
        await expect(card.locator('[data-popular-plays]')).to_have_text(label)
        await expect(launch).to_have_accessible_name(f'Jogar {name}, posição {index} entre os mais jogados, {label}')
        image = card.locator('img')
        await image.scroll_into_view_if_needed()
        await expect(image).to_have_attribute('src', re.compile(r'^/static/covers/' + re.escape(slug) + r'\.webp(?:\?|$)'))
        await page.wait_for_function('(slug)=>{const i=document.querySelector(`#popularList li[data-popular-game="${slug}"] img`);return i?.complete&&i.naturalWidth>0}', arg=slug)
        assert await image.get_attribute('alt') is not None
        await safe_target(launch)
        metric = await card.evaluate('el=>({slug:el.dataset.popularGame,playsFont:parseFloat(getComputedStyle(el.querySelector("[data-popular-plays]")).fontSize),rect:{width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height}})')
        metric.update(catalog_name=catalog_name, visible_name=name)
        metrics.append(metric)
    assert all(item['playsFont'] >= 12 for item in metrics), metrics
    assert 'mais jogad' in (await section.inner_text()).lower()
    checks.extend(['server_order_preserved', 'positions_match_card_order', 'real_catalog_cover_images_loaded', 'accessible_game_buttons', 'portuguese_categories', 'portuguese_registered_plays_and_singular', '44px_game_targets', 'registered_count_at_least12px'])
    return metrics


async def settled_rail(page):
    # A new click during smooth scroll can reach a disabled edge by the time
    # actionability runs. Observe native scrollend and actual position stability.
    return await asyncio.wait_for(page.evaluate('''()=>new Promise(resolve=>{
      const rail=document.querySelector('#popularList');
      let previous=rail.scrollLeft,quietSince=performance.now(),ended=false;
      const start=quietSince,onEnd=()=>{ended=true};
      rail.addEventListener('scrollend',onEnd);
      const sample=()=>{
        const now=performance.now(),current=rail.scrollLeft;
        if(Math.abs(current-previous)>.05){previous=current;quietSince=now;}
        if(now-quietSince>=150){
          rail.removeEventListener('scrollend',onEnd);
          resolve({scrollLeft:current,previousDisabled:document.querySelector('#popularPrev').disabled,
            nextDisabled:document.querySelector('#popularNext').disabled,observedScrollEnd:ended,
            quietMs:now-quietSince,elapsedMs:now-start});
        }else requestAnimationFrame(sample);
      };requestAnimationFrame(sample);
    })'''), TIMEOUT / 1000)


async def reset_rail(page, diagnostics=None):
    previous = page.locator('#popularPrev')
    for _ in range(12):
        state = await settled_rail(page)
        if diagnostics is not None:
            diagnostics.append(state)
        if state['previousDisabled']:
            assert state['scrollLeft'] <= 2, state
            return
        await previous.click()
    state = await settled_rail(page)
    assert state['previousDisabled'] and state['scrollLeft'] <= 2, state


async def open_first(page, checks, keyboard=False, result=None):
    await reset_rail(page, result.setdefault('rail_resets', []) if result is not None else None)
    launch = page.locator('#popularList button[data-game="snake"]')
    if keyboard:
        await launch.focus()
        await expect(launch).to_be_focused()
        focus = await launch.evaluate('el=>({outline:getComputedStyle(el).outlineStyle,shadow:getComputedStyle(el).boxShadow})')
        assert focus['outline'] != 'none' or focus['shadow'] != 'none', focus
        await page.keyboard.press('Enter')
        checks.append('keyboard_enter_opens_popular_game')
    else:
        await launch.click()
        checks.append('popular_game_uses_existing_open_flow')
    portrait = page.locator('[data-help-action="portrait-start"]')
    if await portrait.is_visible():
        await portrait.click()
    await expect(page.locator('#helpDialog')).to_be_visible()
    await expect(page.locator('#helpContent h2')).not_to_be_empty()
    await page.locator('[data-help-action="start"]').click()
    await expect(page.locator('#playerLoader')).to_be_hidden()
    await expect(page.locator('#gameFrame')).to_have_attribute('src', re.compile(r'^/play-v3/games/arcade/snake/index\.html\?v=20261025-7$'))
    await expect(page.locator('#playerFullscreen')).to_have_attribute('aria-pressed', 'true')
    assert not await page.locator('.player-stage').evaluate('el=>el.classList.contains("is-rotated")')
    before = await page.locator('#playerFavorite').get_attribute('aria-pressed')
    await page.locator('#playerFavorite').click()
    await expect(page.locator('#playerFavorite')).to_have_attribute('aria-pressed', 'false' if before == 'true' else 'true')
    await page.locator('#playerFullscreen').click()
    await expect(page.locator('#playerFullscreen')).to_have_attribute('aria-pressed', 'false')
    await page.locator('#playerFullscreen').click()
    await expect(page.locator('#playerFullscreen')).to_have_attribute('aria-pressed', 'true')
    header = await page.locator('.player-bar').bounding_box()
    frame = await page.locator('#gameFrame').bounding_box()
    assert header and frame and header['y'] >= 98 and frame['y'] >= header['y'] + header['height'] - 1, (header, frame)
    for button in await page.locator('.player-bar button:visible').all():
        await safe_target(button)
    await page.locator('#playerBack').click()
    await expect(page.locator('#player')).to_be_hidden()
    assert not await page.evaluate('Telegram.WebApp.isFullscreen')
    assert not await page.locator('#app').evaluate('el=>el.inert')
    if keyboard:
        await expect(launch).to_be_focused()
        checks.append('keyboard_launcher_focus_restored_on_exit')
    checks.extend(['existing_tutorial_and_player_loaded', 'existing_player_favorite_works', 'fullscreen_toggle_does_not_rotate_game', '44px_safe_player_controls', 'exit_clears_fullscreen_and_restores_library'])


async def full_case(page, fixture, catalog, checks, result):
    section = page.locator('#popularSection')
    await expect(section).to_have_attribute('data-state', 'loading')
    await expect(section).to_have_attribute('aria-busy', 'true')
    await expect(page.locator('#popularLoading')).to_be_visible()
    await expect(page.locator('#popularList li[data-popular-game]')).to_have_count(0)
    checks.append('loading_does_not_invent_games_or_plays')
    fixture.gate.set()
    await expect_ready(page, fixture, checks)
    result['card_metrics'] = await cards(page, list(zip(SLUGS, PLAYS)), catalog, checks)
    await reset_rail(page, result.setdefault('rail_resets', []))
    for selector in ['#popularPrev', '#popularNext']:
        await safe_target(page.locator(selector))
        await expect(page.locator(selector)).to_have_accessible_name(re.compile('.+'))
    initial = await page.locator('#popularList').evaluate('el=>el.scrollLeft')
    await page.locator('#popularNext').click()
    await page.wait_for_function('before=>document.querySelector("#popularList").scrollLeft>before+10', arg=initial)
    await reset_rail(page, result['rail_resets'])
    checks.extend(['44px_rail_navigation', 'next_and_previous_scroll_real_rail', 'native_scroll_settles_before_next_click'])
    result['geometry'] = await no_overflow(page)
    await section.scroll_into_view_if_needed()
    await page.screenshot(path=str(OUT / (result['id'] + '-ready.png')), timeout=TIMEOUT)
    await open_first(page, checks, result=result)
    await expect(page.locator('#popularList li[data-popular-game]')).to_have_count(10)
    assert len(fixture.calls) == 1, fixture.calls
    checks.extend(['return_home_preserves_top10', 'return_within_ttl_does_not_refetch_or_poll'])
    await no_overflow(page)


async def states_case(page, fixture, catalog, checks, result):
    await expect(page.locator('#popularSection')).to_have_attribute('data-state', 'error')
    await expect(page.locator('#popularError')).to_be_visible()
    await expect(page.locator('#popularLoading')).to_be_hidden()
    await expect(page.locator('#popularList li[data-popular-game]')).to_have_count(0)
    await safe_target(page.locator('#retryPopular'))
    await page.locator('#popularSection').scroll_into_view_if_needed()
    await page.screenshot(path=str(OUT / (result['id'] + '-error.png')), timeout=TIMEOUT)
    checks.extend(['api_error_has_real_retry', 'error_has_no_fabricated_top10'])
    fixture.status, fixture.data = 200, payload([])
    await page.locator('#retryPopular').click()
    await expect(page.locator('#popularSection')).to_have_attribute('data-state', 'empty')
    await expect(page.locator('#popularEmpty')).to_be_visible()
    await expect(page.locator('#popularList')).to_be_hidden()
    await expect(page.locator('#popularList li[data-popular-game]')).to_have_count(0)
    assert len(fixture.calls) == 2, fixture.calls
    checks.extend(['retry_performs_second_public_get', 'zero_returns_empty_without_featured_fallback'])
    await page.screenshot(path=str(OUT / (result['id'] + '-empty.png')), timeout=TIMEOUT)
    await page.locator('#popularEmpty [data-go="explore"]').click()
    await expect(page.locator('[data-view="explore"]')).to_be_visible()
    checks.append('empty_explore_cta_works')
    entries = [('snake', 12), ('tetris', 2), ('chess', 1)]
    fixture.data = payload(entries)
    await page.reload(wait_until='domcontentloaded')
    await expect(page.locator('#popularSection')).to_have_attribute('data-state', 'ready')
    await expect(page.locator('#popularList li[data-popular-game]')).to_have_count(3)
    assert len(fixture.calls) == 3, fixture.calls
    result['card_metrics'] = await cards(page, entries, catalog, checks)
    checks.append('fewer_than10_stays_three_without_fillers')
    await no_overflow(page)
    await page.locator('#popularSection').scroll_into_view_if_needed()
    await page.screenshot(path=str(OUT / (result['id'] + '-three.png')), timeout=TIMEOUT)


async def keyboard_case(page, fixture, catalog, checks, result):
    await expect_ready(page, fixture, checks)
    rail = page.locator('#popularList')
    await rail.focus()
    await expect(rail).to_be_focused()
    await page.keyboard.press('ArrowRight')
    await page.wait_for_function('document.querySelector("#popularList").scrollLeft>10')
    await page.keyboard.press('ArrowLeft')
    await page.wait_for_function('document.querySelector("#popularList").scrollLeft<=1')
    assert await page.evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches')
    motion = await rail.locator('*').evaluate_all('(els)=>els.map(el=>({animation:getComputedStyle(el).animationName,transition:getComputedStyle(el).transitionDuration})).filter(s=>s.animation!=="none"||s.transition.split(",").some(t=>parseFloat(t)>0))')
    assert not motion, motion
    checks.extend(['rail_is_keyboard_focusable', 'arrow_keys_scroll_real_rail', 'reduced_motion_has_no_rail_animation_or_transition'])
    await open_first(page, checks, keyboard=True, result=result)
    await no_overflow(page)


async def scenario(browser, engine, kind, width, height, catalog):
    result = {'id': f'{engine}-{kind}-{width}x{height}', 'browser': engine,
              'scenario': kind, 'viewport': [width, height], 'passed': False, 'checks': []}
    context = None
    fixture = PopularFixture(status=503 if kind == 'states' else 200, hold=kind == 'full')
    errors, writes, api_requests, bad_images = [], [], [], []
    page = None
    try:
        context = await browser.new_context(viewport={'width': width, 'height': height}, has_touch=width <= 390,
                                            locale='pt-BR', reduced_motion='reduce' if kind == 'keyboard' else 'no-preference')
        async def guard(route):
            if route.request.method != 'GET':
                writes.append({'method': route.request.method, 'url': route.request.url})
                await route.abort('blockedbyclient')
            else:
                await route.continue_()
        await context.route('**/*', guard)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT)
        page.on('pageerror', lambda error: errors.append(error.stack or str(error)))
        page.on('request', lambda request: api_requests.append({'method': request.method, 'url': request.url}) if '/api/' in request.url else None)
        page.on('response', lambda response: bad_images.append({'url': response.url, 'status': response.status}) if '/static/covers/' in response.url and response.status >= 400 else None)
        await page.route('https://telegram.org/js/telegram-web-app.js', lambda route: route.fulfill(status=200, content_type='application/javascript', body=SDK))
        await page.route('**/api/games/popular**', fixture.route)
        await page.route(PLAY_ROUTE, lambda route: route.fulfill(status=200, content_type='text/html', body=PLAYER))
        await page.goto(BASE, wait_until='domcontentloaded')
        await expect(page.locator('#homeGrid .game-card').first).to_be_visible()
        await {'full': full_case, 'states': states_case, 'keyboard': keyboard_case}[kind](page, fixture, catalog, result['checks'], result)
        assert not errors and not writes and not bad_images, (errors, writes, bad_images)
        assert not any('/api/session' in r['url'] or '/api/runs' in r['url'] for r in api_requests), api_requests
        assert all(c['method'] == 'GET' and not c['authorization'] for c in fixture.calls), fixture.calls
        result['checks'].extend(['no_authenticated_session_or_ranking_write', 'no_page_or_cover_http_errors'])
        result.update(passed=True, status='passed')
    except Exception as error:
        result.update(status='failed', error=str(error), error_type=type(error).__name__)
        if page:
            try:
                await asyncio.wait_for(page.screenshot(path=str(OUT / ('FAIL-' + result['id'] + '.png')), timeout=TIMEOUT), 10)
            except Exception as diagnostic:
                result['screenshot_error'] = f'{type(diagnostic).__name__}: {diagnostic}'
    finally:
        fixture.gate.set()
        if context:
            try:
                await asyncio.wait_for(context.close(), 10)
            except Exception as error:
                result.update(passed=False, status='failed', cleanup_error=f'{type(error).__name__}: {error}')
        result.update(page_errors=errors, non_get_attempts=writes, popularity_requests=fixture.calls, api_requests=api_requests, cover_http_errors=bad_images)
    (OUT / (result['id'] + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result.get(k) for k in ['id', 'status', 'error', 'checks']}, ensure_ascii=False), flush=True)
    return result


async def main():
    assert urlparse(BASE).hostname in {'127.0.0.1', 'localhost', '::1'}, 'This fixture suite is restricted to the isolated local server'
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'report.json').exists(), 'Preserve previous evidence; choose a new TEST_OUTPUT_DIR'
    async with httpx.AsyncClient() as client:
        response = await client.get(BASE + '/api/catalog', timeout=30)
        response.raise_for_status()
        catalog = {game['slug']: game for game in response.json()['games']}
    assert all(slug in catalog for slug in SLUGS)
    plan = [('full', 320, 740), ('full', 390, 844), ('full', 1440, 1000), ('states', 390, 844), ('keyboard', 1440, 1000)]
    engines = [value.strip() for value in os.getenv('TEST_BROWSERS', 'chromium,firefox,webkit').split(',') if value.strip()]
    report = {'base': BASE, 'prepared': len(plan) * len(engines), 'results': [], 'hashes_before': hashes(),
              'scope': 'Real local portal/catalog/covers. Popularity API/guest SDK/player are explicit isolated fixtures; no real account, DB writes, 142-game mechanics or physical Telegram validation.'}
    async with async_playwright() as playwright:
        for engine in engines:
            browser = None
            try:
                browser = await getattr(playwright, engine).launch(headless=True)
                for index, (kind, width, height) in enumerate(plan):
                    if not browser.is_connected():
                        raise RuntimeError('Browser disconnected before the next scenario started')
                    item = await scenario(browser, engine, kind, width, height, catalog)
                    report['results'].append(item)
                    if item.get('cleanup_error'):
                        for next_kind, next_width, next_height in plan[index + 1:]:
                            report['results'].append({'browser': engine, 'scenario': next_kind, 'viewport': [next_width, next_height],
                                                      'status': 'blocked', 'passed': False, 'checks': [], 'error': 'Previous context could not close; clean scenario isolation is unavailable'})
                        break
            except Exception as error:
                remaining = plan[sum(r['browser'] == engine for r in report['results']):]
                for kind, width, height in remaining:
                    report['results'].append({'browser': engine, 'scenario': kind, 'viewport': [width, height],
                                              'status': 'blocked', 'passed': False, 'checks': [], 'error': str(error)})
            finally:
                if browser:
                    try:
                        await asyncio.wait_for(browser.close(), 10)
                    except Exception as error:
                        report.setdefault('infrastructure_errors', []).append({'browser': engine, 'operation': 'browser.close', 'error': str(error)})
    report['hashes_after'] = hashes()
    report['source_unchanged'] = report['hashes_before'] == report['hashes_after']
    report['executed'] = sum(r['status'] != 'blocked' for r in report['results'])
    report['passed_scenarios'] = sum(r['passed'] for r in report['results'])
    report['failed'] = sum(r['status'] == 'failed' for r in report['results'])
    report['blocked'] = sum(r['status'] == 'blocked' for r in report['results'])
    report['checks'] = sum(len(r['checks']) for r in report['results'])
    report['passed'] = report['prepared'] == len(report['results']) and report['passed_scenarios'] == report['prepared'] and report['source_unchanged'] and not report.get('infrastructure_errors')
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['passed', 'prepared', 'executed', 'passed_scenarios', 'failed', 'blocked', 'checks', 'source_unchanged']}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
