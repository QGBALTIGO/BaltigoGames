"""Capture actual opening requests for reproducible capacity profiles."""
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ['snake', 'demon', 'car-race', 'chess', 'buttermilk', 'fruit-cosmics', 'wordle', 'cool-platformer', 'alien-battle', 'basketball', 'level-devil', 'cannon-blaster', 'ludo', 'fruit-merge']


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8190')
    parser.add_argument('--output', default='artifacts/capacity/asset-manifest.json')
    args = parser.parse_args()
    catalog = json.loads((ROOT/'data/registry.json').read_text(encoding='utf8'))['games']
    shell = (ROOT/'web/index.html').read_text(encoding='utf8')
    shell_paths = set(re.findall(r'(?:src|href)="(/static/[^"#]+)"', shell))
    shell_paths.add(re.search(r"api\('(/api/catalog[^']*)'", (ROOT/'web/app.js').read_text(encoding='utf8')).group(1))
    profiles = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=['--use-angle=swiftshader-webgl'])
        for slug in SAMPLES:
            game = next(g for g in catalog if g['slug'] == slug)
            context = await browser.new_context(viewport={'width': 844, 'height': 390})
            page = await context.new_page()
            paths = shell_paths | {'/', '/static/fonts/Outfit-Variable.ttf', '/static/fonts/PressStart2P-Regular.ttf', '/static/covers/'+slug+'.webp'}
            failures = []
            def response_seen(response):
                parsed = urlparse(response.url)
                if parsed.netloc == urlparse(args.base).netloc:
                    path = parsed.path + ('?'+parsed.query if parsed.query else '')
                    if response.status in {200, 206}:
                        paths.add(path)
                    else:
                        failures.append({'path': path, 'status': response.status})
            page.on('response', response_seen)
            await page.goto(args.base+'/play-v2/'+game['path'], wait_until='domcontentloaded', timeout=45000)
            try:
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception:
                pass
            await page.wait_for_timeout(800)
            profiles.append({'slug': slug, 'paths': sorted(paths), 'failed_responses': failures, 'scope': 'Real opening network responses plus public portal shell/font/cover requests; graphics and interactivity are qualified separately'})
            print(json.dumps({'slug': slug, 'requests': len(paths), 'failures': failures}), flush=True)
            await context.close()
        await browser.close()
    target = ROOT/args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profiles, indent=2), encoding='utf8')
    if any(p['failed_responses'] for p in profiles):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
