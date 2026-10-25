"""Demon (15 waves), Road Cross and Crowd Control (4 waves).

Controlled near-completion fixtures preserve the actual source attacks, collisions,
battles, animations and real Next/Replay gestures. This is not a full playthrough.
"""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

BASE='http://127.0.0.1:8190'
OUT=Path('artifacts/campaign-proofs')
BROWSER_FLAGS=['--enable-webgl','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']
G='window.__baltigo.games[0]'
S=f'{G}.scene.getScenes(true)[0]'

async def target(page,expression):
    return await page.evaluate(f"""() => {{const g={G},s={S};const o=({expression});const b=o.getBounds(),r=g.canvas.getBoundingClientRect();return {{x:r.x+(b.centerX)*r.width/g.scale.gameSize.width,y:r.y+(b.centerY)*r.height/g.scale.gameSize.height,width:b.width*r.width/g.scale.gameSize.width,height:b.height*r.height/g.scale.gameSize.height}};}}""")

async def tap(page,expression):
    at=await target(page,expression)
    await page.touchscreen.tap(at['x'],at['y'])
    return at

async def start(page,path,condition):
    await page.goto(BASE+'/play-v2/'+path,wait_until='networkidle')
    await page.wait_for_function(f"() => {S}?.children?.list?.length>0")
    await page.wait_for_timeout(250)
    await tap(page,"(()=>{const all=[];const walk=o=>{all.push(o);(o.list||[]).forEach(walk)};s.children.list.forEach(walk);return all.find(o=>o.input?.enabled&&o.visible&&/playbtn|play_game|button_play/.test(o.texture?.key||''));})()")
    await page.wait_for_function(f'() => !!{S} && ({condition})',timeout=15000)

async def tap_texture(page,texture):
    return await tap(page,"s.children.list.find(o=>o.input?.enabled&&o.texture?.key==="+json.dumps(texture)+")")

async def wait(page,condition,timeout=20000):
    await page.wait_for_function(f'()=>!!window.__baltigo?.games?.[0]&&!!{S}&&({condition})',timeout=timeout)

