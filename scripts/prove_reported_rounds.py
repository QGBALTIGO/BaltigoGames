"""Near-win fixtures, real game input, and final controls through the portal."""
from __future__ import annotations
import asyncio
import argparse
import json
from pathlib import Path
from playwright.async_api import async_playwright
from audit_round_transitions import INSPECT

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=r"""slug => {
 const scene=window.__baltigo.games[0].scene.getScenes(true).find(s=>!/menu|boot|preload|win|over/i.test(s.sys.settings.key));
 if(slug==='cannon-blaster'){
   scene.score=scene.scoreTarget-10;scene.stones.clear(true,true);scene.spawnStone();
   const stone=scene.stones.getChildren()[0];stone.setData('hits',1);stone.body.reset(scene.cannon.x,scene.cannon.y-330);stone.setVelocity(0,0).body.setAllowGravity(false);stone.getData('text').setText('1');
   return {kind:'near-win score and one real stone; native auto-fire collision must supply final10points',score:scene.score,target:scene.scoreTarget};
 }
 if(slug==='fruit-cosmics'){
   scene.score=scene.targetScore-10;scene.combo=0;scene.fruits.clear(true,true);scene.corruptedFruits.clear(true,true);scene.spawnFruit();
   const fruit=scene.fruits.getChildren()[0];fruit.body.reset(540,900);fruit.setVelocity(0,0).body.setAllowGravity(false);
   const b=fruit.getBounds();return {kind:'near-win score and frozen real fruit; browser slice must supply final10points',score:scene.score,target:scene.targetScore,point:{x:b.centerX,y:b.centerY}};
 }
 scene.score=scene.targetScore-1;scene.totalPoured=50;scene.mix=Object.fromEntries(Object.entries(scene.currentOrder.targets).map(([key,pct])=>[key,pct*.5]));scene._redrawLiquid();
 const b=scene.glass.getBounds();return {kind:'near-win score and correct drink proportions; browser downward swipe must serve it',score:scene.score,target:scene.targetScore,point:{x:b.centerX,y:b.centerY},dy:200};
}"""

