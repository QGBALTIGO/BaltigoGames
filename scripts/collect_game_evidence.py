"""Index opening and native terminal evidence for every catalog entry."""
from pathlib import Path
import argparse
import csv
import json

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entry', default='artifacts/qualification/entry-index.json')
    parser.add_argument('--terminal', action='append', default=[])
    parser.add_argument('--native', default='artifacts/native-rounds-frozen/report.json')
    parser.add_argument('--native-override', action='append', default=[])
    parser.add_argument('--campaign-primary', default='artifacts/campaigns-primary-release/authored-phases-browser.json')
    parser.add_argument('--campaign-remaining', default='artifacts/campaigns-remaining-release/authored-phases-rest-browser.json')
    parser.add_argument('--external', default='artifacts/native-football-hex-release')
    parser.add_argument('--out', default='artifacts/qualification/games')
    args = parser.parse_args()
    catalog = read(ROOT/'data/registry.json')['games']
    metadata = read(ROOT/'data/catalog-pt.json')
    opening = {(row['slug'], row['profile']):row for row in read(ROOT/args.entry)['cases']}
    terminal = {}
    for folder in ['artifacts/terminal-release-final', *args.terminal]:
        for path in sorted((ROOT/folder).glob('*.json')):
            data = read(path)
            if isinstance(data, dict) and 'slug' in data and 'pass' in data:
                terminal[data['slug']] = (data, path, 'Fonte Phaser: confirmação e reinício')
    for filename, method in [(args.native, 'Fluxo nativo'), *[(f, 'Fluxo nativo') for f in args.native_override], (args.campaign_primary, 'Campanha: progressão nativa'), (args.campaign_remaining, 'Campanha: progressão nativa')]:
        path = ROOT/filename
        for data in read(path):
            terminal[data['slug']] = (data, path, method)
    for filename in ['football-native-rounds.json', 'hex-native-rounds.json']:
        path = ROOT/args.external/filename
        data = read(path)
        terminal[data['slug']] = (data, path, 'Canvas próprio: confirmação e reinício')
    rows = []
    for game in catalog:
        slug = game['slug']
        source = terminal.get(slug)
        data, path, method = source if source else ({}, None, 'Pendente')
        terminal_passed = bool(data.get('pass', data.get('passed', False)))
        # This legacy scene is not reachable from Screw Master's actual game.
        # Only its real timeout/error-and-replay fixture can qualify this entry.
        if slug == 'screw-master' and data.get('fixture', {}).get('method') == 'WinScene':
            terminal_passed = False
            method = 'Requer terminal real; cena legada inacessível excluída'
        preferred = bool(opening.get((slug, 'preferred'), {}).get('passed'))
        desktop = bool(opening.get((slug, 'desktop'), {}).get('passed'))
        rows.append({'slug':slug, 'nome':metadata[slug]['name'],
                     'orientacao':metadata[slug]['orientation'],
                     'celular_aprovado':preferred, 'desktop_aprovado':desktop,
                     'terminal_aprovado':terminal_passed, 'metodo':method,
                     'next':'Não se aplica' if data.get('next_applicable') is False or slug in {'screw-master','dream-weaver','window-shooter'} else data.get('next_pass', 'Consultar fluxo nativo'),
                     'replay':data.get('replay_pass', 'Consultar fluxo nativo'),
                     'evidencia_terminal':path.relative_to(ROOT).as_posix() if path else None,
                     'aprovado':preferred and desktop and terminal_passed})
    output = ROOT/args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'scope':'Every catalog game: retained real-browser opening checks, source-native terminal fixtures and real confirmation gestures. Campaigns use reviewed near-completion states. This does not claim every level was played fully by a human or tested on physical Telegram devices.',
              'games':len(catalog), 'passed':sum(r['aprovado'] for r in rows),
              'failed':[r['slug'] for r in rows if not r['aprovado']], 'cases':rows}
    output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with output.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k:v for k,v in report.items() if k not in {'cases', 'scope'}}, ensure_ascii=True))
    return 0 if not report['failed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
