"""Focused real-input proofs after the scoped presentation repairs."""
import argparse
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from audit_round_transitions import INSPECT

ROOT=Path(__file__).resolve().parents[1]
READ=r'''() => {const s=window.__baltigo,g=s.games[0];return{version:s.version,status:s.status,outcome:s.outcome,boot:performance.timeOrigin,frame:g.loop.frame,scenes:g.scene.getScenes(true).map(s=>s.sys.settings.key),text:s.texts().filter(t=>t.visible).map(t=>t.text)}}'''
POINT=r'''point=>{const g=window.__baltigo.games[0],r=g.canvas.getBoundingClientRect();return{x:r.x+point.x*r.width/g.scale.width,y:r.y+point.y*r.height/g.scale.height}}'''

async def run(args):
 out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
 registry={g['slug']:g for g in json.loads((ROOT/'data/registry.json').read_text(encoding='utf-8'))['games']}
 results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--enable-webgl','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding'])
  for slug in args.slugs:
   context=await browser.new_context(viewport={'width':390,'height':780},has_touch=True,is_mobile=True,locale='pt-BR')
   host=args.base+'/_postvisual_controls/'+slug
   html='<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0"><script>window.roundMessages=[];addEventListener("message",e=>{if(e.origin===location.origin&&e.data?.type?.startsWith("baltigo:"))roundMessages.push(e.data);});</script><iframe style="border:0;width:390px;height:780px" src="'+args.base+'/play-v2/'+registry[slug]['path']+'?baltigo_release=20261025-7"></iframe></body></html>'
   await context.route(host,lambda route:route.fulfill(body=html,content_type='text/html'))
   page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
   result={'slug':slug,'pass':False,'method':'Genuine final-server game in a neutral message-observing host, real browser gestures; no fabricated postMessages.'}
   try:
    await page.goto(host);f=page.frames[-1]
    await f.wait_for_function('window.__baltigo?.status==="ready"',polling=100,timeout=25000)
    async def tap_native(point):
     pt=await f.evaluate(POINT,point);await page.touchscreen.tap(pt['x'],pt['y'])
    async def begin():
     data=await f.evaluate(INSPECT)
     choices=[t for t in data['targets'] if any(k in t['label'].lower() for k in ['play','start','jogar']) and not any(k in t['label'].lower() for k in ['replay','restart'])]
     if choices:await page.touchscreen.tap(choices[0]['x'],choices[0]['y'])
     await f.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.children.list.length&&!/boot|preload|menu/i.test(s.sys.settings.key)&&!s.load?.isLoading())',polling=100,timeout=20000)
     await page.wait_for_timeout(1200)
    await begin()
    result['initial']=await f.evaluate(READ)
    if slug=='wordle':
     bounds=await f.evaluate(r'''() => {const s=window.__baltigo.games[0].scene.getScenes(true).find(s=>s.keyRects);return s.children.list.filter(o=>/^(enviar|apagar)$/i.test(o.text||'')).map(o=>{const b=o.getBounds(),key=s.keyRects.find(k=>Math.abs(k.x+k.w/2-o.x)<1&&Math.abs(k.y+k.h/2-o.y)<1);return{text:o.text,bounds:{x:b.x,y:b.y,width:b.width,height:b.height},key};});}''')
     assert len(bounds)==2,'Both special keyboard labels must be rendered'
     assert all(b['key']['x']+5<=b['bounds']['x'] and b['bounds']['x']+b['bounds']['width']<=b['key']['x']+b['key']['w']-5 for b in bounds),'Special keyboard label escapes key'
     result['special_key_bounds']=bounds
     async def key(code):
      point=await f.evaluate('code=>{const s=window.__baltigo.games[0].scene.getScenes(true).find(s=>s.keyRects),k=s.keyRects.find(k=>k.code===code);return{x:k.x+k.w/2,y:k.y+k.h/2}}',code)
      await tap_native(point);await page.wait_for_timeout(100)
     await key('A');await f.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.col===1)')
     await key('DEL');await f.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.col===0)')
     answer=await f.evaluate('window.__baltigo.games[0].scene.getScenes(true).find(s=>s.keyRects).answer')
     result['answer_fixture']='The native Portuguese answer was read to drive a valid word through real keys; this is not a blind solve.'
     for letter in answer:await key(letter)
     await key('ENTER');await f.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.sys.settings.key==="WinScene")',polling=100,timeout=15000)
     result['real_delete_and_submit_pass']=True
    elif slug=='ellars':
     ui=await f.evaluate(r'''() => {const g=window.__baltigo.games[0],s=g.scene.getScenes(true)[0],t=s.shuffleText,b=t.getBounds(),ratio=g.canvas.getBoundingClientRect().width/g.scale.width;const labels=s.children.list.filter(o=>typeof o.text==='string'&&o.depth===11&&o.y<150).map(o=>{const b=o.getBounds();return{text:o.text,x:b.x,y:b.y,width:b.width,height:b.height};});return{hitWidth:t.input.hitArea.width,hitHeight:t.input.hitArea.height,custom:t.input.customHitArea,cssHitHeight:t.input.hitArea.height*ratio,textBounds:{x:b.x,y:b.y,width:b.width,height:b.height},point:{x:t.x,y:t.y+55},chances:s.shuffleChances,labels};}''')
     assert ui['custom'] and ui['cssHitHeight']>=44,'Shuffle touch target is smaller than 44 CSS pixels'
     # The tap is deliberately below the text while inside the authored button.
     assert ui['point']['y']>ui['textBounds']['y']+ui['textBounds']['height']
     await tap_native(ui['point'])
     await f.wait_for_function('n=>window.__baltigo.games[0].scene.getScenes(true)[0].shuffleChances===n-1',arg=ui['chances'],polling=100,timeout=3000)
     timer=next(x for x in ui['labels'] if x['text'].startswith('Tempo'))
     value=next(x for x in ui['labels'] if ':' in x['text'] and x['text'][0].isdigit())
     assert timer['x']+timer['width']+8<=value['x'],'Timer label overlaps its value'
     result['ui']=ui;result['full_button_real_tap_pass']=True
    elif slug=='doodle-jump':
     await f.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.startgamenow===1)',polling=100,timeout=10000)
     await f.evaluate('()=>{const s=window.__baltigo.games[0].scene.getScenes(true)[0];s.doodler.body.allowGravity=false;s.doodler.setVelocity(0,0);s.initialDoodlerY=s.doodler.y+581;}')
     await f.wait_for_function('window.__baltigo.games[0].scene.getScenes(true)[0].score===58',polling=100,timeout=4000)
     bounds=await f.evaluate('()=>{const s=window.__baltigo.games[0].scene.getScenes(true)[0];return[s.scoreText,s.highScoreText].map(o=>{const b=o.getBounds();return{text:o.text,x:b.x,width:b.width,y:b.y,height:b.height};});}')
     assert bounds[0]['x']+bounds[0]['width']+20<bounds[1]['x'],'Record overlaps score'
     result['native_height_fixture']='A stable authored player height was prepared; its normal update loop calculated 58 points and record.'
     result['score_record_bounds']=bounds
    elif slug=='jump-dot':
     text=await f.evaluate('window.__baltigo.visibleText()')
     assert any('Cada toque troca' in t for t in text),'Corrected native introduction was not loaded'
     state='window.__baltigo.games[0].scene.getScenes(true)[0].flipSide'
     before=await f.evaluate(state)
     await page.touchscreen.tap(100,400);await f.wait_for_function('old=>window.__baltigo.games[0].scene.getScenes(true)[0].flipSide!==old',arg=before,polling=100,timeout=3000)
     middle=await f.evaluate(state)
     await page.touchscreen.tap(100,400);await f.wait_for_function('old=>window.__baltigo.games[0].scene.getScenes(true)[0].flipSide!==old',arg=middle,polling=100,timeout=3000)
     result['same_side_two_taps_toggle_pass']=True
    elif slug=='balance-stack':
     # Reach the same native terminal as a missed block. The real-input miss
     # transition and any-tap replay are checked separately from victory UI.
     await f.evaluate('()=>{const s=window.__baltigo.games[0].scene.getScenes(true)[0];s.showEndScreen(false);}')
     await f.wait_for_function('window.__baltigo.status==="finished"',polling=100,timeout=5000)
     result['terminal']=await f.evaluate(READ)
     result['messages_before']=await page.evaluate('roundMessages')
     await page.touchscreen.tap(40,200)
     await f.wait_for_function('window.__baltigo.games[0].scene.getScenes(true).some(s=>s.startOverlay?.active&&!s.isGameOver)',polling=100,timeout=10000)
     await begin();await f.wait_for_function('window.__baltigo.status==="playing"',polling=100,timeout=5000)
     result['messages_after']=await page.evaluate('roundMessages')
     count=lambda messages:sum(m['type']=='baltigo:start' for m in messages)
     assert count(result['messages_after'])>count(result['messages_before']),'Replay plus real Play failed to start another activity round'
     result['authored_any_tap_replay_and_new_play_pass']=True
    result['after']=await f.evaluate(READ)
    await page.screenshot(path=str(out/(slug+'.png')))
    result['pass']=not errors
   except Exception as error:result['failure']=str(error)
   result['errors']=errors;results.append(result)
   (out/(slug+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({k:result.get(k) for k in ['slug','pass','failure','errors']},ensure_ascii=True),flush=True)
   await context.close()
  await browser.close()
 (out/'report.json').write_text(json.dumps({'pass':all(r['pass'] for r in results),'results':results},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:8190');parser.add_argument('--out',default='artifacts/postvisual-controls-release');parser.add_argument('slugs',nargs='*',default=['ellars','wordle','doodle-jump','jump-dot','balance-stack'])
 asyncio.run(run(parser.parse_args()))
