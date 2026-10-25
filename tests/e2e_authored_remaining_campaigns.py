"""Cut Rope (2 levels), Gunman (4 waves), Perfect Square (3 levels), Penalty (5 rounds).

The fixtures explicitly align the last candy collision, real aim/targets, final
landings and deterministic opponent lanes. Source rules, battles and animations
run normally; real browser input advances and replays. Not a full playthrough.
"""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

BASE='http://127.0.0.1:8190'
OUT=Path('artifacts/campaign-proofs')
BROWSER_FLAGS=['--enable-webgl','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']
G='window.__baltigo.games[0]'
S=f'{G}.scene.getScenes(true)[0]'

async def wait(page,condition,timeout=15000):
    await page.wait_for_function(f'() => !!window.__baltigo?.games?.[0] && !!{S} && ({condition})',timeout=timeout)

async def tap(page,expression):
    at=await page.evaluate(f"""() => {{const g={G},s={S},o=({expression});if(!o)throw Error('No actual target: '+{json.dumps(expression)});const matrix=o.getWorldTransformMatrix();const b=o.getBounds?.()||{{centerX:matrix.tx,centerY:matrix.ty}},r=g.canvas.getBoundingClientRect();return {{x:r.x+b.centerX*r.width/g.scale.gameSize.width,y:r.y+b.centerY*r.height/g.scale.gameSize.height}};}}""")
    await page.touchscreen.tap(at['x'],at['y'])

async def open_game(browser,path,condition,errors,bad,start=True):
    page=await browser.new_page(viewport={'width':390,'height':650},has_touch=True,is_mobile=True,locale='pt-BR')
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
    await page.goto(BASE+'/play-v2/'+path,wait_until='networkidle')
    await wait(page,f'{S}.children?.list?.length>0')
    await page.wait_for_timeout(250)
    if start:
        await tap(page,"(()=>{const all=[];const walk=o=>{all.push(o);(o.list||[]).forEach(walk)};s.children.list.forEach(walk);return all.find(o=>o.input?.enabled&&o.visible&&/playbtn|play_game|button_play/.test(o.texture?.key||''));})()")
    await wait(page,condition)
    return page

