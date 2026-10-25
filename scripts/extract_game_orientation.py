"""Extract authored game orientation and actual logical canvas dimensions."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract(html: str, config: dict | None = None) -> dict:
    config = config or {}
    messages = re.findall(r'''["']?type["']?\s*:\s*["']orientation["']\s*,\s*["']?value["']?\s*:\s*["'](portrait|landscape)["']''', html)
    dimensions = re.findall(r'\bwidth\s*:\s*(\d{3,4})\s*,\s*height\s*:\s*(\d{3,4})', html)
    variables = {key: int(value) for key, value in re.findall(r'(?:const|let|var)\s+((?:GAME_)?(?:WIDTH|HEIGHT))\s*=\s*(\d{3,4})', html)}
    size = tuple(map(int, dimensions[-1])) if dimensions else None
    if not size:
        for prefix in ('GAME_', ''):
            if prefix+'WIDTH' in variables and prefix+'HEIGHT' in variables:
                size = (variables[prefix+'WIDTH'], variables[prefix+'HEIGHT'])
                break
    authored = messages[-1] if messages else None
    orientation = authored
    source = 'authored-message' if authored else None
    if size:
        logical_orientation = 'landscape' if size[0] > size[1] else 'portrait'
        if not orientation or orientation != logical_orientation:
            orientation = logical_orientation
            source = 'logical-size-overrides-message' if authored else 'logical-size'
    if not orientation:
        orientation = config.get('gameplay', {}).get('orientation') or config.get('mechanics', {}).get('orientation')
        source = 'config'
    if orientation not in {'portrait', 'landscape'}:
        orientation = 'portrait'
        source = 'responsive-default'
    return {'orientation': orientation, 'authored_orientation': authored,
            'logical_width': size[0] if size else None,
            'logical_height': size[1] if size else None,
            'orientation_source': source}


def main():
    source = ROOT / '.deploy/mirror'
    registry = json.loads((ROOT / 'data/registry.json').read_text(encoding='utf-8'))
    result = {}
    for game in registry['games']:
        path = source / game['path']
        config = {}
        try:
            config = json.loads(path.with_name('config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        result[game['slug']] = extract(path.read_text(encoding='utf-8'), config)
    (ROOT / 'data/game-orientations.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'games':len(result), 'landscape':sum(x['orientation']=='landscape' for x in result.values())}))


if __name__ == '__main__':
    main()
