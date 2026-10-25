"""Measure the nine reviewed HUD repairs against real local game engines.

The three viewport profiles are opened directly, including a narrow portrait
viewport for landscape games. Result/replay mechanics have a separate harness.
Penalty's defense turn and Cooking's recipe selection are explicit source-state
fixtures for presentation coverage, rather than complete gameplay claims.
"""
from __future__ import annotations
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
from playwright.async_api import async_playwright
from audit_round_transitions import INSPECT, start_game

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ['--enable-webgl', '--use-angle=swiftshader-webgl', '--enable-unsafe-swiftshader', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows']
SLUGS = ['antigravity', 'endless-runner', 'football', 'cooking', 'table-tennis', 'sniper', 'trench-defence', 'planet-visitor', 'penalty', '6oct', 'collector', 'cosmic-cleaner', 'cricket-123', 'kaiju-krush', 'pacman', 'shadow-runner', 'shooter', 'tower-shooter', 'vaccine-shooter']
MEASURE = r'''() => {
 const game=window.__baltigo?.games?.[0];if(!game)return null;
 const s=game.scene.getScenes(true).find(s=>!/menu|boot|preload/i.test(s.sys.settings.key));if(!s)return null;
 const canvas=game.canvas.getBoundingClientRect(),ratio=canvas.width/game.scale.width;
 const box=o=>{const b=o.getBounds();return {text:o.text,x:b.x,y:b.y,width:b.width,height:b.height,fontCSS:parseFloat(o.style?.fontSize||0)*ratio,visible:o.visible};};
 let groups=[];
 const group=(plate,labels)=>({plate:box(plate),labels:labels.map(box)});
 switch(window.__baltigo.slug){
 case 'antigravity':groups=[group(s.scorebar,[s.coreText])];break;
 case 'endless-runner':groups=[group(s.pointBox,[s.coinText]),group(s.timeBox,[s.timerText])];break;
 case 'table-tennis':groups=[group(s.__baltigoScorePlate,[s.ui.scoreText])];break;
 case 'sniper':groups=[group(s.__baltigoTimerPlate,[s.__baltigoTimerLabel,s.ui.timer])];break;
 case 'trench-defence':groups=[group(s.scorebar,[s.scoreText,s.timerText])];break;
 case 'cosmic-cleaner':groups=[group(s.__baltigoHudPlate,[s.batteryBar,s.scoreText,s.shieldBar])];break;
 case 'planet-visitor':{
   const plates=s.children.list.filter(o=>o.type==='Rectangle'&&o.depth===99&&o.fillColor===0x081824);
   groups=[s.healthText,s.pictureCounterText,s.timerText].map((label,i)=>group(plates[i],[label]));break;
 }
 case 'penalty':groups=[s.ui.scoreText,s.ui.roundText,s.ui.timerText,s.ui.statusText].map(label=>({plate:{x:0,y:0,width:s.W,height:s.H},labels:[box(label)]}));break;
 default:groups=(s.__baltigoHudGroups||[]).map(g=>group(g.plate,g.labels));break;
 }
 return {world:[game.scale.width,game.scale.height],canvas:{x:canvas.x,y:canvas.y,width:canvas.width,height:canvas.height},ratio,groups,frame:game.loop.frame,activeScene:s.sys.settings.key,recipe:s.currentRecipe?.name,visibleText:window.__baltigo.visibleText(),status:window.__baltigo.status};
}'''


def assert_bounds(data):
    assert data, 'No active gameplay scene'
    for group in data['groups']:
        plate=group['plate']
        assert plate['x'] >= -1 and plate['x']+plate['width'] <= data['world'][0]+1, ('plate outside canvas', group)
        for label in group['labels']:
            assert label['visible'], ('HUD label remains hidden',label)
            assert label['fontCSS'] >= 13.9, ('primary label smaller than 14 CSS pixels',label)
            assert label['x'] >= plate['x']-1 and label['x']+label['width'] <= plate['x']+plate['width']+1, ('caption escapes plate',group)
            assert label['y'] >= plate['y']-1 and label['y']+label['height'] <= plate['y']+plate['height']+1, ('caption escapes plate vertically',group)
        for left,right in zip(group['labels'],group['labels'][1:]):
            assert left['x']+left['width']+5/data['ratio'] <= right['x']+1e-6, ('captions overlap',group)


async def run(args):
    out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    catalog={g['slug']:g for g in json.loads((ROOT/'data/registry.json').read_text(encoding='utf-8'))['games']}
    files=['app/game_runtime.py','web/game-runtime.js','data/config-overrides.json']
    hashes=lambda:{path:sha256((ROOT/path).read_bytes()).hexdigest() for path in files}
    before=hashes();results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=FLAGS)
        try:
            for slug in args.slugs or SLUGS:
                for profile,width,height in [('portrait',380,780),('landscape',844,390),('desktop',1280,800)]:
                    context=await browser.new_context(viewport={'width':width,'height':height},has_touch=True,is_mobile=True,locale='pt-BR')
                    page=await context.new_page();errors=[];bad=[]
                    page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
                    page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
                    result={'slug':slug,'profile':profile,'viewport':[width,height],'pass':False}
                    try:
                        await page.goto(args.base+'/play-v3/'+catalog[slug]['path'],wait_until='domcontentloaded')
                        await page.wait_for_function("window.__baltigo?.status==='ready'",polling=100,timeout=30000)
                        if slug=='football':
                            await page.wait_for_function("typeof gameStarted!=='undefined'",polling=100,timeout=20000)
                            await page.screenshot(path=str(out/f'{slug}-{profile}-tutorial.png'),timeout=10000)
                            await page.locator('#startOverlay button').tap()
                            await page.wait_for_function('gameStarted&&!gameOver')
                            await page.wait_for_timeout(200)
                            data=await page.evaluate('''()=>{const c=canvas.getBoundingClientRect(),r=c.height/GAME_HEIGHT,b=overlayEl.getBoundingClientRect();return{canvas:{x:c.x,y:c.y,width:c.width,height:c.height},help:{x:b.x,y:b.y,width:b.width,height:b.height},scoreAndTimerBottom:c.y+(__footballHud.timerY+__footballHud.time)*r,scoreFont:__footballHud.score*r,timerFont:__footballHud.time*r,helpFont:parseFloat(getComputedStyle(overlayEl).fontSize),scoreLeft,scoreRight,gameStarted,gameOver,text:overlayEl.innerText};}''')
                            assert data['help']['y'] >= data['scoreAndTimerBottom']+3,data
                            assert data['help']['x']>=0 and data['help']['x']+data['help']['width']<=width,data
                            assert data['helpFont']>=14 and data['gameStarted'] and not data['gameOver'],data
                            assert data['scoreFont']>=15.9 and data['timerFont']>=13.9,data
                        else:
                            await page.wait_for_function("window.__baltigo.games[0]?.scene.getScenes(true).some(s=>s.children.list.length&&!s.load?.isLoading()&&!/boot|preload/i.test(s.sys.settings.key))",polling=100,timeout=25000)
                            await page.wait_for_timeout(150)
                            await page.screenshot(path=str(out/f'{slug}-{profile}-tutorial.png'),timeout=10000)
                            await start_game(page,page.main_frame)
                            if slug=='penalty':
                                await page.evaluate("window.__baltigo.games[0].scene.getScenes(true).find(s=>s._setTurn)._setTurn('CPU_AIM')")
                                result['fixture']='Native defense-turn selection to measure its full instruction; no campaign win claimed.'
                                assert not await page.locator('.hint').is_visible(),'Duplicate HTML footer crosses the touch controls'
                            await page.wait_for_timeout(250)
                            data=await page.evaluate(MEASURE)
                            assert_bounds(data)
                            assert data['groups'],'No reviewed HUD group was actually bound'
                            if slug=='cooking':
                                names=await page.evaluate("window.__baltigo.games[0].scene.getScenes(true).find(s=>s.currentRecipe).cfg.gameplay.recipes.map(r=>r.name)")
                                assert names==['Bolo','Hambúrguer','Pizza'],names
                                result['recipe_names']=names
                                assert not any('Burger' in text or 'Cake' in text for text in data['visibleText']),data
                        result['measurement']=data
                        await page.screenshot(path=str(out/f'{slug}-{profile}-playing.png'),timeout=10000)
                        if slug=='planet-visitor' and profile=='landscape':
                            await page.locator('canvas').screenshot(path=str(out/'planet-visitor-active-canvas.png'),timeout=10000)
                        result['pass']=not errors and not bad
                    except Exception as error:
                        result['failure']=str(error)
                        try:result['failure_state']=await page.evaluate(INSPECT)
                        except Exception:pass
                        try:await page.screenshot(path=str(out/f'{slug}-{profile}-failure.png'),timeout=5000)
                        except Exception as diagnostic:result['screenshot_error']=str(diagnostic)
                    finally:
                        result['errors']=errors;result['bad_responses']=bad;results.append(result)
                        (out/f'{slug}-{profile}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                        print(json.dumps({k:result.get(k) for k in ['slug','profile','pass','failure','errors']},ensure_ascii=True),flush=True)
                        await context.close()
        finally:await browser.close()
    report={'base':args.base,'runtime_version':'20261025-7','browser_flags':FLAGS,'product_before':before,'product_after':hashes(),'prepared':len(args.slugs or SLUGS)*3,'executed':len(results),'passed':sum(r['pass'] for r in results),'results':results}
    report['pass']=report['prepared']==report['executed']==report['passed'] and before==report['product_after']
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:8195');parser.add_argument('--out',default='artifacts/visual-v3-candidate');parser.add_argument('slugs',nargs='*')
    asyncio.run(run(parser.parse_args()))