async def run(args):
 out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--enable-webgl','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding'])
  for slug in ['buttermilk','fruit-cosmics','cannon-blaster']:
   context=await browser.new_context(viewport={'width':390,'height':780},has_touch=True,is_mobile=True,locale='pt-BR')
   await context.route('**/telegram-web-app.js',lambda route:route.fulfill(body=''))
   page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   result={'slug':slug,'portal':args.base,'profile':'portrait390x780','pass':False,'test_method':'Controlled near-win fixture plus actual browser gameplay input and confirmation; not a full level playthrough'}
   try:
    await page.goto(args.base+'/?startapp='+slug)
    await page.locator('#helpDialog').wait_for(state='visible',timeout=20000)
    rotated=await page.locator('[data-help-action="rotate-start"]').count()>0
    if rotated:await page.locator('[data-help-action="rotate-start"]').click()
    await page.locator('[data-help-action="start"]').click()
    await page.wait_for_function("document.querySelector('#gameFrame').contentWindow.__baltigo?.status==='ready'",polling=100,timeout=35000)
    frame=page.frames[-1]
    async def click_target(target):
     box=await page.locator('#gameFrame').bounding_box()
     if rotated:x=box['x']+box['width']-target['y'];y=box['y']+target['x']
     else:x=box['x']+target['x'];y=box['y']+target['y']
     await page.mouse.click(x,y)
    async def start():
     await frame.wait_for_function("window.__baltigo.games[0].scene.getScenes(true).some(s=>s.children.list.length&&!s.load?.isLoading()&&!/Boot|Preload|WinScene|GameOverScene/i.test(s.sys.settings.key)&&s.hasEnded!==true)",polling=100,timeout=25000)
     d=await frame.evaluate(INSPECT)
     targets=[t for t in d['targets'] if any(k in t['label'].lower() for k in ['play','jogar','start']) and not any(k in t['label'].lower() for k in ['replay','restart','new_round'])]
     if targets:await click_target(targets[0])
     await frame.wait_for_function('() => {const d=('+INSPECT+")();return !d.targets.some(t=>/play|jogar|start/i.test(t.label)&&!/replay|restart|new_round/i.test(t.label));}",polling=100,timeout=25000)
    async def world(point):
     t=await frame.evaluate("p=>{const g=window.__baltigo.games[0];const r=g.canvas.getBoundingClientRect();return{x:r.x+p.x*r.width/g.scale.width,y:r.y+p.y*r.height/g.scale.height}}",point)
     box=await page.locator('#gameFrame').bounding_box()
     return {'x':box['x']+box['width']-t['y'],'y':box['y']+t['x']} if rotated else {'x':box['x']+t['x'],'y':box['y']+t['y']}
    async def win():
     result['near_win_fixture']=await frame.evaluate(FIXTURE,slug)
     fixture=result['near_win_fixture']
     if fixture.get('point'):
      point=await world(fixture['point'])
      if fixture.get('dy'):
       end=await world({**fixture['point'],'y':fixture['point']['y']+fixture['dy']})
       await page.mouse.move(point['x'],point['y']);await page.mouse.down();await page.mouse.move(end['x'],end['y'],steps=12);await page.mouse.up()
      else:await page.mouse.click(point['x'],point['y'])
     await frame.wait_for_function('() => {const d=('+INSPECT+")();return d.targets.some(t=>t.next||/new_round|next/i.test(t.label));}",polling=100,timeout=30000)
     return await frame.evaluate(INSPECT)
    await start()
    result['win']=await win()
    await page.screenshot(path=str(out/(slug+'-won.png')))
    old=result['win']['boot']
    await page.wait_for_timeout(1000)
    assert await frame.evaluate('performance.timeOrigin')==old,'Automatically reloaded result'
    await click_target(next(t for t in result['win']['targets'] if t['next'] or 'new_round' in t['label']))
    await frame.wait_for_function('old=>performance.timeOrigin!==old&&window.__baltigo?.status==="ready"',arg=old,polling=100,timeout=35000)
    await start()
    before=await frame.evaluate(INSPECT)
    await frame.wait_for_function('old=>window.__baltigo.games[0].loop.frame>old+10',arg=before['frame'],polling=100,timeout=15000)
    result['new_round']=await frame.evaluate(INSPECT)
    assert not result['new_round']['paused']
    assert all(s['ended'] is not True for s in result['new_round']['scenes'])
    assert not all(s['physicsPaused'] is True for s in result['new_round']['scenes'])
    await page.screenshot(path=str(out/(slug+'-fresh.png')))
    result['next_pass']=True
    result['second_win']=await win()
    replays=[t for t in result['second_win']['targets'] if not t['next'] and any(k in t['label'].lower() for k in ['replay','restart','reiniciar','repetir'])]
    await click_target(replays[0])
    await frame.wait_for_function('old=>performance.timeOrigin!==old&&window.__baltigo?.status==="ready"',arg=result['second_win']['boot'],polling=100,timeout=35000)
    await start()
    before=await frame.evaluate(INSPECT)
    await frame.wait_for_function('old=>window.__baltigo.games[0].loop.frame>old+10',arg=before['frame'],polling=100,timeout=15000)
    result['replayed']=await frame.evaluate(INSPECT)
    assert not result['replayed']['paused']
    assert not all(s['physicsPaused'] is True for s in result['replayed']['scenes'])
    assert all(s['ended'] is not True for s in result['replayed']['scenes'])
    result['replay_pass']=True
    result['pass']=not errors
   except Exception as error:
    result['failure']=str(error)
    try:result['failure_state']=await frame.evaluate(INSPECT)
    except Exception:pass
   result['errors']=errors;results.append(result)
   (out/(slug+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({'slug':slug,'pass':result['pass'],'next':result.get('next_pass'),'replay':result.get('replay_pass'),'failure':result.get('failure')},ensure_ascii=False),flush=True)
   await context.close()
  await browser.close()
 (out/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
 parser=argparse.ArgumentParser()
 parser.add_argument('--base',default='http://127.0.0.1:8190')
 parser.add_argument('--out',default='artifacts/reported-rounds')
 asyncio.run(run(parser.parse_args()))
