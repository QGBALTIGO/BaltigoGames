"""Real tile input, genuine loss and replay; no unused victory scene fixture."""
import argparse
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from audit_round_transitions import INSPECT

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOT=r'''() => {const g=window.__baltigo.games[0],s=g.scene.getScenes(true).find(s=>s.rowData?.[0]);return{boot:performance.timeOrigin,version:window.__baltigo.version,status:window.__baltigo.status,outcome:window.__baltigo.outcome,frame:g.loop.frame,score:s?.score,elapsed:s?.elapsed,gameOver:s?.gameOver,scene:s?.sys.settings.key,text:window.__baltigo.texts().filter(t=>t.visible).map(t=>t.text)}}'''
TILE=r'''wrong => {const g=window.__baltigo.games[0],s=g.scene.getScenes(true).find(s=>s.rowData?.[0]);const col=wrong?(s.rowData[0].black+1)%s.cols:s.rowData[0].black;const b=s.tiles[0][col].getBounds(),r=g.canvas.getBoundingClientRect();return{x:r.x+b.centerX*r.width/g.scale.width,y:r.y+b.centerY*r.height/g.scale.height}}'''

async def run(args):
 out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
 result={'slug':'screw-master','method':'Real black tile taps, real incorrect white tile, genuine native inline terminal and real replay gesture; no victory scene fixture','next_applicable':False,'next_evidence':'GameScene.endGame is the authored terminal; no gameplay transition to WinScene exists.','pass':False}
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--enable-webgl','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding'])
  context=await browser.new_context(viewport={'width':390,'height':780},is_mobile=True,has_touch=True)
  # Only this neutral parent host is test HTML. The iframe and all game assets
  # are genuine final-server responses; messages are received, never forged.
  host=args.base+'/_native_screw_proof_host'
  html='<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0"><script>window.roundMessages=[];addEventListener("message",e=>{if(e.origin===location.origin&&e.data?.type?.startsWith("baltigo:"))roundMessages.push(e.data);});</script><iframe style="border:0;width:390px;height:780px" src="'+args.base+'/play-v2/games/puzzle/screw-master/index.html?baltigo_release=20261025-7"></iframe></body></html>'
  await context.route(host,lambda route:route.fulfill(body=html,content_type='text/html'))
  page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
  try:
   await page.goto(host)
   frame=page.frames[-1]
   await frame.wait_for_function('window.__baltigo?.status==="ready"',polling=100,timeout=25000)
   data=await frame.evaluate(INSPECT)
   for target in data['targets']:
    if any(word in target['label'].lower() for word in ['play','jogar','start']):
     await page.mouse.click(target['x'],target['y']);break
   await frame.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.rowData?.[0]&&s.gameOver===false)',polling=100,timeout=15000)
   result['initial']=await frame.evaluate(SNAPSHOT)
   for expected in range(1,4):
    point=await frame.evaluate(TILE,False)
    await page.mouse.click(point['x'],point['y'])
    await frame.wait_for_function('n=>window.__baltigo.games[0].scene.getScenes(true).some(s=>s.score===n&&s.gameOver===false)',arg=expected,polling=100,timeout=5000)
    await page.wait_for_timeout(150)
   result['earned_score']=await frame.evaluate(SNAPSHOT)
   point=await frame.evaluate(TILE,True);await page.mouse.click(point['x'],point['y'])
   await frame.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.gameOver===true)',polling=100,timeout=5000)
   await page.wait_for_timeout(1000)
   result['terminal']=await frame.evaluate(SNAPSHOT)
   result['terminal_layout']=await frame.evaluate(r'''() => {const g=window.__baltigo.games[0],s=g.scene.getScenes(true)[0],text=s.children.list.find(o=>/^Acertos por segundo:/.test(o.text||'')),b=text.getBounds(),ratio=g.canvas.getBoundingClientRect().width/g.scale.width;return{text:text.text,x:b.x,y:b.y,width:b.width,height:b.height,logicalWidth:g.scale.width,cssFont:parseFloat(text.style.fontSize)*ratio,align:text.style.align};}''')
   layout=result['terminal_layout']
   assert layout['x']>=20 and layout['x']+layout['width']<=layout['logicalWidth']-20,'Result caption escapes the game width'
   assert layout['cssFont']>=14 and '\n' in layout['text'],'Result caption must have a readable label and separate value'
   result['messages_before_replay']=await page.evaluate('roundMessages')
   await page.screenshot(path=str(out/'terminal.png'))
   await page.mouse.click(195,390)
   await frame.wait_for_function('previous=>performance.timeOrigin!==previous&&window.__baltigo?.status==="ready"',arg=result['terminal']['boot'],polling=100,timeout=25000)
   data=await frame.evaluate(INSPECT)
   for target in data['targets']:
    if any(word in target['label'].lower() for word in ['play','jogar','start']):
     await page.mouse.click(target['x'],target['y']);break
   await frame.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.rowData?.[0]&&s.gameOver===false&&s.score===0)',polling=100,timeout=15000)
   before=await frame.evaluate(SNAPSHOT)
   await frame.wait_for_function('n=>window.__baltigo.games[0].loop.frame>n+5',arg=before['frame'],polling=100,timeout=10000)
   await page.wait_for_timeout(1000)
   result['replayed']=await frame.evaluate(SNAPSHOT)
   result['messages_after_replay']=await page.evaluate('roundMessages')
   await page.screenshot(path=str(out/'replayed.png'))
   result['native_replay_pass']=result['replayed']['score']==0 and result['replayed']['gameOver'] is False and result['replayed']['frame']>before['frame']
   point=await frame.evaluate(TILE,False);await page.mouse.click(point['x'],point['y'])
   await frame.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.score===1&&!s.gameOver)',polling=100,timeout=5000)
   result['replayed_input']=await frame.evaluate(SNAPSHOT)
   result['new_document_pass']=result['terminal']['boot']!=result['replayed']['boot']
   starts_before=sum(m['type']=='baltigo:start' for m in result['messages_before_replay'])
   starts_after=sum(m['type']=='baltigo:start' for m in result['messages_after_replay'])
   result['replay_start_event_pass']=starts_after>starts_before
   result['runtime_playing_after_replay']=result['replayed']['status']=='playing'
   result['pass']=result['native_replay_pass'] and result['replay_start_event_pass'] and result['runtime_playing_after_replay'] and result['new_document_pass'] and result['replayed_input']['score']==1 and not errors
  except Exception as error:
   result['failure']=str(error)
  result['errors']=errors
  (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({key:result.get(key) for key in ['pass','native_replay_pass','replay_start_event_pass','runtime_playing_after_replay','failure','errors']},ensure_ascii=True),flush=True)
  await browser.close()

if __name__=='__main__':
 parser=argparse.ArgumentParser()
 parser.add_argument('--base',default='http://127.0.0.1:8190')
 parser.add_argument('--out',default='artifacts/screw-native-before-fix')
 asyncio.run(run(parser.parse_args()))