async def crowd(browser,reports):
    errors=[];bad=[];phases=[]
    page=await browser.new_page(viewport={'width':390,'height':650},has_touch=True,is_mobile=True,locale='pt-BR')
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
    await page.goto(BASE+'/play-v2/games/arcade/crowd-control/index.html',wait_until='networkidle')
    await wait(page,f"{S}.state==='pause'")
    await tap_texture(page,'playbtn');await wait(page,f"{S}.state==='run'")
    cdp=await page.context.new_cdp_session(page)
    for wave in range(4):
        choice=await page.evaluate(f"""()=>{{const g={G},s={S};const b=s.powerups.getChildren().filter(o=>o.type==='add').sort((a,b)=>b.value-a.value)[0];const r=g.canvas.getBoundingClientRect();return {{value:b.value,x:r.x+b.x*r.width/g.scale.gameSize.width,y:r.y+(s.fixedLeaderY-250)*r.height/g.scale.gameSize.height}};}}""")
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':195,'y':choice['y']}]})
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':choice['x'],'y':choice['y']}]})
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
        # Advance only the chosen authored board's travel to its natural
        # overlap. Its actual value and all authored enemy counts remain.
        await page.evaluate(f"""()=>{{const s={S};const b=s.powerups.getChildren().filter(o=>o.type==='add').sort((a,b)=>b.value-a.value)[0];b.posY=s.players[0].getBounds().centerY;b.y=b.posY;}}""")
        await wait(page,f'{S}.boardConsumed===true && {S}.players.length>1')
        await wait(page,f'{S}.obstacles.getLength()>0')
        before=await page.evaluate(f"({{wave:{S}.waveIndex,players:{S}.players.length,enemies:{S}.obstacles.getLength(),frame:{G}.loop.frame}})")
        # Move only the front opponent to the source's battle threshold,
        # skipping scroll time while preserving the entire real battle.
        await page.evaluate(f"{S}.obstacles.getChildren()[0].y={S}.scale.height-750")
        if wave<3: await wait(page,f"{S}.waveIndex==={wave+1} && {S}.state==='run'")
        else: await wait(page,f"{S}.waveIndex===4 && {S}.children.list.some(o=>o.texture?.key==='lvlrestart'&&o.input?.enabled)")
        after=await page.evaluate(f"({{wave:{S}.waveIndex,players:{S}.players.length,enemies:{S}.obstacles.getLength(),frame:{G}.loop.frame}})")
        assert after['wave']==wave+1 and after['players']==before['players']-before['enemies'] and after['frame']>before['frame'],after
        phases.append({'authored_board_value':choice['value'],'before_battle':before,'after_battle':after})
        print(json.dumps({'crowd_wave':wave+1,'passed':True}),flush=True)
    await page.screenshot(path=str(OUT/'crowd-four-wave-win.png'))
    await tap_texture(page,'lvlrestart')
    await wait(page,f"{S}.waveIndex===0 && {S}.state==='pause' && {S}.players.length===1")
    await tap_texture(page,'playbtn');await wait(page,f"{S}.state==='run'")
    reset=await page.evaluate(f"({{wave:{S}.waveIndex,players:{S}.players.length,score:{S}.score,state:{S}.state,boards:{S}.powerups.getLength()}})")
    assert reset=={'wave':0,'players':1,'score':0,'state':'run','boards':2},reset
    report={'slug':'crowd-control','fixture':'Real horizontal touch chooses each actual highest positive authored board. Board travel and front-opponent travel shortened; all board values and all four full battle enemy counts preserved.','phases':phases,'real_replay_reset':reset,'errors':errors,'bad_responses':bad,'passed':not errors and not bad}
    (OUT/'crowd-authored-phases-browser.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps({'slug':report['slug'],'passed':report['passed'],'waves':len(phases)},ensure_ascii=True),flush=True)
    assert report['passed']
    reports.append(report)
    await page.close()

async def main():
    reports=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=BROWSER_FLAGS)
        (OUT/'environment.json').write_text(json.dumps({'base':BASE,'browser_version':browser.version,'browser_flags':BROWSER_FLAGS,'viewport':{'width':390,'height':650},'fixtures':'Explicit controlled near-goal conditions; real source progression and actual browser input, not full playthroughs'},indent=2),encoding='utf8')
        page=await browser.new_page(viewport={'width':390,'height':650},has_touch=True,is_mobile=True,locale='pt-BR')
        errors=[];bad=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
        await start(page,'games/arcade/demon/index.html',f"{S}.sys.settings.key==='GameScene'")
        phases=[]
        for wave in range(1,16):
            await page.evaluate(f"""() => {{const s={S};s.time.removeAllEvents();s.enemies.clear(true,true);s.projectiles.clear(true,true);s.pendingEnemies=0;s.akazaIsActive=true;s.state.cleared=false;s.state.invulnUntil=1e12;s.playerIsDead=false;s.state.nextAttackAt=0;s.playerFacing=1;s.player.body.allowGravity=false;s.player.setVelocity(0,0);s.player.setPosition(500,1200);s._spawnFloorBoss();const e=s.enemies.getChildren()[0];e.hp=1;e.body.allowGravity=false;e.update=()=>e.setVelocity(0,0);e.setPosition(548,1200);}}""")
            before=await page.evaluate(f"({{floor:{S}.state.floor,enemies:{S}.enemies.countActive(true),frame:{G}.loop.frame}})")
            if wave==1:
                await tap(page,"s.children.list.find(o=>o.input?.enabled&&o.texture?.key==='slash')")
            else: await page.keyboard.press('Space')
            await page.wait_for_function(f"() => !!{S} && {S}.state.cleared===true && !!{S}.nextFloorHint",timeout=10000)
            button=await target(page,'s.nextFloorHint')
            assert button['width']>=44 and button['height']>=44 and button['x']-button['width']/2>=0 and button['x']+button['width']/2<=390 and button['y']+button['height']/2<=650,button
            if wave in [1,15]: await page.screenshot(path=str(OUT/f'demon-wave-{wave}-exit.png'))
            await tap(page,'s.nextFloorHint')
            if wave<15:
                await page.wait_for_function(f"() => !!{S} && {S}.state.floor==={wave+1} && !{S}.state.cleared")
                after=await page.evaluate(f"({{floor:{S}.state.floor,cleared:{S}.state.cleared,pending:{S}.pendingEnemies,frame:{G}.loop.frame}})")
                assert after['frame']>before['frame'] and after['pending']>0,after
            else:
                await page.wait_for_function(f"() => !!{S} && {S}.sys.settings.key==='WinScene'")
                after={'scene':await page.evaluate(f'{S}.sys.settings.key')}
            phases.append({'near_completion_fixture':'Only final one-HP authored boss remains; actual attack defeats it, then real exit tap','before':before,'exit_css':button,'after':after})
            print(json.dumps({'demon_wave':wave,'passed':True}),flush=True)
        await tap(page,"s.children.list.find(o=>o.input?.enabled&&o.texture?.key==='lvl_replay')")
        await page.wait_for_function(f"() => !!{S} && {S}.sys.settings.key==='GameScene'")
        reset=await page.evaluate(f"({{floor:{S}.state.floor,cleared:{S}.state.cleared,dead:{S}.playerIsDead,kills:{S}.state.kills,hp:{S}.playerHP,maxHp:{S}.playerMaxHP}})")
        assert reset['floor']==1 and reset['cleared'] is False and reset['dead'] is False and reset['kills']==0 and reset['hp']==reset['maxHp'],reset
        reports.append({'slug':'demon','authored_waves':15,'phases':phases,'real_replay_reset':reset,'errors':errors.copy(),'bad_responses':bad.copy(),'passed':not errors and not bad})
        (OUT/'authored-phases-browser.json').write_text(json.dumps(reports,indent=2,ensure_ascii=False),encoding='utf8')
        await page.close()

        page=await browser.new_page(viewport={'width':390,'height':650},has_touch=True,is_mobile=True,locale='pt-BR')
        errors=[];bad=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
        await start(page,'games/arcade/road-cross/index.html',f'{S}._started===true')
        await page.evaluate(f"() => {{const s={S};s.cars.clear(true,true);s.player.y=s.GOAL_HEIGHT/2+s.TILE_SIZE;}}")
        await tap(page,"s.controlButtons.list.find(o=>o.texture.key==='up')")
        await page.wait_for_function(f"() => !!{S}._endOverlay && {S}.gameOver===true")
        await tap(page,"s._endOverlay.list.find(o=>o.input?.enabled&&o.texture?.key==='next')")
        await page.wait_for_function(f"() => !!{S}._startOverlay && {S}._startOverlay.visible && !{S}.gameOver")
        await tap(page,"s._startOverlay.list.find(o=>o.texture?.key==='playbtn')")
        await page.wait_for_function(f"() => !!{S} && {S}._started===true")
        level2=await page.evaluate(f"({{level:{S}.levelText.text,score:{S}.scoreText.text,started:{S}._started,input:{S}.input.enabled,paused:{S}.physics.world.isPaused}})")
        assert level2['level'].endswith('2') and level2['input'] and not level2['paused'],level2
        # A controlled one-second clock reaches the source timeout condition.
        await page.evaluate(f'{S}.timeLeft=1')
        await page.wait_for_function(f"() => !!{S} && {S}.gameOver===true && !!{S}._endOverlay",timeout=10000)
        await tap(page,"s._endOverlay.list.find(o=>o.input?.enabled&&o.texture?.key==='replay')")
        await page.wait_for_function(f"() => !!{S}._startOverlay && {S}._startOverlay.visible && !{S}.gameOver")
        await tap(page,"s._startOverlay.list.find(o=>o.texture?.key==='playbtn')")
        await page.wait_for_function(f"() => !!{S} && {S}._started===true")
        reset=await page.evaluate(f"({{level:{S}.levelText.text,score:{S}.scoreText.text,started:{S}._started,input:{S}.input.enabled,paused:{S}.physics.world.isPaused}})")
        assert reset['level'].endswith('1') and reset['score'].endswith('0') and reset['input'] and not reset['paused'],reset
        await page.screenshot(path=str(OUT/'road-cross-real-next-reset.png'))
        reports.append({'slug':'road-cross','fixture':'Player one real Up tap from goal; later source timer one second from loss','actual_next':level2,'actual_loss_replay':reset,'errors':errors,'bad_responses':bad,'passed':not errors and not bad})
        await page.close()
        await crowd(browser,reports)
        await browser.close()
    (OUT/'authored-phases-browser.json').write_text(json.dumps(reports,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps({'passed':all(r['passed'] for r in reports),'games':[{'slug':r['slug'],'passed':r['passed']} for r in reports]},ensure_ascii=True),flush=True)
    assert len(reports)==3
    assert all(r['passed'] for r in reports)



if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8190')
    parser.add_argument('--out',type=Path,default=Path('artifacts/campaigns-primary'))
    args=parser.parse_args()
    BASE=args.base.rstrip('/')
    OUT=args.out.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    asyncio.run(main())
