"""Regression: genuine Start must not also shoot the hostage beneath it."""
import asyncio,importlib.util,json,os
from pathlib import Path
from playwright.async_api import async_playwright
spec=importlib.util.spec_from_file_location('native',str(Path(__file__).with_name('e2e_native_rounds.py')));n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
OUT=Path(os.getenv('TEST_OUTPUT_DIR','artifacts/tee-shooter-gesture'))
STATE="(()=>{const s=window.__baltigo.games[0].scene.keys.Main;return{documentId:performance.timeOrigin,state:s.gameState,kills:s.kills,misses:s.misses,active:s.isActive,target:s.currentCharType,index:s.activeCharIdx,taps:window.nativeTapCount}})()"
async def prepare(f):
 await f.wait_for_function("window.__baltigo.games[0]?.scene.keys.Main?.startOverlay?.visible",timeout=25000)
 await f.evaluate("()=>{Phaser.Math.Between=(a,b)=>Math.floor((a+b)/2);Math.random=()=>0;window.nativeTapCount=0;const s=window.__baltigo.games[0].scene.keys.Main,actual=s.handleTap;s.handleTap=function(...args){nativeTapCount++;return actual.apply(this,args)}}")
async def main():
 OUT.mkdir(parents=True,exist_ok=True);report={'scope':'Deterministic central hostage fixture; real touchscreen Start, hostage hit, Retry, Start. No fabricated result event.','passed':False}
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True,args=['--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling'])
  c,page,f,errors=await n.open_game(b,'tee-shooter')
  try:
   await prepare(f);await n.tap_phaser(page,f,'button_play');await page.wait_for_timeout(300)
   start=await f.evaluate(STATE);report['start']=start
   assert start['state']=='playing' and start['active'] and start['taps']==0 and start['kills']==0 and start['misses']==0,start
   assert start['target']=='hostage' and start['index']==1,start
   point=await f.evaluate("()=>{const g=window.__baltigo.games[0],s=g.scene.keys.Main,t=s.windowRects[1],r=g.canvas.getBoundingClientRect();return{x:r.x+t.x*r.width/g.scale.width,y:r.y+t.y*r.height/g.scale.height}}")
   await page.touchscreen.tap(point['x'],point['y']);await f.wait_for_function("window.__baltigo.games[0].scene.keys.Main.gameOverOverlay.visible")
   report['actual_hostage_hit']=await f.evaluate(STATE);assert report['actual_hostage_hit']['state']=='gameover'
   await n.replay_capture(page,f,'tee-shooter','actual-hostage-loss')
   old=start['documentId'];await n.tap_phaser(page,f,'button_retry')
   await f.wait_for_function('previous=>performance.timeOrigin!==previous&&window.__baltigo?.status==="ready"',arg=old,timeout=25000)
   await prepare(f);await n.tap_phaser(page,f,'button_play');await page.wait_for_timeout(300)
   retry=await f.evaluate(STATE);report['retry_then_start']=retry
   assert retry['documentId']!=old and retry['state']=='playing' and retry['active'] and retry['taps']==0 and retry['kills']==0 and retry['misses']==0,retry
   assert not errors,errors;report['passed']=True
  except Exception as e:report['error']=repr(e)
  finally:report['errors']=errors;await c.close();await b.close()
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
 return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
