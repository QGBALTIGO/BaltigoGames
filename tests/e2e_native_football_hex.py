"""Native Football and Hex Puzzle: actual terminal conditions and real Next/Replay touches.

Football prepares a two-goal lead and the natural timeout; Hex prepares a score
one point below its target and invokes the real scoring callback. These are
explicit near-win fixtures, not full gameplay victories.
"""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright

BASE='http://127.0.0.1:8190'
OUT=Path('artifacts/campaign-proofs')
BROWSER_FLAGS=['--enable-webgl','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']
async def football_start(page):
    await page.wait_for_function("window.__baltigo?.status==='ready' && typeof gameStarted!=='undefined'")
    if await page.locator('#startOverlay').is_visible(): await page.locator('#startOverlay button').tap()
    await page.wait_for_function('gameStarted===true && !gameOver')
async def football_win(page):
    await page.evaluate('scoreLeft=2;scoreRight=0;matchTime=.02;goalPause=0;')
    await page.wait_for_function("gameOver===true && document.getElementById('winOverlay').style.display==='flex'")
async def football_main():
    errors=[];bad=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=BROWSER_FLAGS)
        (OUT/'environment.json').write_text(json.dumps({'base':BASE,'browser_version':browser.version,'browser_flags':BROWSER_FLAGS,'fixtures':'Football natural timeout and Hex actual scoring callback; controlled near-win conditions and real Next/Replay touches, not full playthroughs'},indent=2),encoding='utf8')
        page=await browser.new_page(viewport={'width':844,'height':390},has_touch=True,is_mobile=True,locale='pt-BR')
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
        await page.goto(BASE+'/play-v2/games/sports/football/index.html',wait_until='networkidle')
        await football_start(page);await football_win(page)
        before=await page.evaluate('({scoreLeft,scoreRight,gameStarted,gameOver,matchTime,boot:performance.timeOrigin})')
        await page.screenshot(path=str(OUT/'football-native-win.png'))
        await page.locator('#winOverlay .secondary').tap()
        await page.wait_for_function('previous=>performance.timeOrigin!==previous',arg=before['boot'])
        await football_start(page)
        next_state=await page.evaluate('({scoreLeft,scoreRight,gameStarted,gameOver,matchTime,boot:performance.timeOrigin})')
        assert next_state['scoreLeft']==0 and next_state['scoreRight']==0 and not next_state['gameOver'] and next_state['matchTime']>0,next_state
        await football_win(page)
        await page.locator('#winOverlay button:not(.secondary)').tap()
        await page.wait_for_timeout(300)
        await football_start(page)
        replay=await page.evaluate('({scoreLeft,scoreRight,gameStarted,gameOver,matchTime})')
        assert replay['scoreLeft']==0 and replay['scoreRight']==0 and not replay['gameOver'] and replay['matchTime']>0,replay
        # Actual mobile movement, not merely a running animation frame.
        x=await page.evaluate('player.x')
        button=page.locator('[data-action=right]');box=await button.bounding_box()
        cdp=await page.context.new_cdp_session(page)
        at={'x':box['x']+box['width']/2,'y':box['y']+box['height']/2}
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[at]})
        await page.wait_for_timeout(400)
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
        moved=await page.evaluate('player.x')
        assert moved>x,(x,moved)
        await browser.close()
    report={'slug':'football','engine':'native canvas, not Phaser','fixture':'Actual two-goal lead and .02seconds remaining; natural game-loop timeout opens native win screen','win':before,'real_next':next_state,'real_replay':replay,'real_touch_movement':{'before_x':x,'after_x':moved},'errors':errors,'bad_responses':bad,'passed':not errors and not bad}
    (OUT/'football-native-rounds.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    assert report['passed']



"""Native Hex Puzzle: real score branch, actual Next and Replay touches."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright



async def hex_start(page):
    await page.wait_for_function("window.__baltigo?.status==='ready' && typeof playing!=='undefined'",timeout=60000)
    if await page.locator('#howOverlay').evaluate("element=>element.classList.contains('show')"):
        await page.locator('#startBtn').tap()
    await page.wait_for_function('playing===true && !gameOver')

async def hex_win(page):
    await page.evaluate('score=TARGET_SCORE-1;addScore(1)')
    await page.wait_for_function("gameOver===true && document.getElementById('resultOverlay').classList.contains('show')")

async def hex_state(page):
    return await page.evaluate('({score,gameOver,playing,timeLeft,boot:performance.timeOrigin,resultVisible:resultOverlay.classList.contains("show")})')

async def hex_main():
    report={'slug':'hex-puzzle','engine':'native canvas, not Phaser','fixture':'Actual source scoring callback reaches its configured target with the preceding score prepared; not a full puzzle playthrough','passed':False}
    errors=[];bad=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=BROWSER_FLAGS)
        page=await browser.new_page(viewport={'width':390,'height':780},has_touch=True,is_mobile=True,locale='pt-BR')
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('response',lambda response:bad.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
        try:
            await page.goto(BASE+'/play-v2/games/puzzle/hex-puzzle/index.html',wait_until='networkidle',timeout=60000)
            await hex_start(page);await hex_win(page)
            report['win']=await hex_state(page)
            await page.screenshot(path=str(OUT/'hex-native-win.png'))
            await page.locator('#nextBtn').tap()
            await page.wait_for_function('previous=>performance.timeOrigin!==previous',arg=report['win']['boot'],timeout=60000)
            await hex_start(page)
            report['real_next']=await hex_state(page)
            assert report['real_next']['score']==0 and report['real_next']['playing'] and not report['real_next']['gameOver'] and report['real_next']['timeLeft']>0,report
            await hex_win(page)
            await page.locator('#replayBtn').tap()
            await page.wait_for_timeout(300)
            await hex_start(page)
            report['real_replay']=await hex_state(page)
            assert report['real_replay']['score']==0 and report['real_replay']['playing'] and not report['real_replay']['gameOver'] and report['real_replay']['timeLeft']>0,report
            report['passed']=not errors and not bad
        except Exception as error:
            report['failure']=str(error)
            await page.screenshot(path=str(OUT/'hex-native-failure.png'))
        finally:
            report['errors']=errors;report['bad_responses']=bad
            (OUT/'hex-native-rounds.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
            await browser.close()
    print(json.dumps(report,ensure_ascii=True),flush=True)
    assert report['passed']



async def main():
    for slug,proof in [('football',football_main),('hex-puzzle',hex_main)]:
        try:
            await proof()
        except Exception as error:
            (OUT/'failure.json').write_text(json.dumps({'slug':slug,'passed':False,'failure':str(error)},indent=2),encoding='utf8')
            raise

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8190')
    parser.add_argument('--out',type=Path,default=Path('artifacts/native-football-hex'))
    args=parser.parse_args()
    BASE=args.base.rstrip('/')
    OUT=args.out.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    asyncio.run(main())
