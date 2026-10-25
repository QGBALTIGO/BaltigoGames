"""Bundle the exact engine versions used by the catalog and retain their licenses."""
import asyncio
import json
import re
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


async def main():
    catalog = json.loads((ROOT / 'data/registry.json').read_text(encoding='utf-8'))
    mirror = ROOT / '.deploy/mirror'
    urls = set()
    for game in catalog['games']:
        html = (mirror / game['path']).read_text(encoding='utf-8')
        urls.update(re.findall(r'<script[^>]+src=[\"\'](https?://[^\"\']+)[\"\']', html, re.I))
    output = ROOT / 'web/vendor'
    output.mkdir(exist_ok=True)
    mapping = {}
    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        for url in sorted(urls):
            if not any(host in url for host in ['cdn.jsdelivr.net', 'cdnjs.cloudflare.com', 'unpkg.com']):
                raise RuntimeError('unreviewed external script: ' + url)
            filename = re.sub(r'[^a-zA-Z0-9._-]', '-', url.split('://')[1])
            response = await client.get(url)
            response.raise_for_status()
            assert len(response.content) > 1000
            (output / filename).write_bytes(response.content)
            mapping[url] = '/static/vendor/' + filename
        licenses = {}
        for name, url in {
            'Phaser': 'https://raw.githubusercontent.com/phaserjs/phaser/v3.60.0/license.txt',
            'Three.js': 'https://raw.githubusercontent.com/mrdoob/three.js/r159/LICENSE',
            'GSAP 1.19.1': 'https://cdn.jsdelivr.net/npm/gsap@1.19.1/README.md',
        }.items():
            response = await client.get(url)
            if response.status_code == 200:
                licenses[name] = {'source': url, 'license': response.text}
    (output / 'LICENSES.json').write_text(json.dumps(licenses, indent=2), encoding='utf-8')
    (ROOT / 'data/vendor-map.json').write_text(json.dumps(mapping, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'engines': len(mapping), 'bytes': sum(path.stat().st_size for path in output.iterdir())}))


if __name__ == '__main__':
    asyncio.run(main())
