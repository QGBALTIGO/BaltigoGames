"""Read-only parsing of the effective game responses and Portuguese adapter.

Uses the same transformation entry point as /play-v2; JavaScript is parsed,
never executed, except for the isolated pure translation function in Node VM.
No game or browser is opened and no product file is modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import mimetypes
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.game_runtime import VERSION, metadata, transition_policies, word_games
from app.main import CONFIG_OVERRIDES, adapt_game_content


class InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'script':
            return
        attrs = dict(attrs)
        kind = (attrs.get('type') or '').lower()
        if not attrs.get('src') and kind in {'', 'text/javascript', 'application/javascript', 'module'}:
            self.current = {'type': 'module' if kind == 'module' else 'classic', 'source': '', 'line': self.getpos()[0]}

    def handle_data(self, data):
        if self.current is not None:
            self.current['source'] += data

    def handle_endtag(self, tag):
        if tag.lower() == 'script' and self.current is not None:
            self.scripts.append(self.current)
            self.current = None


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def freeze_hashes():
    files = sorted({
        *ROOT.joinpath('app').glob('*.py'),
        *ROOT.joinpath('data').glob('*.json'),
        *ROOT.joinpath('web').glob('*.html'),
        *ROOT.joinpath('web').glob('*.js'),
        *ROOT.joinpath('web').glob('*.css'),
        *ROOT.joinpath('web').rglob('*.svg'),
        *ROOT.joinpath('web/vendor').glob('*.js'),
    })
    return {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in files if 'covers' not in p.parts}


NODE_CHECK = r"""
const fs=require('fs');const vm=require('vm');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const errors=[];let classic=0,moduleCount=0;
for(const item of input.scripts){
  try{
    if(item.type==='module'){new vm.SourceTextModule(item.source,{identifier:item.id});moduleCount++;}
    else if(item.type==='external'){
      try{new vm.Script(item.source,{filename:item.id});classic++;}
      catch(first){
        // External modules can have .js filenames; compile module syntax only
        // when a classic parse fails, without linking or evaluating imports.
        new vm.SourceTextModule(item.source,{identifier:item.id});moduleCount++;
      }
    }else{new vm.Script(item.source,{filename:item.id});classic++;}
  }catch(error){errors.push({id:item.id,kind:item.type,error:String(error),stack:error.stack});}
}
const sandbox={window:{}};vm.createContext(sandbox);
vm.runInContext(input.localization,sandbox,{filename:'game-localization.js'});
const prefix=input.runtime.slice(0,input.runtime.indexOf('  const canvasLabels='))+'})();';
vm.runInContext(prefix,sandbox,{filename:'game-runtime.translation-only.js'});
const dictionary=sandbox.window.__BALTIGO_PT,translate=sandbox.window.__baltigo.translate;
const translationFailures=[],idempotenceFailures=[],valueIdempotenceFailures=[];
let changes=0;
for(const [english,portuguese]of Object.entries(dictionary)){
  const once=translate(english),twice=translate(once),valueOnce=translate(portuguese),valueTwice=translate(valueOnce);
  if(once!==english)changes++;
  if(once!==twice)idempotenceFailures.push({english,once,twice});
  if(valueOnce!==valueTwice)valueIdempotenceFailures.push({portuguese,once:valueOnce,twice:valueTwice});
  // Whitespace and symbol substitutions are intentional runtime presentation.
  // Compare against the same cleanup applied to the reviewed Portuguese value.
  if(translate(once)!==valueOnce)translationFailures.push({english,expected:valueOnce,actual:translate(once)});
}
const probes=['Distância: 10','Distânciaância: 10','PONTOS200','Pontos: 200','VIDAS3','Tempo: 00:50','Limpar casa','Você perdeu. O computador 1 venceu a partida.'];
const probeResults=probes.map(source=>{let value=source;for(let i=0;i<20;i++)value=translate(value);return{source,after20:value,stable:translate(value)===value};});
const substantiveIdempotenceFailures=idempotenceFailures.filter(item=>item.once.replace(/◀/g,'←').replace(/▶/g,'→')!==item.twice);
fs.writeFileSync(process.argv[3],JSON.stringify({syntax:{checked:input.scripts.length,classic,module:moduleCount,errors},translation:{entries:Object.keys(dictionary).length,changedEnglishEntries:changes,translationFailures,idempotenceFailures,valueIdempotenceFailures,substantiveIdempotenceFailures,strictFirstPassIdempotent:idempotenceFailures.length===0,reviewedPortugueseValuesIdempotent:valueIdempotenceFailures.length===0,knownSymbolNormalization:'Reviewed strings containing U+25C0/U+25B6 are canonicalized to U+2190/U+2192 on the following translation pass; no language or suffix changes.',probes:probeResults}},null,2));
"""


def run(args):
    started = time.monotonic()
    before_hashes = freeze_hashes()
    out = ROOT / args.out
    work = ROOT / '.deploy/runtime-freeze-check'
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    scripts = []
    effective = []
    json_errors = []
    html_count = external_count = inline_count = config_count = 0
    effective_wordle_allowed = None
    mirror = ROOT / '.deploy/mirror'
    for path in sorted((mirror / 'games').rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.html', '.js', '.json'}:
            continue
        rel = path.relative_to(mirror).as_posix()
        source = path.read_bytes()
        payload = json.dumps(CONFIG_OVERRIDES[rel], ensure_ascii=False).encode('utf-8') if rel in CONFIG_OVERRIDES else source
        content = adapt_game_content(rel, payload, mimetypes.guess_type(path.name)[0] or '')
        effective.append({'path':rel,'source_sha256':digest(source),'effective_sha256':digest(content),'bytes':len(content),'config_override':rel in CONFIG_OVERRIDES})
        if path.suffix.lower() == '.json':
            config_count += 1
            try:
                parsed=json.loads(content)
                if rel.endswith('/wordle/config.json'):
                    effective_wordle_allowed=len(parsed['words']['validGuesses'])
            except Exception as error:
                json_errors.append({'path':rel,'error':str(error)})
        elif path.suffix.lower() == '.js':
            external_count += 1
            scripts.append({'id':rel,'type':'external','source':content.decode('utf-8-sig')})
        else:
            html_count += 1
            parser = InlineScripts()
            parser.feed(content.decode('utf-8-sig'))
            for index, script in enumerate(parser.scripts):
                if script['source'].strip():
                    inline_count += 1
                    scripts.append({'id':f'{rel}#inline-{index+1}-line-{script["line"]}','type':script['type'],'source':script['source']})
    for path in [ROOT/'web/game-runtime.js', ROOT/'web/game-localization.js', *sorted(ROOT.joinpath('web/vendor').glob('*.js'))]:
        scripts.append({'id':path.relative_to(ROOT).as_posix(),'type':'external','source':path.read_text(encoding='utf-8-sig')})
    input_path = work / 'input.json'
    node_path = work / 'parse.cjs'
    result_path = work / 'node-result.json'
    input_path.write_text(json.dumps({'scripts':scripts,'runtime':(ROOT/'web/game-runtime.js').read_text(encoding='utf-8'),'localization':(ROOT/'web/game-localization.js').read_text(encoding='utf-8')},ensure_ascii=False),encoding='utf-8')
    node_path.write_text(NODE_CHECK,encoding='utf-8')
    process = subprocess.run([args.node,'--experimental-vm-modules',str(node_path),str(input_path),str(result_path)],capture_output=True,text=True,timeout=120)
    if process.returncode:
        raise RuntimeError(process.stderr[:4000])
    checked = json.loads(result_path.read_text(encoding='utf-8'))
    after_hashes = freeze_hashes()
    changed_files = [path for path in before_hashes.keys()|after_hashes.keys() if before_hashes.get(path)!=after_hashes.get(path)]
    catalog = json.loads((ROOT/'data/registry.json').read_text(encoding='utf-8'))['games']
    slugs = {game['slug'] for game in catalog}
    coverage = {'games':len(slugs),'portuguese_metadata':len(slugs&metadata().keys()),'transition_policies':len(slugs&transition_policies().keys()),'missing_metadata':sorted(slugs-metadata().keys()),'missing_transitions':sorted(slugs-transition_policies().keys()),'portuguese_wordle_answers':len(word_games()['wordle']['answerPool']),'portuguese_wordle_allowed':effective_wordle_allowed,'wordle_raw_bank_entries':len(word_games()['wordle']['validGuesses'])}
    report = {'version':VERSION,'utc':datetime.now(timezone.utc).isoformat(),'duration_seconds':round(time.monotonic()-started,3),'method':'Effective app.main.adapt_game_content for every mirrored HTML/JS/JSON, config overrides included; Node VM parse without execution; pure runtime translator only executed in an isolated VM. No browser or gameplay test.','source_counts':{'html':html_count,'external_js':external_count,'inline_js':inline_count,'json':config_count,'extra_runtime_vendor_scripts':11},**checked,'json_errors':json_errors,'coverage':coverage,'hashes_unchanged_during_check':not changed_files,'changed_files':changed_files,'product_sha256':after_hashes,'harness_sha256':digest(Path(__file__).read_bytes())}
    report['pass']=not checked['syntax']['errors'] and not json_errors and not checked['translation']['translationFailures'] and not checked['translation']['valueIdempotenceFailures'] and not checked['translation']['substantiveIdempotenceFailures'] and not changed_files and not coverage['missing_metadata'] and not coverage['missing_transitions']
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'effective-manifest.json').write_text(json.dumps(effective,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'version':VERSION,'pass':report['pass'],'counts':report['source_counts'],'syntax_checked':checked['syntax']['checked'],'syntax_errors':len(checked['syntax']['errors']),'json_errors':len(json_errors),'translation_entries':checked['translation']['entries'],'translation_failures':len(checked['translation']['translationFailures']),'idempotence_failures':len(checked['translation']['idempotenceFailures']),'value_idempotence_failures':len(checked['translation']['valueIdempotenceFailures']),'hashes_stable':not changed_files,'report':str(out/'report.json')},ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out',default='artifacts/runtime-freeze-v7')
    parser.add_argument('--node',default='C:/Program Files/nodejs/node.exe')
    run(parser.parse_args())
