"""142 real catalog tutorials in four viewports; guest, before game loading.

Only Telegram SDK/insets/fullscreen events are simulated. Catalog, UI, fonts and
covers are real HTTP responses. No API/game-frame routes are mocked; no session,
run, score, game result or database write is created. This is tutorial/layout QA,
not a gameplay qualification or a physical Telegram test.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import sys
from urllib.parse import urlparse

from PIL import Image, ImageDraw
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8190').rstrip('/')
OUT = ROOT / os.getenv('TEST_OUTPUT_DIR', 'artifacts/catalog-tutorials-v5')
VIEWPORTS = [(320, 568), (390, 844), (844, 390), (1440, 900)]
if os.getenv('TEST_VIEWPORTS'):
    requested = [tuple(map(int, item.split('x'))) for item in os.environ['TEST_VIEWPORTS'].split(',')]
    assert requested and len(set(requested)) == len(requested) and all(size in VIEWPORTS for size in requested)
    VIEWPORTS = requested
TIMEOUT = 10000
SAFE = {'top': 98, 'bottom': 34, 'left': 0, 'right': 0}
SAMPLES = {'survivor', 'planet-visitor', 'tetris', 'connected'}
SOURCE_FILES = [
    'web/app.js', 'web/index.html', 'web/styles.css', 'web/game-runtime.js',
    'web/game-localization.js', 'data/catalog-pt.json', 'data/localization-pt.json',
    'app/main.py', 'app/game_runtime.py',
]

SDK = """
window.__tutorialSDK={events:{},fullscreenRequests:0,fullscreenExits:0};
window.Telegram={WebApp:{
  initData:'',initDataUnsafe:{},version:'8.0',platform:__PLATFORM__,
  isFullscreen:false,viewportHeight:innerHeight,viewportStableHeight:innerHeight,
  safeAreaInset:{top:44,bottom:34,left:0,right:0},
  contentSafeAreaInset:{top:54,bottom:0,left:0,right:0},
  ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},setBottomBarColor(){},
  isVersionAtLeast(){return true},disableVerticalSwipes(){},enableVerticalSwipes(){},
  onEvent(name,fn){(window.__tutorialSDK.events[name]||=[]).push(fn)},
  offEvent(name,fn){window.__tutorialSDK.events[name]=(window.__tutorialSDK.events[name]||[]).filter(x=>x!==fn)},
  BackButton:{onClick(){},show(){},hide(){}},HapticFeedback:{impactOccurred(){}},
  requestFullscreen(){window.__tutorialSDK.fullscreenRequests++;this.isFullscreen=true;
    for(const fn of window.__tutorialSDK.events.fullscreenChanged||[])fn()},
  exitFullscreen(){window.__tutorialSDK.fullscreenExits++;this.isFullscreen=false;
    for(const fn of window.__tutorialSDK.events.fullscreenChanged||[])fn()}
}};
"""

MEASURE = """() => {
 const d=document.querySelector('#helpDialog'),p=document.querySelector('.controls-box p');
 const box=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
 const text=[...d.querySelectorAll('.controls-box p,.tutorial-steps p')].map(e=>({text:e.textContent,fontSize:parseFloat(getComputedStyle(e).fontSize),lineHeight:parseFloat(getComputedStyle(e).lineHeight),clientWidth:e.clientWidth,scrollWidth:e.scrollWidth,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,...box(e)}));
 return{dialog:box(d),clientWidth:d.clientWidth,scrollWidth:d.scrollWidth,clientHeight:d.clientHeight,scrollHeight:d.scrollHeight,
   scrollTop:d.scrollTop,controls:p?.textContent,instructions:[...d.querySelectorAll('.tutorial-steps p')].map(e=>e.textContent),text,
   title:d.querySelector('h2')?.textContent,documentOverflow:document.documentElement.scrollWidth>innerWidth+1,
   rotated:document.querySelector('.player-stage')?.classList.contains('is-rotated'),
   frameSource:document.querySelector('#gameFrame')?.getAttribute('src'),
   cover:[...d.querySelectorAll('.help-cover img')].map(e=>({src:e.currentSrc,loaded:e.complete&&e.naturalWidth>0,...box(e)}))};
}"""


def snapshot() -> dict:
    result = {}
    for rel in SOURCE_FILES:
        path = ROOT / rel
        stat = path.stat()
        result[rel] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
    return result


async def failure_photo(page, name: str) -> dict:
    try:
        await asyncio.wait_for(page.screenshot(path=str(OUT / name), timeout=TIMEOUT), 10)
        return {'screenshot': name}
    except Exception as error:
        return {'screenshot_error': f'{type(error).__name__}: {error}'}


async def target_info(locator, dialog: bool) -> dict:
    return await locator.evaluate("""(e,inDialog)=>{
      const r=e.getBoundingClientRect(),d=document.querySelector('#helpDialog'),dr=d?.getBoundingClientRect();
      const x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y),style=getComputedStyle(e);
      const top=inDialog?Math.max(98,dr.top+d.clientTop):98;
      const bottom=inDialog?Math.min(innerHeight-34,dr.top+d.clientTop+d.clientHeight):innerHeight-110;
      return{x:r.x,y:r.y,width:r.width,height:r.height,centerX:x,centerY:y,top,bottom,
        inside:r.x>=0&&r.right<=innerWidth&&r.y>=top+1&&r.bottom<=bottom-1,
        receivesPointer:!!hit&&(hit===e||e.contains(hit)),visible:style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity)>0,
        dialogScroll:inDialog?d.scrollTop:null};
    }""", dialog)


async def real_scroll_to(page, locator, in_dialog: bool) -> dict:
    """Use real wheel input; no DOM scrollTop writes or hidden/forced clicks."""
    for step in range(24):
        info = await target_info(locator, in_dialog)
        if info['inside'] and info['receivesPointer'] and info['visible']:
            return {**info, 'wheel_steps': step}
        if in_dialog:
            rect = await page.locator('#helpDialog').bounding_box()
            assert rect is not None
            await page.mouse.move(rect['x'] + rect['width'] / 2,
                                  rect['y'] + min(rect['height'] - 5, max(5, rect['height'] / 2)))
        else:
            await page.mouse.move(page.viewport_size['width'] / 2, page.viewport_size['height'] / 2)
        # A fixed127px wheel step can jump over the entire65px valid interval
        # of a117px card in a182px safe region. Aim at the actual safe center,
        # keeping the same full-box and pointer-actionability requirements.
        delta = info['centerY'] - (info['top'] + info['bottom']) / 2
        if abs(delta) < 8:
            delta = -8 if info['y'] < info['top'] + 1 else 8
        amount = max(-280, min(280, delta))
        await page.mouse.wheel(0, amount)
        await page.wait_for_timeout(60)
    raise AssertionError(f'Control unreachable through real scrolling: {await target_info(locator,in_dialog)}')


async def assert_modal(page, width: int, height: int) -> dict:
    data = await page.evaluate(MEASURE)
    r = data['dialog']
    assert r['y'] >= SAFE['top'] - 1 and r['bottom'] <= height - SAFE['bottom'] + 1, ('native safe areas', r)
    assert r['x'] >= 0 and r['right'] <= width + 1, ('modal horizontal bounds', r)
    assert data['scrollWidth'] <= data['clientWidth'] + 1 and not data['documentOverflow'], 'Horizontal overflow'
    assert not data['rotated'], 'Game rotation must remain an explicit choice'
    assert not data['frameSource'] or data['frameSource'] == 'about:blank', 'A pre-game tutorial must not load the game'
    assert data['cover'] and all(item['loaded'] for item in data['cover']), 'Real tutorial cover not loaded'
    assert data['text'] and all(item['fontSize'] >= 14 for item in data['text']), ('Essential text below14CSSpx', data['text'])
    assert all(item['scrollWidth'] <= item['width'] + 1 for item in data['text']), 'Text box overflows horizontally'
    assert all(item['scrollHeight'] <= item['clientHeight'] + 1 for item in data['text']), 'Text box clips vertically'
    assert all(item['lineHeight'] >= item['fontSize'] * 1.35 for item in data['text']), 'Insufficient text line height'
    return data


async def open_tutorial(page, game: dict, first: bool, width: int, height: int) -> dict:
    await page.locator('#exploreSearch').fill(game['slug'])
    card = page.locator(f'#exploreGrid [data-game-card="{game["slug"]}"]')
    launch = card.locator('[data-game]')
    await expect(card).to_be_visible()
    await real_scroll_to(page, launch, False)
    await expect(card.locator('img')).to_have_js_property('complete', True)
    assert await card.locator('img').evaluate('e=>e.naturalWidth>0'), 'Real catalog cover failed'
    await launch.click()
    await expect(page.locator('#helpDialog')).to_be_visible()
    orientation = page.locator('[data-help-action="portrait-start"]')
    required = first and game.get('orientation') == 'landscape' and height > width and width < 1000
    if required:
        await expect(orientation).to_be_visible()
        assert not await page.locator('.player-stage').evaluate('e=>e.classList.contains("is-rotated")')
        geometry = await page.locator('#helpDialog').bounding_box()
        assert geometry and geometry['y'] >= SAFE['top'] - 1 and geometry['y'] + geometry['height'] <= height - SAFE['bottom'] + 1
        await real_scroll_to(page, orientation, True)
        await orientation.click()
    else:
        await expect(orientation).to_have_count(0)
    await expect(page.locator('.controls-box p')).to_be_visible()
    await page.wait_for_function("document.querySelector('.help-cover img')?.complete&&document.querySelector('.help-cover img').naturalWidth>0")
    return {'orientation_prompt': required, 'rotation_selected': False}


def write_contact(width: int, height: int, samples: list) -> str | None:
    if not samples:
        return None
    canvas = Image.new('RGB', (width * 2, (height + 30) * 2), '#080e1b')
    draw = ImageDraw.Draw(canvas)
    for i, (slug, data) in enumerate(samples[:4]):
        x, y = (i % 2) * width, (i // 2) * (height + 30)
        draw.text((x + 8, y + 8), f'{slug} | {width}x{height}', fill='#c5f86d')
        canvas.paste(Image.open(BytesIO(data)).convert('RGB'), (x, y + 30))
    name = f'contact-{width}x{height}.png'
    canvas.save(OUT / name)
    return name


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    local = json.loads((ROOT / 'data/catalog-pt.json').read_text(encoding='utf-8'))
    registry = json.loads((ROOT / 'data/registry.json').read_text(encoding='utf-8'))['games']
    all_slugs = [game['slug'] for game in registry]
    assert len(all_slugs) == 142 and len(set(all_slugs)) == 142 and all(local[slug].get('controls_pt') for slug in all_slugs)
    slugs = os.environ.get('TEST_SLUGS', '').split(',') if os.getenv('TEST_SLUGS') else all_slugs
    assert slugs and len(set(slugs)) == len(slugs) and all(slug in all_slugs for slug in slugs)
    expected_cases = len(slugs) * len(VIEWPORTS)
    before = snapshot()
    report = {'base_url': BASE_URL, 'prepared': expected_cases, 'executed': 0, 'passed_cases': 0, 'failed': 0, 'blocked': 0,
              'passed': False, 'scope': __doc__, 'viewports': VIEWPORTS,
              'started_utc': datetime.now(timezone.utc).isoformat(), 'sources_before': before,
              'environment': {'python': sys.version, 'platform': platform.platform(), 'playwright': version('playwright')},
              'sdk_fixture_sha256': hashlib.sha256(SDK.encode()).hexdigest(),
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'selected_slugs': slugs, 'real_api_catalog_expected': 142,
              'cases': [], 'profiles': [], 'infrastructure_errors': []}
    browser = None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            report['environment']['browser'] = browser.version
            for width, height in VIEWPORTS:
                context = None
                profile_result = {'viewport': f'{width}x{height}', 'api_writes': [], 'game_requests': [], 'errors': []}
                try:
                    context = await browser.new_context(viewport={'width': width, 'height': height},
                                                        has_touch=width < 1000, locale='pt-BR')
                    sdk = SDK.replace('__PLATFORM__', json.dumps('ios' if width < 1000 else 'tdesktop'))
                    await context.route('https://telegram.org/js/telegram-web-app.js', lambda route: route.fulfill(
                        status=200, content_type='application/javascript', body=sdk))
                    page = await context.new_page()
                    page.set_default_timeout(TIMEOUT)
                    js_errors, http_errors, request_failures, console_errors = [], [], [], []
                    page.on('pageerror', lambda error: js_errors.append(str(error)))
                    page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
                    page.on('response', lambda response: http_errors.append({'url': response.url, 'status': response.status}) if response.status >= 400 else None)
                    page.on('requestfailed', lambda request: request_failures.append({'url': request.url, 'error': request.failure}))
                    def observe(request):
                        path = urlparse(request.url).path
                        if request.method != 'GET' and path.startswith('/api/'):
                            profile_result['api_writes'].append({'method': request.method, 'path': path})
                        if path.startswith(('/play/', '/play-v2/', '/play-v3/')):
                            profile_result['game_requests'].append(path)
                    page.on('request', observe)
                    async with page.expect_response(lambda response: urlparse(response.url).path == '/api/catalog') as pending:
                        await page.goto(BASE_URL, wait_until='domcontentloaded')
                    response = await pending.value
                    assert response.status == 200
                    payload = await response.json()
                    games = {game['slug']: game for game in payload['games']}
                    assert set(games) == set(all_slugs) and all(games[slug]['controls_pt'] == local[slug]['controls_pt'] for slug in all_slugs), 'Real API catalog stale or incomplete'
                    profile_result['catalog_url'] = response.url
                    profile_result['catalog_sha256'] = hashlib.sha256((await response.body())).hexdigest()
                    await page.evaluate('document.fonts.ready')
                    await page.locator('[data-view-target="explore"]:visible').first.click()
                    await expect(page.locator('[data-view="explore"]')).to_be_visible()
                    samples = []
                    for slug in slugs:
                        game = games[slug]
                        case = {'slug': slug, 'viewport': f'{width}x{height}', 'status': 'failed', 'checks': []}
                        report['executed'] += 1
                        initial_errors = (len(js_errors), len(http_errors), len(request_failures), len(console_errors))
                        try:
                            case.update(await open_tutorial(page, game, True, width, height))
                            data = await assert_modal(page, width, height)
                            assert data['controls'] == game['controls_pt'], 'Controls differ from real catalog'
                            instructions = game.get('instructions_pt') or game.get('tutorial') or game.get('description_pt') or game.get('description')
                            expected = instructions if isinstance(instructions, list) else [instructions]
                            assert data['instructions'] == expected, 'Tutorial differs from real catalog'
                            case['checks'] += ['real_catalog_exact_controls', 'real_catalog_exact_tutorial', 'real_cover_loaded',
                                               'safe_modal', '14px_essential_text', 'no_horizontal_overflow', 'no_implicit_rotation', 'no_game_loaded']
                            case['geometry'] = data
                            start = page.locator('[data-help-action="start"]')
                            case['primary_target'] = await real_scroll_to(page, start, True)
                            await start.click(trial=True)
                            case['checks'].append('start_reachable_actionability_only_no_game_start')
                            if slug in SAMPLES:
                                samples.append((slug, await page.screenshot()))
                            cancel = page.locator('[data-help-action="cancel"]')
                            case['cancel_target'] = await real_scroll_to(page, cancel, True)
                            await cancel.click()
                            await expect(page.locator('#helpDialog')).to_be_hidden()
                            await expect(page.locator('#player')).to_be_hidden()
                            case['checks'].append('real_cancel_returns_catalog')
                            await open_tutorial(page, game, False, width, height)
                            close = page.locator('#closeHelp')
                            case['close_target'] = await real_scroll_to(page, close, True)
                            await close.click()
                            await expect(page.locator('#helpDialog')).to_be_hidden()
                            await expect(page.locator('#player')).to_be_hidden()
                            assert not profile_result['api_writes'] and not profile_result['game_requests'], 'Pre-game tutorial caused a write or game request'
                            assert initial_errors == (len(js_errors), len(http_errors), len(request_failures), len(console_errors)), 'Browser/HTTP error during this case'
                            case['checks'] += ['real_close_returns_catalog', 'no_api_writes', 'no_game_requests']
                            case['status'] = 'passed'
                            report['passed_cases'] += 1
                        except Exception as error:
                            case['error'] = str(error)
                            case['error_type'] = type(error).__name__
                            case.update(await failure_photo(page, f'FAIL-{slug}-{width}x{height}.png'))
                            report['failed'] += 1
                            try:
                                await page.goto(BASE_URL, wait_until='domcontentloaded')
                                await page.locator('[data-view-target="explore"]:visible').first.click()
                            except Exception as recovery:
                                case['recovery_error'] = str(recovery)
                                report['cases'].append(case)
                                raise
                        finally:
                            case['js_errors'] = js_errors[initial_errors[0]:]
                            case['http_errors'] = http_errors[initial_errors[1]:]
                            case['request_failures'] = request_failures[initial_errors[2]:]
                            case['console_errors'] = console_errors[initial_errors[3]:]
                        report['cases'].append(case)
                        (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                        print(json.dumps({'slug': slug, 'viewport': case['viewport'], 'status': case['status'], 'error': case.get('error', '')[:240]}, ensure_ascii=False), flush=True)
                    profile_result['contact'] = write_contact(width, height, samples)
                    profile_result.update(js_errors=js_errors, http_errors=http_errors, request_failures=request_failures, console_errors=console_errors)
                except Exception as error:
                    profile_result['errors'].append(f'{type(error).__name__}: {error}')
                    recorded = {case['slug'] for case in report['cases'] if case['viewport'] == f'{width}x{height}'}
                    for slug in slugs:
                        if slug not in recorded:
                            report['cases'].append({'slug': slug, 'viewport': f'{width}x{height}', 'status': 'blocked', 'error': 'Profile setup or recovery failed'})
                            report['blocked'] += 1
                finally:
                    if context is not None:
                        try:
                            await asyncio.wait_for(context.close(), 10)
                        except Exception as error:
                            profile_result['errors'].append(f'Context cleanup: {type(error).__name__}: {error}')
                    report['profiles'].append(profile_result)
        except Exception as error:
            report['infrastructure_errors'].append(f'{type(error).__name__}: {error}')
            recorded = {(case['slug'], case['viewport']) for case in report['cases']}
            for width, height in VIEWPORTS:
                for slug in slugs:
                    if (slug, f'{width}x{height}') not in recorded:
                        report['cases'].append({'slug': slug, 'viewport': f'{width}x{height}', 'status': 'blocked', 'error': 'Browser infrastructure failed before execution'})
                        report['blocked'] += 1
        finally:
            if browser is not None:
                try:
                    await asyncio.wait_for(browser.close(), 10)
                except Exception as error:
                    report['infrastructure_errors'].append(f'Browser cleanup: {type(error).__name__}: {error}')
    report['sources_after'] = snapshot()
    report['source_hashes_unchanged'] = all(before[rel]['sha256'] == report['sources_after'][rel]['sha256'] for rel in SOURCE_FILES)
    report['passed'] = (report['executed'] == report['passed_cases'] == expected_cases and not report['failed'] and not report['blocked']
                        and report['source_hashes_unchanged'] and not report['infrastructure_errors']
                        and all(not profile['errors'] and not profile['api_writes'] and not profile['game_requests']
                                and not profile.get('js_errors') and not profile.get('http_errors')
                                and not profile.get('request_failures') and not profile.get('console_errors') for profile in report['profiles']))
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['prepared', 'executed', 'passed_cases', 'failed', 'blocked', 'source_hashes_unchanged', 'passed']}))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
