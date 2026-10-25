"""Exercise source-native result panels and real Next/Replay button gestures.

Opening a native completion handler is an isolated branch fixture. It does not
claim that the level was won through a complete human playthrough. The three
reported regressions additionally use near-win state and their real game input.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from hashlib import sha256
import re
import time
from pathlib import Path
import httpx
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
AUTHORED={'crowd-control','cut-rope','demon','gunman','perfect-square','road-cross','penalty'}
FRONTEND={'car-race','archer','ludo','chess','sudoku','crossy-road','curve-snake','memory','stack-tower','tetris','line-trap','swipe-assassin','level-devil'}
EXTERNAL_NATIVE={'football','hex-puzzle'}
INSPECT=r"""() => {
 const game=window.__baltigo?.games?.[0];const scenes=game?.scene.getScenes(true)||[];
 const objects=[];const visit=o=>{objects.push(o);if(o.list)o.list.forEach(visit);};scenes.forEach(s=>s.children.list.forEach(visit));
 const visible=o=>{for(let p=o;p;p=p.parentContainer)if(p.visible===false||p.alpha===0||p.active===false)return false;return true;};
 const cr=game?.canvas.getBoundingClientRect();
 const targets=objects.filter(o=>visible(o)&&o.input?.enabled&&typeof o.getBounds==='function').map(o=>{const b=o.getBounds();const nearby=objects.filter(t=>visible(t)&&typeof t.text==='string'&&t.text.length<45&&/^(jogar|iniciar|começar|play|start|reiniciar|replay|nova partida|continuar|repetir fase)/i.test(t.text.trim())&&b.contains(t.getBounds().centerX,t.getBounds().centerY)).map(t=>t.text);const c=o.scene.cameras.main;const p=c.matrix.transformPoint(b.centerX-c.scrollX*o.scrollFactorX,b.centerY-c.scrollY*o.scrollFactorY,{});return {label:[o.texture?.key,o.texture?.__baltigoLabel,o.text,o.name,...nearby].filter(Boolean).join(' '),next:o.__baltigoRoundConfirmation===true,x:cr.x+p.x*cr.width/game.scale.width,y:cr.y+p.y*cr.height/game.scale.height,clip:p.x<0||p.y<0||p.x>game.scale.width||p.y>game.scale.height};});
 const text=objects.filter(o=>visible(o)&&typeof o.text==='string').map(o=>o.text);
 const textBounds=objects.filter(o=>visible(o)&&typeof o.text==='string'&&o.text&&typeof o.getBounds==='function').map(o=>{const b=o.getBounds();return{text:o.text,x:b.x,y:b.y,width:b.width,height:b.height,font:o.style?.fontSize,interactive:!!o.input?.enabled,hitArea:o.input?.hitArea?{width:o.input.hitArea.width,height:o.input.hitArea.height}:null};});
 return {boot:performance.timeOrigin,version:window.__baltigo?.version,status:window.__baltigo?.status,paused:window.__baltigo?.paused,frame:game?.loop.frame,visibility:document.visibilityState,readyState:document.readyState,domReady:window.__baltigo?.domReady,readyPhase:window.__baltigo?.readyPhase,reportTimer:window.__baltigo?.reportTimer,reportCount:window.__baltigo?.reportCount,diagnostics:window.__baltigo?.frameDiagnostics?.(),loop:{running:game?.loop.running,started:game?.loop.started,paused:game?.isPaused},targets,text,textBounds,scenes:scenes.map(s=>({key:s.sys.settings.key,score:s.score??s.state?.score??null,ended:[s.hasEnded,s.isGameOver,s._gameOver,s.won].some(v=>v===true)||/^(win|won|gameover|lose|lost)$/.test(s.gameState||''),playing:s.isGameStarted??s.gameStarted??s.started??null,time:s.timerMs??s.timeLeft??s.state?.timerLeft??s.time.now,physicsPaused:s.physics?.world?.isPaused,sourcePaused:s.isPaused,keys:Object.keys(s).filter(k=>/^(player|cannon|hero|snake|avatar)/i.test(k))}))};
}"""
FIXTURE=r"""() => {
 const game=window.__baltigo?.games?.[0];if(!game)throw new Error('No Phaser game');
 const scenes=game.scene.getScenes(true);const scene=scenes.find(s=>!/menu|boot|preload|win|over|lose/i.test(s.sys.settings.key))||scenes[0];
 if(!scene)throw new Error('Scene transition has not completed');
 if(typeof scene.coresCollected==='number'&&scene.levelData?.cores)scene.coresCollected=scene.levelData.cores.length;
 if(typeof scene.score==='number')scene.score=Math.max(scene.score,scene.targetScore||scene.scoreTarget||scene.settings?.winPopCount||scene.cfg?.gameplay?.targetScore||scene.cfg?.targetScore||0);
 if(scene.sys.settings.key==='BowlingScene')scene.rolls=Array(12).fill(10);
 for(const name of ['winNow','_win','_onWin','_winLevel','winGame','handleWin','onWin','win','levelComplete','completeLevel','triggerLevelComplete','reachFinish','doWin','winLevel','winScene','showLevelComplete','showLevelCompleteUI','showLevelCompleteOverlay','showWinScene','showWin','showWinScreen','showGameComplete','showWinOverlay']){
  if(typeof scene[name]==='function'){scene[name](true);return {kind:'source-native completion branch',method:scene.sys.settings.key+'.'+name};}
 }
 for(const name of ['win','handleWin','showLevelCompleteScreen','addLevelCompleteUIElements','endLevel']){
   const fn=window.__terminalNative?.[name]||window[name];
   if(typeof fn==='function'){fn(scene,scene.levelData);return {kind:'source-native completion branch',method:'module.'+name};}
 }
 if(game.scene.keys.WinScene){scene.scene.start('WinScene',{score:scene.score||0});return {kind:'source-native result-scene branch',method:'WinScene'};}
 for(const [name,args]of [['_endRound',[true,'target']],['_endGame',[true]],['_finish',[true]],['endGame',[true]],['finishGame',[true]],['showEndScreen',[true]]]){
  if(typeof scene[name]==='function'){
   const code=Function.prototype.toString.call(scene[name]);
   if(/^[^(]*\(\s*outcome\b/.test(code))args[0]='win';
   if(/^[^(]*\(\s*sceneKey\b/.test(code))args[0]='WinScene';
   scene[name](...args);return {kind:'source-native completion branch',method:scene.sys.settings.key+'.'+name};
  }
 }
 throw new Error('No reviewed native completion entry found: '+Object.getOwnPropertyNames(Object.getPrototypeOf(scene)).join(','));
}"""

async def start_game(page,frame):
    await page.wait_for_function("""() => {
      const game=window.__baltigo?.games?.[0];return game?.scene.getScenes(true).some(s=>s.children.list.length&&!s.load?.isLoading()&&!/Boot|Preload|WinScene|GameOverScene|LoseScene/i.test(s.sys.settings.key)&&s.hasEnded!==true);
    }""",polling=100,timeout=20000)
    await page.wait_for_timeout(200)
    data=await frame.evaluate(INSPECT)
    choices=[t for t in data['targets'] if any(k in t['label'].lower() for k in ['play','start','jogar','iniciar']) and not any(k in t['label'].lower() for k in ['replay','restart','new_round'])]
    if choices:
        await click(page,choices[0])
        await page.wait_for_function('() => { const d=('+INSPECT+")();return !d.targets.some(t=>/play|start|jogar|iniciar/i.test(t.label)&&!/replay|restart|new_round/i.test(t.label));}",polling=100,timeout=20000)
    await page.wait_for_function("window.__baltigo.games[0].scene.getScenes(true).some(s=>s.children.list.length&&!/Boot|Preload|MainMenuScene/i.test(s.sys.settings.key))",polling=100,timeout=20000)
    active=await frame.evaluate(INSPECT)
    if await frame.evaluate('window.__baltigo.slug')=='dream-weaver' and any(s['playing'] is False for s in active['scenes']):
        viewport=page.viewport_size
        await page.mouse.click(viewport['width']*.5,viewport['height']*.6)
        await page.wait_for_function("window.__baltigo?.games?.some(g=>g.scene.getScenes(true).some(s=>s.started===true))",polling=100,timeout=15000)
        active=await frame.evaluate(INSPECT)
    if await frame.evaluate('window.__baltigo.slug')=='window-shooter' and any(s['key']=='MainMenu' for s in active['scenes']):
        viewport=page.viewport_size
        await page.mouse.click(viewport['width']*.5,viewport['height']*.6)
        await page.wait_for_function("window.__baltigo?.games?.some(g=>g.scene.getScenes(true).some(s=>s.sys.settings.key==='GameScene'))",polling=100,timeout=15000)
        active=await frame.evaluate(INSPECT)
    if await frame.evaluate('window.__baltigo.slug')=='flappy' and any(s['playing'] is False for s in active['scenes']):
        viewport=page.viewport_size
        await page.mouse.click(viewport['width']*.5,viewport['height']*.6)
        await page.wait_for_function("window.__baltigo?.games?.some(g=>g.scene.getScenes(true).some(s=>s.isGameStarted===true))",polling=100,timeout=15000)
        active=await frame.evaluate(INSPECT)
    assert not any(s['playing'] is False for s in active['scenes']),'Source start flag remains false after actual start gesture'
    return active

async def click(page,target):
    # These audits use an authored viewport directly, avoiding transform math.
    await page.mouse.click(target['x'],target['y'])

async def case(browser,game,args,sem):
    async with sem:
        slug=game['slug'];out=ROOT/args.out
        path=out/(slug+'.json')
        if args.resume and path.exists():return
        orientation=game.get('orientation','portrait')
        size={'width':844,'height':390} if orientation=='landscape' else {'width':390,'height':780}
        context=await browser.new_context(viewport=size,has_touch=True,is_mobile=True,locale='pt-BR')
        if args.no_clocks:
            runtime=(ROOT/'web/game-runtime.js').read_text(encoding='utf-8')
            start=runtime.index('  const originalRAF=')
            end=runtime.index('  function pause(paused)',start)
            replacement='''  const originalRAF=window.requestAnimationFrame.bind(window);
  const originalCancelRAF=window.cancelAnimationFrame.bind(window);
  const originalTimeout=window.setTimeout.bind(window);
  const originalClearTimeout=window.clearTimeout.bind(window);
  const originalInterval=window.setInterval.bind(window);
  const originalNow=performance.now.bind(performance);
  const originalDateNow=Date.now.bind(Date);
  const pendingFrames=new Map();const pendingTimeouts=new Map();
  let pauseStarted=0,pauseDuration=0,pausedScenes=[];
'''
            runtime=runtime[:start]+replacement+runtime[end:]
            await context.route('**/static/game-runtime.js*',lambda route:route.fulfill(body=runtime,content_type='application/javascript'))
        http=httpx.AsyncClient(timeout=20,trust_env=False)
        async def expose_native(route):
            try:
                response=await http.get(route.request.url)
                source=response.text
                names=set(re.findall(r'\bfunction\s+([A-Za-z_$][\w$]*)\s*\(',source))
                if names:
                    source+='\n;window.__terminalNative=Object.assign(window.__terminalNative||{}, {'+','.join(name+':typeof '+name+'==="function"?'+name+':undefined' for name in names)+'});\n'
                await route.fulfill(status=response.status_code,content_type='application/javascript',body=source)
            except Exception:
                try:await route.abort()
                except Exception:pass
        folder=ROOT/'.deploy/mirror'/Path(game['path']).parent
        needs_module_fixture=any(re.search(r'\bfunction\s+[A-Za-z_$][\w$]*\s*\(',p.read_text(encoding='utf-8-sig',errors='ignore')) for p in folder.rglob('*.js'))
        if needs_module_fixture:
            await context.route(re.compile(r'/play-v2/[^?#]*/'+re.escape(game['slug'])+r'/[^?#]*\.js(?:[?#]|$)'),expose_native)
        page=await context.new_page();errors=[];pending={};bad=[]
        page.on('request',lambda request:pending.update({request:(request.url,time.monotonic())}))
        page.on('requestfinished',lambda request:pending.pop(request,None))
        def failed_request(request):
            pending.pop(request,None)
            bad.append({'url':request.url,'error':request.failure})
        page.on('requestfailed',failed_request)
        page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
        page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
        result={'slug':slug,'viewport':size,'classification':'legacy terminal confirmation','test_method':'Native result branch fixture plus real browser button; not a complete gameplay win','pass':False}
        fixture_path=ROOT/'tests/fixtures/rounds'/(slug+'.js')
        fixture=fixture_path.read_text(encoding='utf-8') if fixture_path.exists() else FIXTURE
        replay_fixture_path=ROOT/'tests/fixtures/rounds'/(slug+'-replay.js')
        replay_fixture=replay_fixture_path.read_text(encoding='utf-8') if replay_fixture_path.exists() else fixture
        result['fixture_sha256']=sha256(fixture.encode('utf-8')).hexdigest()
        result['replay_fixture_sha256']=sha256(replay_fixture.encode('utf-8')).hexdigest()
        try:
            opened=time.monotonic()
            result['requested_release']=args.expect_version
            result['opening_url']=args.base+'/play-v2/'+game['path']+'?baltigo_release='+args.expect_version
            await page.goto(result['opening_url'],wait_until='domcontentloaded',timeout=25000)
            await page.wait_for_function("window.__baltigo?.status==='ready'",polling=100,timeout=25000)
            result['opening_ready_ms']=round((time.monotonic()-opened)*1000)
            frame=page.main_frame
            result['initial']=await start_game(page,frame)
            assert result['initial']['version']==args.expect_version,'Unexpected game runtime version'
            result['fixture']=await frame.evaluate(fixture)
            if slug in {'dream-weaver','window-shooter','screw-master'}:
                result['next_applicable']=False
                result['next_evidence']={'dream-weaver':'The authored makeEndOverlay has only Restart; no Next handler or external sceneComplete exists.','window-shooter':'The authored GameOver/LevelComplete scenes restart on any pointerdown; no authored Next or second level exists. The adapter exposes that replay as a visible button.','screw-master':'Only GameScene.endGame is reachable from gameplay, after a wrong tile or timeout. It offers any-tap Replay. The registered WinScene is unused.'}[slug]
                await page.wait_for_function('() => {const d=('+INSPECT+")();return d.targets.some(t=>/replay|restart|reiniciar|repetir|novamente/i.test(t.label));}",polling=100,timeout=15000)
                result['terminal']=await frame.evaluate(INSPECT)
                await page.screenshot(path=str(out/(slug+'-result.png')))
                replay=next(t for t in result['terminal']['targets'] if any(k in t['label'].lower() for k in ['replay','restart','reiniciar','repetir','novamente']))
                await click(page,replay)
                await page.wait_for_function('previous=>performance.timeOrigin!==previous&&window.__baltigo?.status==="ready"',arg=result['terminal']['boot'],polling=100,timeout=25000)
                result['replay']=await start_game(page,frame)
                assert result['replay']['version']==args.expect_version,'Unexpected runtime version after Replay'
                assert not any(s['ended'] for s in result['replay']['scenes'])
                previous=result['replay']['frame']
                await page.wait_for_function('previous=>window.__baltigo.games[0].loop.frame>previous+2',arg=previous,polling=100,timeout=12000)
                result['replay_active']=await frame.evaluate(INSPECT)
                result['replay_pass']=True;result['pass']=not errors
                return
            await page.wait_for_function('() => {const d=('+INSPECT+")();return d.targets.some(t=>t.next||/next|nova partida|new_round/i.test(t.label));}",polling=100,timeout=15000)
            result['terminal']=await frame.evaluate(INSPECT)
            await page.screenshot(path=str(out/(slug+'-result.png')))
            nexts=[t for t in result['terminal']['targets'] if t['next'] or any(k in t['label'].lower() for k in ['next','nova partida','new_round'])]
            if not nexts:
                raise AssertionError('Native result has no Next confirmation target')
            old_boot=result['terminal']['boot']
            await page.wait_for_timeout(500)
            assert await frame.evaluate('performance.timeOrigin')==old_boot,'Result automatically reloaded before confirmation'
            await click(page,nexts[0])
            opened=time.monotonic()
            await page.wait_for_function('previous=>performance.timeOrigin!==previous&&window.__baltigo?.status==="ready"',arg=old_boot,polling=100,timeout=25000)
            result['next_ready_ms']=round((time.monotonic()-opened)*1000)
            result['fresh']=await start_game(page,frame)
            assert result['fresh']['version']==args.expect_version,'Unexpected runtime version after Next'
            assert not any(s.get('ended') is True for s in result['fresh']['scenes']),'Source kept its finished state after confirmation'
            before=result['fresh']['frame']
            await page.wait_for_function('previous=>window.__baltigo.games[0].loop.frame>previous+2',arg=before,polling=100,timeout=12000)
            result['fresh_active']=await frame.evaluate(INSPECT)
            assert result['fresh_active']['frame']>before,'New round animation did not advance'
            assert not result['fresh_active']['paused'],'Runtime stayed paused after confirmation'
            assert not all(s.get('sourcePaused') is True for s in result['fresh_active']['scenes']),'Source remained paused after confirmation'
            assert not all(s.get('physicsPaused') is True for s in result['fresh_active']['scenes']),'Physics stayed paused after confirmation'
            result['next_pass']=True
            result['replay_fixture']=await frame.evaluate(replay_fixture)
            await page.wait_for_function('() => {const d=('+INSPECT+")();return d.targets.some(t=>/replay|restart|reiniciar|repetir|novamente/i.test(t.label)&&!t.next);}",polling=100,timeout=15000)
            terminal=await frame.evaluate(INSPECT)
            replays=[t for t in terminal['targets'] if any(k in t['label'].lower() for k in ['replay','restart','reiniciar','repetir','novamente']) and not t['next']]
            if not replays:raise AssertionError('Native result has no Replay target')
            await click(page,replays[0])
            opened=time.monotonic()
            await page.wait_for_function('previous=>performance.timeOrigin!==previous&&window.__baltigo?.status==="ready"',arg=terminal['boot'],polling=100,timeout=25000)
            result['replay_ready_ms']=round((time.monotonic()-opened)*1000)
            result['replay']=await start_game(page,frame)
            assert result['replay']['version']==args.expect_version,'Unexpected runtime version after Replay'
            assert not any(s.get('ended') is True for s in result['replay']['scenes']),'Source kept its finished state after Replay'
            before=result['replay']['frame']
            await page.wait_for_function('previous=>window.__baltigo.games[0].loop.frame>previous+2',arg=before,polling=100,timeout=12000)
            result['replay_active']=await frame.evaluate(INSPECT)
            assert result['replay_active']['frame']>before,'Replay animation did not advance'
            assert not result['replay_active']['paused'],'Runtime stayed paused after Replay'
            assert not all(s.get('sourcePaused') is True for s in result['replay_active']['scenes']),'Source stayed paused after Replay'
            assert not all(s.get('physicsPaused') is True for s in result['replay_active']['scenes']),'Physics stayed paused after Replay'
            terminal_keys={'WinScene','GameOverScene','LoseScene','VictoryScene','ResultScene'}
            assert not all(s['key'] in terminal_keys for s in result['replay_active']['scenes']),'Replay remained on result scene'
            result['replay_pass']=True
            result['pass']=not errors
        except Exception as e:
            result['failure']=str(e)
            try:result['failure_state']=await page.evaluate(INSPECT)
            except Exception:pass
        finally:
            result['errors']=errors
            result['pending_requests']=[{'url':url,'seconds':round(time.monotonic()-started,2)} for url,started in pending.values()]
            result['bad_requests']=bad
            path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'slug':slug,'pass':result['pass'],'next':result.get('next_pass',False),'replay':result.get('replay_pass',False),'failure':result.get('failure','')[:500]},ensure_ascii=False),flush=True)
            await context.unroute_all(behavior='wait')
            await http.aclose()
            await context.close()

async def run(args):
    catalog=json.loads((ROOT/'data/registry.json').read_text(encoding='utf-8'))['games']
    metadata=json.loads((ROOT/'data/catalog-pt.json').read_text(encoding='utf-8'))
    games=[{**g,**metadata[g['slug']]} for g in catalog]
    games=[g for g in games if (g['slug'] in args.slugs if args.slugs else g['slug'] not in AUTHORED|FRONTEND)]
    if args.phaser_only:
        games=[g for g in games if g['slug'] not in EXTERNAL_NATIVE]
    games=games[args.offset:args.offset+args.limit if args.limit else None]
    out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    flags=['--enable-webgl','--use-angle='+args.angle,'--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']
    if args.software_canvas:flags.append('--disable-accelerated-2d-canvas')
    product_files=[*ROOT.joinpath('app').glob('*.py'),*ROOT.joinpath('data').glob('*.json'),*ROOT.joinpath('web').glob('*.js'),*ROOT.joinpath('web/game-art').glob('*.svg')]
    hashes=lambda:{path.relative_to(ROOT).as_posix():sha256(path.read_bytes()).hexdigest() for path in sorted(product_files)}
    before_hashes=hashes()
    scope={'games':[g['slug'] for g in games],'excluded_authored':sorted(AUTHORED),'excluded_frontend':sorted(FRONTEND),'separately_tested_native':sorted(EXTERNAL_NATIVE) if args.phaser_only else [],'browser_flags':flags,'expected_runtime_version':args.expect_version,'product_sha256':before_hashes,'harness_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'scope.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')
    sem=asyncio.Semaphore(args.workers)
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=flags)
        await asyncio.gather(*(case(browser,g,args,sem) for g in games))
        await browser.close()
    after_hashes=hashes()
    scope['hashes_unchanged_during_run']=before_hashes==after_hashes
    scope['changed_files']=[path for path in before_hashes if before_hashes[path]!=after_hashes.get(path)]
    scope['backend_only_changes']=[path for path in scope['changed_files'] if path.startswith('app/leaderboard')]
    scope['game_runtime_hashes_unchanged']=all(path in scope['backend_only_changes'] for path in scope['changed_files'])
    (out/'scope.json').write_text(json.dumps(scope,indent=2),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:8198')
    parser.add_argument('--out',default='artifacts/terminal-rounds')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--offset',type=int,default=0)
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--no-clocks',action='store_true',help='Diagnostic A/B fixture only; excludes runtime clock wrappers in this test context')
    parser.add_argument('--angle',default='swiftshader-webgl',help='Headless WebGL fallback; avoids accelerating unrelated Canvas2D with SwiftShader')
    parser.add_argument('--software-canvas',action='store_true',help='Diagnostic browser environment: disable accelerated Canvas2D')
    parser.add_argument('--phaser-only',action='store_true',help='Exercise the120 Phaser legacy games; Football/Hex Puzzle require their separate native harnesses')
    parser.add_argument('--expect-version',default='20261025-7',help='Require this runtime version on initial, Next and Replay documents')
    parser.add_argument('slugs',nargs='*')
    asyncio.run(run(parser.parse_args()))