async def main():
    reports=[]
    def save():
        (OUT/'authored-phases-rest-browser.json').write_text(json.dumps(reports,indent=2,ensure_ascii=False),encoding='utf8')
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=BROWSER_FLAGS)
        (OUT/'environment.json').write_text(json.dumps({'base':BASE,'browser_version':browser.version,'browser_flags':BROWSER_FLAGS,'viewport':{'width':390,'height':650},'fixtures':'Explicit controlled near-goal conditions; real source progression and actual browser input, not full playthroughs'},indent=2),encoding='utf8')
        # Cut Rope: the real candy/mouth collision performs the authored
        # automatic scene transition, with no synthetic completion event.
        errors=[];bad=[]
        page=await open_game(browser,'games/puzzle/cut-rope/index.html',f'{S}._levelIndex===0',errors,bad)
        phases=[]
        for index in [0,1]:
            before=await page.evaluate(f"({{index:{S}._levelIndex,frame:{G}.loop.frame,anchors:{S}.anchors.length,ropes:{S}.ropes.length}})")
            await page.evaluate(f"""() => {{const s={S};s.state.starsCollected=s.state.starsRequired;const b=s.candy.getData('body');s.matter.body.setStatic(b,true);s.matter.body.setPosition(b,{{x:s.monster.x,y:s.monster.y}});s.candy.setPosition(s.monster.x,s.monster.y);}}""")
            if index==0:
                await wait(page,f'{S}._levelIndex===1 && !{S}.state.won && !{S}.state.lost')
                after=await page.evaluate(f"({{index:{S}._levelIndex,frame:{G}.loop.frame,anchors:{S}.anchors.length,ropes:{S}.ropes.length,eating:{S}.state.eating,stars:{S}.state.starsCollected}})")
                assert after['frame']>before['frame'] and after['ropes']==3 and after['stars']==0,after
            else:
                await wait(page,f"{S}.sys.settings.key==='WinScene'")
                after={'scene':await page.evaluate(f'{S}.sys.settings.key')}
            phases.append({'near_goal_fixture':'Candy at actual monster mouth with required collected stars; source collision/capture update and tween complete naturally','before':before,'after':after})
        await tap(page,"s.children.list.find(o=>o.input?.enabled&&o.texture?.key==='lvl_replay')")
        try:
            await wait(page,f'{S}._levelIndex===1 && !{S}.state.won')
        except Exception:
            print(json.dumps({'cut_rope_replay_failure':await page.evaluate(f"() => ({{scenes:{G}.scene.getScenes(true).map(s=>({{key:s.sys.settings.key,index:s._levelIndex,state:s.state,children:s.children.list.length}}))}})"),'errors':errors,'bad':bad},ensure_ascii=True),flush=True)
            await page.screenshot(path=str(OUT/'cut-rope-replay-failure.png'))
            raise
        reset=await page.evaluate(f"({{index:{S}._levelIndex,stars:{S}.state.starsCollected,won:{S}.state.won,lost:{S}.state.lost}})")
        reports.append({'slug':'cut-rope','phases':phases,'real_replay':reset,'errors':errors,'bad_responses':bad,'passed':not errors and not bad});save();await page.close()
        print(json.dumps({'slug':'cut-rope','passed':True}),flush=True)

        # Gunman: real touches fire all three grunt shots and all three boss
        # hits. The fixture only aligns the authored moving aim and targets.
        errors=[];bad=[]
        page=await open_game(browser,'games/shooter/gunman/index.html',f"{S}.sys.settings.key==='GameScene'",errors,bad)
        waves=[]
        for index in range(4):
            await page.evaluate(f"""() => {{const s={S};s.aim.min=s.aim.max=-Math.PI/2;const e=s.groups.enemies.getChildren()[0];e.setPosition(s.player.x,s.player.y-170);e.body.reset(e.x,e.y);}}""")
            before=await page.evaluate(f"({{wave:{S}.state.waveIndex,shots:{S}.state.shotsLeft,frame:{G}.loop.frame}})")
            hits=3 if index==3 else 1
            for hit in range(hits):
                await page.touchscreen.tap(12,180)
                await page.wait_for_timeout(250)
            if index<3:
                await wait(page,f'{S}.state.waveIndex==={index+1}')
                after=await page.evaluate(f"({{wave:{S}.state.waveIndex,shots:{S}.state.shotsLeft,enemies:{S}.groups.enemies.countActive(true)}})")
                assert before['shots']-after['shots']==hits and after['enemies']==1,after
            else:
                await wait(page,f"{S}.sys.settings.key==='WinScene'")
                after={'scene':await page.evaluate(f'{S}.sys.settings.key')}
            waves.append({'before':before,'real_shots':hits,'after':after})
        await tap(page,"s.children.list.find(o=>o.input?.enabled&&o.texture?.key==='lvl_replay')")
        await wait(page,f"{S}.sys.settings.key==='GameScene'")
        reset=await page.evaluate(f"({{wave:{S}.state.waveIndex,finished:{S}.state.finished,shots:{S}.state.shotsLeft,enemies:{S}.groups.enemies.countActive(true)}})")
        assert reset['wave']==0 and not reset['finished'] and reset['enemies']==1 and reset['shots']>0,reset
        reports.append({'slug':'gunman','fixture':'Authored aim fixed vertically and real target placed directly above player; actual bullet physics and full boss3HP unchanged','waves':waves,'real_replay':reset,'errors':errors,'bad_responses':bad,'passed':not errors and not bad});save();await page.close()
        print(json.dumps({'slug':'gunman','passed':True}),flush=True)

        # Perfect Square: each final required landing is made by a real hold
        # and release; only the near-complete count and grown width are set.
        errors=[];bad=[]
        page=await open_game(browser,'games/puzzle/perfect-square/index.html',f"{S}.mode==='play'",errors,bad)
        cdp=await page.context.new_cdp_session(page)
        levels=[]
        for level in [1,2,3]:
            await wait(page,f'{S}.canGrow===true')
            await page.evaluate(f'{S}.square.successful={level-1}')
            await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':195,'y':250}]})
            await wait(page,f'{S}.isGrowing===true')
            geometry=await page.evaluate(f"""() => {{const s={S};s.growTween.stop();const outer=s.rightSquare.x-s.leftSquare.x,inner=s.rightWall.x-s.leftWall.x;const width=(outer+inner)/2;s.square.setDisplaySize(width,width);return {{outer,inner,width}};}}""")
            await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
            if level<3:
                try:
                    await wait(page,f'{S}.savedData.level==={level+1}')
                except Exception:
                    print(json.dumps({'perfect_failed_level':level,'geometry':geometry,'actual':await page.evaluate(f"({{mode:{S}.mode,level:{S}.savedData.level,successful:{S}.square.successful,canGrow:{S}.canGrow,isGrowing:{S}.isGrowing,timeLeft:{S}.timeLeft,width:{S}.square.displayWidth,outer:{S}.rightSquare.x-{S}.leftSquare.x,inner:{S}.rightWall.x-{S}.leftWall.x}})"),'errors':errors,'bad':bad},ensure_ascii=True),flush=True)
                    await page.screenshot(path=str(OUT/'perfect-square-transition-failure.png'))
                    raise
                after=await page.evaluate(f"({{level:{S}.savedData.level,successful:{S}.square.successful,mode:{S}.mode}})")
            else:
                await wait(page,f"{S}.mode==='win'")
                after={'mode':'win'}
            levels.append({'level':level,'near_goal_final_drop_geometry':geometry,'after':after})
        await tap(page,"s.winOverlay.list.find(o=>o.input?.enabled&&o.texture?.key==='lvl_replay')")
        await wait(page,f"{S}.mode==='play' && {S}.savedData.level===1")
        reset=await page.evaluate(f"({{level:{S}.savedData.level,successful:{S}.square.successful,mode:{S}.mode,timeLeft:{S}.timeLeft}})")
        assert reset['successful']==0 and reset['timeLeft']>0,reset
        reports.append({'slug':'perfect-square','levels':levels,'real_replay':reset,'errors':errors,'bad_responses':bad,'passed':not errors and not bad});save();await page.close()
        print(json.dumps({'slug':'perfect-square','passed':True}),flush=True)

        # Penalty: all five real player kicks and real defensive commits run
        # their authored animations. Deterministic CPU lanes avoid flaky wins.
        errors=[];bad=[]
        page=await open_game(browser,'games/sports/penalty/index.html',f'{S}.controls?.action && {S}.turn===\'PLAYER_AIM\'',errors,bad,start=False)
        await page.evaluate(f"() => {{const s={S};s._randLane=()=>1;s._randLaneExcept=()=>1;s.cfg.gameplay.cpuSaveBias=0;}}")
        rounds=[]
        for round_number in range(1,6):
            await wait(page,f"{S}.turn==='PLAYER_AIM' && !{S}.busy")
            await tap(page,'s.controls.action')
            await wait(page,f"{S}.turn==='CPU_AIM' && !{S}.busy")
            await tap(page,'s.controls.right')
            await tap(page,'s.controls.action')
            if round_number<5:
                await wait(page,f"{S}.round==={round_number+1} && {S}.turn==='PLAYER_AIM' && !{S}.busy")
                after=await page.evaluate(f"({{round:{S}.round,player:{S}.playerScore,cpu:{S}.cpuScore,turn:{S}.turn,busy:{S}.busy}})")
            else:
                await wait(page,f"{S}.sys.settings.key==='WinScene'")
                after=await page.evaluate(f"() => {{const s={G}.scene.getScene('GameScene');return {{round:s.round,player:s.playerScore,cpu:s.cpuScore,scene:{S}.sys.settings.key}};}}")
            rounds.append({'completed_round':round_number,'after':after})
            assert after['player']==round_number and after['cpu']==0,after
        # Penalty's minimal WinScene explicitly accepts any real canvas tap.
        await page.screenshot(path=str(OUT/'penalty-five-round-win.png'))
        replay=await page.evaluate(f"() => {S}.children.list.filter(o=>o.input?.enabled).map(o=>({{type:o.type,text:o.text,key:o.texture?.key}}))")
        await page.touchscreen.tap(195,350)
        await wait(page,f"{S}.sys.settings.key==='GameScene' && {S}.round===1")
        reset=await page.evaluate(f"({{round:{S}.round,player:{S}.playerScore,cpu:{S}.cpuScore,turn:{S}.turn,busy:{S}.busy,suddenDeath:{S}.inSuddenDeath}})")
        assert reset=={'round':1,'player':0,'cpu':0,'turn':'PLAYER_AIM','busy':False,'suddenDeath':False},reset
        reports.append({'slug':'penalty','fixture':'Deterministic opponent lane and no CPU save bias; full actual5round×2shot pointer inputs and animations','rounds':rounds,'win_replay_actions':replay,'real_replay':reset,'errors':errors,'bad_responses':bad,'passed':not errors and not bad});save();await page.close()
        print(json.dumps({'slug':'penalty','passed':True}),flush=True)
        await browser.close()
    assert len(reports)==4 and all(r['passed'] for r in reports),reports



if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8190')
    parser.add_argument('--out',type=Path,default=Path('artifacts/campaigns-remaining'))
    args=parser.parse_args()
    BASE=args.base.rstrip('/')
    OUT=args.out.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    asyncio.run(main())
