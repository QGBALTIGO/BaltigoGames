"""Require the reviewed response deltas for nineteen games, preserving others."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.main import adapt_game_content

EXPECTED={
 'games/3d/cosmic-cleaner/mechanics.js',
 'games/3d/planet-visitor/mechanics.js',
 'games/arcade/collector/Scenes/GameScene.js',
 'games/arcade/kaiju-krush/index.html',
 'games/arcade/pacman/Scenes/GameScene.js',
 'games/casual/cooking/config.json',
 'games/casual/cooking/Scenes/GameScene.js',
 'games/platformer/antigravity/mechanics.js',
 'games/puzzle/6oct/Scenes/GameScene.js',
 'games/racing/endless-runner/mechanics.js',
 'games/racing/shadow-runner/Scenes/GameScene.js',
 'games/shooter/shooter/Scenes/GameScene.js',
 'games/shooter/sniper/Scenes/GameScene.js',
 'games/shooter/tower-shooter/Scenes/GameScene.js',
 'games/shooter/trench-defence/mechanics.js',
 'games/shooter/vaccine-shooter/Scenes/GameScene.js',
 'games/sports/cricket-123/Scenes/GameScene.js',
 'games/sports/football/index.html',
 'games/sports/penalty/gamescene.js',
 'games/sports/penalty/index.html',
 'games/sports/table-tennis/Scenes/GameScene.js',
}

def run(args):
 before={item['path']:item for item in json.loads((ROOT/args.before).read_text(encoding='utf-8'))}
 after={item['path']:item for item in json.loads((ROOT/args.after).read_text(encoding='utf-8'))}
 changed={path for path in before.keys()|after.keys() if before.get(path,{}).get('effective_sha256')!=after.get(path,{}).get('effective_sha256')}
 css=[]
 for path in sorted((ROOT/'.deploy/mirror/games').rglob('*.css')):
  rel=path.relative_to(ROOT/'.deploy/mirror').as_posix();raw=path.read_bytes();effective=adapt_game_content(rel,raw,'text/css')
  css.append({'path':rel,'source_sha256':sha256(raw).hexdigest(),'effective_sha256':sha256(effective).hexdigest(),'unchanged':effective==raw})
 report={'baseline':'Public qualification 601ee7f351e9aae5471ae35716d5058d423bccae, response-manifest capture before the scoped HUD edits. CSS adapters remain unchanged and both mirrored stylesheets are byte-identical to their pinned source.','html_js_json_compared':len(before),'css_unchanged':css,'total_source_responses_checked':len(before)+len(css),'expected_changed':sorted(EXPECTED),'actual_changed':sorted(changed),'unexpected':sorted(changed-EXPECTED),'missing_expected':sorted(EXPECTED-changed),'unaffected_html_js_json':len(before)-len(changed),'runtime_js_sha256':sha256((ROOT/'web/game-runtime.js').read_bytes()).hexdigest()}
 report['pass']=set(before)==set(after) and changed==EXPECTED and all(item['unchanged'] for item in css)
 out=ROOT/args.out;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:report[k] for k in ['pass','html_js_json_compared','total_source_responses_checked','unaffected_html_js_json','unexpected','missing_expected']},ensure_ascii=False))
 assert report['pass'],report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--before',default='artifacts/visual-four-patch/before/effective-manifest.json');parser.add_argument('--after',default='artifacts/visual-v3-candidate/source-final/effective-manifest.json');parser.add_argument('--out',default='artifacts/visual-v3-candidate/response-delta.json');run(parser.parse_args())
