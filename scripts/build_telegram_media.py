"""Build Telegram JPEG media exclusively from the repository's real game covers.

Run from any directory with the existing Pillow/Playwright development runtime:
    python scripts/build_telegram_media.py

No bot, HTTP server, external requests, account or deployment is involved.
"""
from __future__ import annotations

import argparse
import asyncio
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'web' / 'telegram'
BACKGROUND = (8, 11, 36)
PHOTO_LIMIT = 5 * 1024 * 1024


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def describe(path: Path) -> dict:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        result = {'path': relative(path), 'sha256': digest(path),
                  'width': image.width, 'height': image.height,
                  'bytes': path.stat().st_size, 'format': image.format,
                  'mode': image.mode}
    assert result['format'] == 'JPEG' and result['mode'] == 'RGB', result
    assert result['bytes'] <= PHOTO_LIMIT, result
    assert result['width'] + result['height'] <= 10000, result
    assert max(result['width'], result['height']) / min(result['width'], result['height']) <= 20, result
    return result


def flattened(source: Path) -> Image.Image:
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert('RGBA')
        background = Image.new('RGBA', image.size, (*BACKGROUND, 255))
        background.alpha_composite(image)
        return background.convert('RGB')


def build_game_media() -> list[dict]:
    metadata = json.loads((ROOT / 'data' / 'catalog-pt.json').read_text(encoding='utf-8'))
    slugs = sorted(metadata)
    covers = {path.stem for path in (ROOT / 'web' / 'covers').glob('*.webp')}
    assert len(slugs) == 142 and set(slugs) == covers, (len(slugs), set(slugs) ^ covers)
    for directory in ['games', 'thumbs']:
        (DESTINATION / directory).mkdir(parents=True, exist_ok=True)
    records = []
    for slug in slugs:
        source = ROOT / 'web' / 'covers' / f'{slug}.webp'
        image = flattened(source)
        photo_path = DESTINATION / 'games' / f'{slug}.jpg'
        image.save(photo_path, 'JPEG', quality=91, optimize=True, progressive=False, subsampling=0)
        thumb_image = ImageOps.contain(image, (240, 150), Image.Resampling.LANCZOS)
        thumbnail = Image.new('RGB', (240, 150), BACKGROUND)
        inset = ((240 - thumb_image.width) // 2, (150 - thumb_image.height) // 2)
        thumbnail.paste(thumb_image, inset)
        thumb_path = DESTINATION / 'thumbs' / f'{slug}.jpg'
        thumbnail.save(thumb_path, 'JPEG', quality=88, optimize=True, progressive=False, subsampling=0)
        photo, thumb = describe(photo_path), describe(thumb_path)
        assert (photo['width'], photo['height']) == image.size
        assert thumb['bytes'] < 200 * 1024
        records.append({'slug': slug, 'name_pt': metadata[slug]['name'],
                        'source': {'path': relative(source), 'sha256': digest(source),
                                   'width': image.width, 'height': image.height},
                        'photo': {**photo, 'url': f'/static/telegram/games/{slug}.jpg'},
                        'thumb': {**thumb, 'url': f'/static/telegram/thumbs/{slug}.jpg',
                                  'fit': 'contain', 'background': '#080b24',
                                  'image_box': [*inset, thumb_image.width, thumb_image.height]}})
    return records


async def build_banner() -> dict:
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={'width': 1280, 'height': 640},
                                          device_scale_factor=1, locale='pt-BR')
            failures = []
            external_requests = []
            page.on('pageerror', lambda error: failures.append(str(error)))
            page.on('request', lambda request: external_requests.append(request.url)
                    if request.url.startswith(('https://', 'http://')) else None)
            await page.goto((DESTINATION / 'source' / 'banner.html').as_uri(), wait_until='load')
            await page.evaluate('document.fonts.ready')
            await page.evaluate('Promise.all([...document.images].map(image => image.decode()))')
            assert await page.evaluate("document.fonts.check('16px Arcade') && document.fonts.check('16px Outfit')")
            images = await page.locator('img').evaluate_all('images=>images.map(image=>({src:image.getAttribute("src"),complete:image.complete,width:image.naturalWidth,height:image.naturalHeight}))')
            assert len(images) == 4 and all(row['complete'] and row['width'] > 0 for row in images), images
            assert not failures and not external_requests, (failures, external_requests)
            path = DESTINATION / 'baltigo-games.jpg'
            await page.screenshot(path=str(path), type='jpeg', quality=95)
            return {**describe(path), 'url': '/static/telegram/baltigo-games.jpg',
                    'renderer': browser.version, 'images': images,
                    'external_requests': external_requests, 'page_errors': failures}
        finally:
            await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-banner', action='store_true', help='Rebuild JPEG game derivatives only.')
    args = parser.parse_args()
    games = build_game_media()
    banner = describe(DESTINATION / 'baltigo-games.jpg') if args.skip_banner else asyncio.run(build_banner())
    sources = ['scripts/build_telegram_media.py', 'web/telegram/source/banner.html',
               'web/telegram/source/logo.svg', 'web/fonts/PressStart2P-Regular.ttf',
               'web/fonts/Outfit-Variable.ttf', 'data/catalog-pt.json']
    manifest = {'schema': 1, 'games_count': len(games), 'photos_count': len(games),
                'thumbs_count': len(games), 'banner': banner, 'games': games,
                'source_files': [{'path': path, 'sha256': digest(ROOT / path)} for path in sources],
                'tool_versions': {'pillow': importlib.metadata.version('Pillow'),
                                  'playwright': importlib.metadata.version('playwright')},
                'photo_policy': 'Capa real convertida para JPEG RGB nas mesmas dimensões, sem recorte ou deformação.',
                'thumb_policy': 'JPEG RGB 240×150; imagem proporcional inteira com letterbox azul-marinho.',
                'scope': 'Arquivos locais derivados das capas reais; nenhum envio Telegram, serviço externo ou publicação.'}
    (DESTINATION / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'games': len(games), 'jpeg_photos': len(games), 'jpeg_thumbs': len(games),
                      'max_photo_bytes': max(game['photo']['bytes'] for game in games),
                      'max_thumb_bytes': max(game['thumb']['bytes'] for game in games),
                      'banner_bytes': banner['bytes'], 'manifest': 'web/telegram/manifest.json'}))


if __name__ == '__main__':
    main()
