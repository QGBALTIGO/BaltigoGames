"""Exercise every catalog game and retain per-game evidence, never just an HTTP status."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
HOOK = r"""(() => {
  window.__audit = {games:[],renderers:[],renders:0,draws:0,inputs:0};
  for(const method of ['clearRect','fillRect','drawImage','fillText']) {
    const original=CanvasRenderingContext2D.prototype[method];
    CanvasRenderingContext2D.prototype[method]=function(...args){window.__audit.draws++;return original.apply(this,args);};
  }
  for (const name of ['Phaser','THREE']) {
    let value;
    Object.defineProperty(window,name,{configurable:true,get(){return value;},set(next){
      value=next;
      const key=name==='Phaser'?'Game':'WebGLRenderer';
      if (!next?.[key] || next[key].__audited) return;
      next[key]=new Proxy(next[key],{construct(target,args,newTarget){
        const result=Reflect.construct(target,args,newTarget);
        if(name==='Phaser') window.__audit.games.push(result);
        else { window.__audit.renderers.push(result);const render=result.render;
          result.render=function(...args){window.__audit.renders++;window.__audit.scene=args[0];return render.apply(this,args);}; }
        return result;
      }});
      next[key].__audited=true;
    }});
  }
  for(const event of ['pointerdown','touchstart','keydown']) addEventListener(event,()=>window.__audit.inputs++);
})();"""
INSPECT = r"""() => {
 const audit=window.__audit||{};
 const games=[...(audit.games||[]),...(window.__baltigo?.games||[])];
 const objects=[]; const seen=new Set();
 const walk=(list)=>{for(const item of list||[]){if(!item||seen.has(item))continue;seen.add(item);objects.push(item);if(item.list)walk(item.list);}};
 for(const game of games)for(const scene of game.scene?.getScenes(true)||[])walk(scene.children?.list);
 const isVisible=o=>{for(let p=o;p;p=p.parentContainer)if(p.visible===false||p.alpha===0||p.active===false)return false;return true;};
 const missingControls=objects.filter(o=>isVisible(o)&&o.input?.enabled&&o.texture?.key==='__MISSING').map(o=>({type:o.type,name:o.name,x:o.x,y:o.y}));
 const visibleTexts=objects.filter(o=>isVisible(o)&&typeof o.text==='string');
 const startLabel=o=>{
   const direct=`${o.texture?.key||''} ${o.texture?.__baltigoLabel||''} ${o.text||''} ${o.name||''}`;
   if(/(^|[ _-])(play|start|jogar|iniciar|começar)|playbtn|playbutton|startbtn|startbutton/i.test(direct))return direct;
   const bounds=o.getBounds?.();
   if(!bounds)return '';
   const label=visibleTexts.find(t=>t.text.length<45&&/^(jogar|iniciar|começar|play|start|continuar)\b/i.test(t.text.trim())&&(()=>{const b=t.getBounds?.();return b&&bounds.contains(b.centerX,b.centerY);})());
   return label?.text||'';
 };
 const targets=objects.filter(o=>isVisible(o) && o.input?.enabled && startLabel(o)).map(o=>{
    const bounds=o.getBounds?.();const game=o.scene?.game;const canvas=game?.canvas;const rect=canvas?.getBoundingClientRect();
    const camera=o.scene?.cameras?.main;
    const point=bounds&&camera?camera.matrix.transformPoint(bounds.centerX-camera.scrollX*o.scrollFactorX,bounds.centerY-camera.scrollY*o.scrollFactorY,{}):bounds&&{x:bounds.centerX,y:bounds.centerY};
    return {label:startLabel(o),x:rect&&point?rect.x+point.x*rect.width/game.scale.width:0,
      y:rect&&point?rect.y+point.y*rect.height/game.scale.height:0};
  }).filter(o=>o.x>0&&o.x<innerWidth&&o.y>0&&o.y<innerHeight);
 const texts=objects.filter(o=>typeof o.text==='string').map(o=>o.text).concat(document.body?.innerText||'',window.__baltigo?.visibleText?.()||[]);
 const canvas=[...document.querySelectorAll('canvas')].map(c=>{const r=c.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};});
 const sceneStates=games.flatMap(g=>(g.scene?.getScenes(true)||[]).map(s=>({name:s.sys?.settings?.key,
   frame:g.loop?.frame,paused:s.sys?.isPaused?.(),score:s.score,started:s.gameStarted??s.started??s.isPlaying??s.running??s.isGameStarted??(s.startgamenow===undefined?undefined:Boolean(s.startgamenow)),state:typeof s.state==='string'?s.state:s.gameState,
   objects:(s.children?.list||[]).slice(0,120).map(o=>[o.type,Math.round(o.x||0),Math.round(o.y||0),o.text,o.visible,o.active])})));
 const htmlStart=[...document.querySelectorAll('button,[role=button],input[type=button]')].filter(el=>el.getBoundingClientRect().width&&/jogar|iniciar|começar|start|play|continuar/i.test(el.textContent||el.value||''));
 return {engine:games.length?'phaser':audit.renderers?.length?'three':canvas.length?'canvas':'dom',targets,missingControls,
   text:texts.filter(Boolean),sceneVisibleText:visibleTexts.map(t=>t.text),canvas,sceneStates,renders:audit.renders||0,draws:audit.draws||0,inputEvents:audit.inputs||0,
   htmlStart:htmlStart.map(el=>el.textContent||el.value),overflow:document.documentElement.scrollWidth>innerWidth+2,
   webgl:!!window.WebGLRenderingContext,body:document.body?.innerText?.slice(0,2000)};
}"""


async def exercise(browser, game, base, profile, out, covers, play_prefix='play-v2'):
    width,height = ((844,390) if game.get('orientation')=='landscape' else (390,780)) if profile=='preferred' else (390,780) if profile=='mobile' else (1280,800) if profile=='desktop' else (844,390)
    context=await browser.new_context(viewport={'width':width,'height':height},has_touch=profile!='desktop',is_mobile=profile!='desktop',device_scale_factor=2 if covers and profile!='desktop' else 1,locale='pt-BR')
    page=await context.new_page()
    await page.add_init_script(HOOK)
    errors=[];bad={};failed=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('response',lambda response:bad.update({response.url:response.status}) if response.status>=400 else None)
    page.on('requestfailed',lambda request:failed.append({'url':request.url,'reason':request.failure}))
    result={'slug':game['slug'],'profile':profile,'viewport':[width,height]}
    async def run_case():
        opening_started=time.monotonic()
        response=await page.goto(base+'/'+play_prefix+'/'+game['path'],wait_until='domcontentloaded',timeout=45000)
        assert response and response.status==200,'game document did not load'
        result['document_ms']=round((time.monotonic()-opening_started)*1000,1)
        try:
            await page.wait_for_load_state('networkidle',timeout=18000)
        except Exception:
            pass
        await page.wait_for_timeout(1200)
        try:
            await page.wait_for_function("""() => {
              const games=[...(window.__audit?.games||[]),...(window.__baltigo?.games||[])];
              if(games.length)return games.some(game=>(game.scene?.scenes||[]).some(scene=>scene.sys?.isActive()&&scene.children?.list?.length>0&&!/boot|preload/i.test(scene.sys.settings.key)));
              return document.querySelector('canvas,button');
            }""",timeout=18000)
        except Exception:
            pass
        before=await page.evaluate(INSPECT)
        result['render_ready_ms']=round((time.monotonic()-opening_started)*1000,1)
        result['before']=before
        started=False
        buttons=page.get_by_role('button',name=re.compile(r'^(jogar|iniciar|começar|start|play|continuar|lançar dado|nova partida)',re.I))
        for index in range(await buttons.count()):
            button=buttons.nth(index)
            if await button.is_visible():
                label=await button.text_content() or ''
                box=await button.bounding_box()
                assert box, 'start button has no hit area'
                if profile=='desktop':await page.mouse.click(box['x']+box['width']/2,box['y']+box['height']/2)
                else:await page.touchscreen.tap(box['x']+box['width']/2,box['y']+box['height']/2)
                started=True
                result['start_action']='DOM '+label
                break
        if not started and before['targets']:
            target=before['targets'][0]
            if profile=='desktop':await page.mouse.click(target['x'],target['y'])
            else:await page.touchscreen.tap(target['x'],target['y'])
            started=True
            result['start_action']='Canvas '+target['label']
        if not started:
            await page.touchscreen.tap(width*.5,height*.45) if profile!='desktop' else await page.mouse.click(width*.5,height*.45)
            result['start_action']='Direct game-area click'
            started=True
        await page.wait_for_timeout(800)
        playing=await page.evaluate(INSPECT)
        if game['slug']=='window-shooter' and any(scene.get('name')=='MainMenu' for scene in playing['sceneStates']):
            await page.touchscreen.tap(width*.5,height*.6) if profile!='desktop' else await page.mouse.click(width*.5,height*.6)
            await page.wait_for_function("window.__baltigo?.games?.some(g=>g.scene.getScenes(true).some(s=>s.sys.settings.key==='GameScene'))",timeout=15000)
            playing=await page.evaluate(INSPECT)
        if game['slug']=='flappy' and any(scene.get('started') is False for scene in playing['sceneStates']):
            await page.touchscreen.tap(width*.5,height*.6) if profile!='desktop' else await page.mouse.click(width*.5,height*.6)
            await page.wait_for_function("window.__baltigo?.games?.some(g=>g.scene.getScenes(true).some(s=>s.isGameStarted===true))",timeout=12000)
            playing=await page.evaluate(INSPECT)
        if not started and playing['targets']:
            target=playing['targets'][0]
            if profile=='desktop':await page.mouse.click(target['x'],target['y'])
            else:await page.touchscreen.tap(target['x'],target['y'])
            started=True
            result['start_action']='Canvas after load '+target['label']
            await page.wait_for_timeout(700)
            playing=await page.evaluate(INSPECT)
        if started and any(re.search(r'menu|instruction|howto|intro',scene.get('name',''),re.I) or scene.get('started') is False for scene in playing['sceneStates']):
            # Phaser applies pointer transitions on its next frame. Under a
            # software renderer this may take longer than a fixed sleep.
            try:
                await page.wait_for_function("""() => {
                    const games=[...(window.__audit?.games||[]),...(window.__baltigo?.games||[])];
                    const scenes=games.flatMap(g=>g.scene?.getScenes(true)||[]);
                    return scenes.length>0&&!scenes.some(s=>/menu|instruction|howto|intro/i.test(s.sys.settings.key)||(s.gameStarted??s.started??s.isPlaying??s.running)===false);
                }""",timeout=12000)
            except Exception:pass
            playing=await page.evaluate(INSPECT)
        result['started_ms']=round((time.monotonic()-opening_started)*1000,1)
        result['playing']=playing
        if covers and profile in {'mobile','preferred'}:
            cover_path=ROOT/'web/covers'/(game['slug']+'.png')
            canvas=page.locator('canvas:not(#confetti)').first
            from PIL import Image, ImageStat
            for attempt in range(3):
                await page.wait_for_timeout(500)
                box=await canvas.bounding_box() if await canvas.count() and await canvas.is_visible() else None
                if box and box['width']>1 and box['height']>1:
                    await page.screenshot(path=str(cover_path),clip=box,timeout=10000)
                else:await page.screenshot(path=str(cover_path),timeout=10000)
                image=Image.open(cover_path).convert('RGB')
                stats=ImageStat.Stat(image)
                if max(stats.mean)>5 or max(stats.stddev)>5:break
            result['cover_blank']=max(stats.mean)<5 and max(stats.stddev)<5
            image.thumbnail((1120,1120))
            image.save(cover_path.with_suffix('.webp'),'WEBP',quality=85)
        before_input_image=await page.screenshot(timeout=10000) if playing['engine']!='phaser' else None
        # Inputs are real browser events; source state and the resulting frame are retained.
        for key in ['ArrowLeft','ArrowUp','ArrowRight','ArrowDown','Space']:
            await page.keyboard.press(key)
            await page.wait_for_timeout(100)
        if game['slug']=='archer':
            # This SVG game starts on any tap and shoots on drag/release.
            await page.mouse.move(width*.30,height*.55)
            await page.mouse.down()
            await page.mouse.move(width*.17,height*.62,steps=8)
            await page.mouse.up()
        if game['slug']=='window-shooter':
            await page.wait_for_function("window.__baltigo?.games?.[0].scene.getScene('GameScene')?.currentCharType==='terrorist'",timeout=10000)
            target=await page.evaluate("""() => {const g=window.__baltigo.games[0],s=g.scene.getScene('GameScene'),r=s.windowRects[s.activeCharIdx],c=g.canvas.getBoundingClientRect();return {x:c.x+r.x*c.width/g.scale.width,y:c.y+r.y*c.height/g.scale.height,kills:s.kills};}""")
            if profile=='desktop':await page.mouse.click(target['x'],target['y'])
            else:await page.touchscreen.tap(target['x'],target['y'])
            await page.wait_for_function("n=>window.__baltigo.games[0].scene.getScene('GameScene').kills>n",arg=target['kills'],timeout=5000)
            result['successful_target_shot']=True
        if profile!='desktop':
            for a,b in [((.25,.5),(.75,.5)),((.6,.65),(.6,.35))]:
                await page.evaluate("([a,b])=>{let target=document.elementFromPoint(a[0],a[1]);let t=new Touch({identifier:1,target,clientX:a[0],clientY:a[1]});target.dispatchEvent(new TouchEvent('touchstart',{touches:[t],changedTouches:[t],bubbles:true}));let e=new Touch({identifier:1,target,clientX:b[0],clientY:b[1]});target.dispatchEvent(new TouchEvent('touchend',{touches:[],changedTouches:[e],bubbles:true}));}",[[a[0]*width,a[1]*height],[b[0]*width,b[1]*height]])
        await page.wait_for_timeout(1700)
        after=await page.evaluate(INSPECT)
        result['after']=after
        result['start_clicked']=started
        result['engine_frames_advanced']=any(a.get('frame',0)>b.get('frame',0) for a,b in zip(after['sceneStates'],playing['sceneStates'])) or after['renders']>playing['renders'] or after['draws']>playing['draws']
        result['state_changed']=json.dumps(after['sceneStates'])!=json.dumps(playing['sceneStates']) or after['renders']>playing['renders'] or after['body']!=playing['body']
        result['errors']=errors
        result['bad_responses']=bad
        result['failed_requests']=failed
        result['english_candidates']=list(dict.fromkeys(text for text in before['text']+after['text'] if re.search(r'\b(how to play|game over|play again|you win|you lose|score|coins|target|swipe|collect|victory|defeat|level|lives|loading|flip board|clear cell|tap to|hold to|press|reach|avoid|jump|start game|stand still)\b',text,re.I)))
        screenshot=out/(game['slug']+'-'+profile+'.png')
        after_image=await page.screenshot(path=str(screenshot))
        result['visual_frame_changed']=bool(before_input_image and hashlib.sha256(before_input_image).digest()!=hashlib.sha256(after_image).digest())
        result['screenshot']=str(screenshot.relative_to(ROOT))
        menu_remaining=any(re.search(r'menu|instruction|howto|intro',scene.get('name',''),re.I) for scene in after['sceneStates'])
        result['menu_remaining']=menu_remaining
        result['missing_controls']=before['missingControls']+after['missingControls']
        # The runtime retains historical text for diagnostics. Only active
        # scene objects and rendered DOM can prove that a tutorial is stuck.
        active_text=after['sceneVisibleText']+[after['body']] if after['engine']=='phaser' else after['text']
        instructions_remaining=any(re.search(r'toque em qualquer lugar para|toque para começar|tap anywhere to start',text,re.I) for text in active_text)
        result['instructions_remaining']=instructions_remaining
        not_started=any(s.get('started') is False for s in after['sceneStates']) and any(re.search(r'como jogar',text,re.I) for text in after['sceneVisibleText'])
        result['not_started']=not_started
        result['tutorial_remaining']=any(re.search(r'como jogar',text,re.I) for text in after['sceneVisibleText']) and any(re.search(r'play|start|jogar|iniciar',target['label'],re.I) for target in after['targets'])
        result['source_waiting']=any(str(scene.get('state','')).lower() in {'start','intro','menu','instructions'} for scene in after['sceneStates']) or (any(scene.get('started') is False for scene in after['sceneStates']) and (result['tutorial_remaining'] or instructions_remaining))
        result['passed']=not errors and not bad and not result['missing_controls'] and not result.get('cover_blank') and not after['overflow'] and not menu_remaining and not instructions_remaining and not not_started and not result['tutorial_remaining'] and not result['source_waiting'] and (started or result['engine_frames_advanced'] or after['engine']=='dom')
        if not started and not result['engine_frames_advanced']:
            result['review_required']='start or ongoing gameplay could not be confirmed'

    start=time.monotonic()
    try:
        async with asyncio.timeout(110):
            await run_case()
    except Exception as exc:
        result.update(passed=False,error=type(exc).__name__+': '+str(exc),errors=errors,bad_responses=bad)
        try:await asyncio.wait_for(page.screenshot(path=str(out/(game['slug']+'-'+profile+'-FAIL.png'))),5)
        except Exception:pass
    finally:
        result['seconds']=round(time.monotonic()-start,2)
        try:await asyncio.wait_for(context.close(),10)
        except Exception:pass
    (out/(game['slug']+'-'+profile+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({key:result.get(key) for key in ['slug','profile','passed','start_action','error','seconds']}),flush=True)
    return result


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:8187')
    parser.add_argument('--profiles',default='mobile')
    parser.add_argument('--slugs',default='')
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--output',default='artifacts/all-games')
    parser.add_argument('--covers',action='store_true')
    parser.add_argument('--cover-slugs',default='',help='Only replace covers for these slugs; preserve separately selected active frames for other games')
    parser.add_argument('--play-prefix',choices=['play','play-v2'],default='play-v2')
    args=parser.parse_args()
    catalog=json.loads((ROOT/'data/registry.json').read_text(encoding='utf-8'))['games']
    localized=ROOT/'data/catalog-pt.json'
    if localized.exists():
        metadata=json.loads(localized.read_text(encoding='utf-8'))
        for game in catalog:game.update(metadata.get(game['slug'],{}))
    if args.slugs:catalog=[game for game in catalog if game['slug'] in args.slugs.split(',')]
    out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
    (ROOT/'web/covers').mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--use-angle=swiftshader-webgl'])
        semaphore=asyncio.Semaphore(args.workers)
        cover_slugs=set(args.cover_slugs.split(',')) if args.cover_slugs else None
        async def work(game,profile):
            async with semaphore:return await exercise(browser,game,args.base.rstrip('/'),profile,out,args.covers and (cover_slugs is None or game['slug'] in cover_slugs),args.play_prefix)
        results=await asyncio.gather(*(work(game,profile) for game in catalog for profile in args.profiles.split(',')))
        await browser.close()
    summary={'base':args.base,'play_prefix':args.play_prefix,'games':len(catalog),'prepared':len(results),'executed':len(results),'passed':sum(bool(r['passed']) for r in results),'failed':[{'slug':r['slug'],'profile':r['profile'],'error':r.get('error'),'errors':r.get('errors'),'assets':r.get('bad_responses')} for r in results if not r['passed']]}
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True),flush=True)
    if summary['failed']:
        raise SystemExit(1)


if __name__=='__main__':asyncio.run(main())
