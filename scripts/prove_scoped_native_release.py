"""Focused native Football, five-round Penalty and Portuguese recipe proofs."""
from __future__ import annotations
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import sys
from playwright.async_api import async_playwright
from audit_round_transitions import start_game

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import e2e_native_football_hex as native
import e2e_authored_remaining_campaigns as campaign


async def run(args):
    out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    native.BASE=args.base;native.OUT=out
    # Existing strict native proof: natural timeout, real Next/Replay, real
    # held mobile movement. Hex is outside this focused change and is not run.
    await native.football_main()
    campaign.BASE=args.base;campaign.OUT=out
    results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=native.BROWSER_FLAGS)
        try:
            errors=[];bad=[];G=campaign.G;S=campaign.S
            page=await campaign.open_game(browser,'games/sports/penalty/index.html',f"{S}.controls?.action && {S}.turn==='PLAYER_AIM'",errors,bad,start=False)
            try:
                await page.evaluate(f"() => {{const s={S};s._randLane=()=>1;s._randLaneExcept=()=>1;s.cfg.gameplay.cpuSaveBias=0;}}")
                rounds=[]
                for number in range(1,6):
                    await campaign.wait(page,f"{S}.turn==='PLAYER_AIM'&&!{S}.busy")
                    await campaign.tap(page,'s.controls.action')
                    await campaign.wait(page,f"{S}.turn==='CPU_AIM'&&!{S}.busy")
                    if number==1:await page.screenshot(path=str(out/'penalty-real-defense.png'))
                    await campaign.tap(page,'s.controls.right');await campaign.tap(page,'s.controls.action')
                    if number<5:
                        await campaign.wait(page,f"{S}.round==={number+1}&&{S}.turn==='PLAYER_AIM'&&!{S}.busy")
                    else:await campaign.wait(page,f"{S}.sys.settings.key==='WinScene'")
                    state=await page.evaluate(f"()=>{{const s={G}.scene.getScene('GameScene');return{{round:s.round,player:s.playerScore,cpu:s.cpuScore}};}}")
                    assert state['player']==number and state['cpu']==0,state
                    rounds.append(state)
                await page.screenshot(path=str(out/'penalty-native-win.png'))
                await page.touchscreen.tap(195,350)
                await campaign.wait(page,f"{S}.sys.settings.key==='GameScene'&&{S}.round===1")
                await page.wait_for_function("window.__baltigo.status==='playing'",polling=100,timeout=10000)
                reset=await page.evaluate(f"({{round:{S}.round,player:{S}.playerScore,cpu:{S}.cpuScore,turn:{S}.turn,busy:{S}.busy,status:window.__baltigo.status}})")
                assert reset=={'round':1,'player':0,'cpu':0,'turn':'PLAYER_AIM','busy':False,'status':'playing'},reset
                assert not errors and not bad,(errors,bad)
                results.append({'slug':'penalty','pass':True,'fixture':'Deterministic CPU lanes and no save bias, followed by all ten actual source action gestures and animations; no phase was skipped.','rounds':rounds,'replay':reset,'errors':errors,'bad_responses':bad})
            finally:await page.close()
            context=await browser.new_context(viewport={'width':844,'height':390},has_touch=True,is_mobile=True,locale='pt-BR')
            try:
                page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
                await page.goto(args.base+'/play-v3/games/casual/cooking/index.html',wait_until='domcontentloaded')
                await page.wait_for_function("window.__baltigo.status==='ready'",polling=100,timeout=30000)
                await start_game(page,page.main_frame)
                recipes=[]
                for index,name in enumerate(['Bolo','Hambúrguer','Pizza']):
                    await page.evaluate('''index=>{const s=window.__baltigo.games[0].scene.getScenes(true).find(s=>s.currentRecipe);s.cfg.gameplay.randomRecipe=false;s.cfg.gameplay.startLevel=index;s.scene.restart();}''',index)
                    await page.wait_for_function('''name=>window.__baltigo.games[0].scene.getScenes(true).some(s=>s.currentRecipe?.name===name&&s.recipeTitleText?.text.includes(name))''',arg=name,polling=100,timeout=15000)
                    record=await page.evaluate('''()=>{const s=window.__baltigo.games[0].scene.getScenes(true).find(s=>s.currentRecipe);return{name:s.currentRecipe.name,caption:s.recipeTitleText.text,sequence:s.currentRecipe.sequence,decoys:s.currentRecipe.decoys,ingredients:s.ingredientsGroup.getLength()};}''')
                    assert record['ingredients']>0,record
                    await page.screenshot(path=str(out/f'cooking-recipe-{index}.png'))
                    recipes.append(record)
                assert not errors,errors
                results.append({'slug':'cooking','pass':True,'fixture':'After actual Play, the existing scene config selects each recipe deterministically and the native create/restart rebuilds its own title and ingredients. No UI text is supplied by the test.','recipes':recipes,'errors':errors})
            finally:await context.close()
        finally:await browser.close()
    report={'base':args.base,'football':json.loads((out/'football-native-rounds.json').read_text(encoding='utf-8')),'results':results,'runtime_sha256':sha256((ROOT/'web/game-runtime.js').read_bytes()).hexdigest()}
    report['pass']=report['football']['passed'] and len(results)==2 and all(result['pass'] for result in results)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pass':report['pass'],'games':['football','penalty','cooking']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:8195');parser.add_argument('--out',default='artifacts/native-v3-candidate');asyncio.run(run(parser.parse_args()))
