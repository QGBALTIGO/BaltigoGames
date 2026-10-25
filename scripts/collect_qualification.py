"""Consolidate retained game evidence without hiding superseded failures.

This indexes browser evidence; it neither executes games nor turns a short
opening check into a claim that a human completed every level.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
ENGLISH = re.compile(r'\b(how to play|game over|play again|you win|you lose|score|coins|target|swipe|collect|victory|defeat|level|lives|loading|flip board|clear cell|tap to|hold to|press|reach|avoid|jump|start game|stand still)\b', re.I)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', default='artifacts/entry-release-final')
    parser.add_argument('--override', action='append', default=[])
    parser.add_argument('--out', default='artifacts/qualification/entry-index.json')
    args = parser.parse_args()
    games = json.loads((ROOT/'data/registry.json').read_text(encoding='utf-8'))['games']
    rows = []
    missing = []
    for game in games:
        for profile in ['preferred', 'desktop']:
            filename = f"{game['slug']}-{profile}.json"
            choices = [ROOT/folder/filename for folder in [args.baseline, *args.override]]
            existing = [path for path in choices if path.exists()]
            if not existing:
                missing.append(filename)
                continue
            path = existing[-1]
            result = json.loads(path.read_text(encoding='utf-8'))
            active = result.get('after', {})
            text = active.get('sceneVisibleText', []) + [active.get('body', '')] if active.get('engine') == 'phaser' else active.get('text', [])
            tutorial = any(re.search(r'como jogar', t, re.I) for t in text) and bool(active.get('targets'))
            intro = any(re.search(r'toque em qualquer lugar para|toque para começar|tap anywhere to start', t, re.I) for t in text)
            source_waiting = any(str(scene.get('state', '')).lower() in {'start', 'intro', 'menu', 'instructions'} for scene in active.get('sceneStates', []))
            english = sorted(set(t for t in text if ENGLISH.search(t)))
            passed = bool(result.get('passed')) and not tutorial and not intro and not source_waiting and not english
            rows.append({'slug':game['slug'], 'profile':profile, 'passed':passed,
                         'source':path.relative_to(ROOT).as_posix(),
                         'superseded_evidence':[p.relative_to(ROOT).as_posix() for p in existing[:-1]],
                         'tutorial_remaining':tutorial, 'intro_remaining':intro,
                         'source_waiting':source_waiting, 'active_english':english,
                         'document_ms':result.get('document_ms'),
                         'started_ms':result.get('started_ms'),
                         'errors':result.get('errors', []), 'error':result.get('error')})
    report = {'scope':'142 games, preferred mobile orientation and desktop; real opening/input/frame checks, not a complete human playthrough or physical Telegram test',
              'prepared':len(games)*2, 'executed':len(rows), 'passed':sum(r['passed'] for r in rows),
              'failed':[r for r in rows if not r['passed']], 'missing':missing,
              'all_passed':len(rows)==len(games)*2 and all(r['passed'] for r in rows),
              'method':'Latest retained targeted report overrides only the same game/profile; original failures remain on disk. Historical runtime text is excluded from active-screen assertions.',
              'product_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [*ROOT.joinpath('app').glob('*.py'), *ROOT.joinpath('web').glob('*.js'), *ROOT.joinpath('data').glob('*.json')]},
              'cases':rows}
    out = ROOT/args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'cases', 'product_sha256'}}, ensure_ascii=True))
    return 0 if report['all_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
