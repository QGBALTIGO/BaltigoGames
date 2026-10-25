"""Native terminal/replay checks in an isolated same-origin iframe host.

Near-win fixtures change source state only. Real clicks, drags and animation
frames perform the final collision/move; no result messages or win functions
are called as evidence. No Telegram account or production ranking is written.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import platform
import json
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_games import HOOK

BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:8190').rstrip('/')
OUT=ROOT/os.getenv('TEST_OUTPUT_DIR','artifacts/native-rounds')
HOST='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body,iframe{width:100%;height:100%;margin:0;border:0;overflow:hidden}</style><iframe id="native" src="GAME_URL"></iframe><script>window.roundMessages=[];window.roundSequence=0;addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==document.querySelector('iframe').contentWindow)return;if(e.data?.type?.startsWith('baltigo:')){if(e.data.type==='baltigo:start')roundSequence++;roundMessages.push({roundSequence,...e.data});}})</script>'''
SNAP='''() => ({documentId:performance.timeOrigin,status:window.__baltigo?.status,outcome:window.__baltigo?.outcome,frames:(window.__nativeAnimationFrames||0)+(window.__audit?.renders||0)+(window.__audit?.draws||0)+(window.__baltigo?.games||[]).reduce((n,g)=>n+(g.loop?.frame||0),0),inputEvents:window.__audit?.inputs||0})'''

def source_path(slug):
    return next((ROOT/'.deploy/mirror/games').glob('*/'+slug))

async def open_game(browser,slug):
    metadata=json.loads((ROOT/'data/catalog-pt.json').read_text(encoding='utf-8'))[slug]
    viewport={'width':844,'height':390} if metadata.get('orientation')=='landscape' else {'width':390,'height':780}
    context=await browser.new_context(viewport=viewport,has_touch=True,is_mobile=True,locale='pt-BR')
    await context.add_init_script(HOOK)
    await context.add_init_script("const nativeRAF=window.requestAnimationFrame;window.__nativeAnimationFrames=0;window.requestAnimationFrame=callback=>nativeRAF.call(window,time=>{window.__nativeAnimationFrames++;callback(time)});")
    page=await context.new_page();page.set_default_timeout(12000)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    path=source_path(slug).relative_to(ROOT/'.deploy/mirror').as_posix()+'/index.html'
    if slug=='car-race':
        async def fixture_scope(route):
            response=await route.fetch();src=await response.text()
            anchor='function animate() {'
            assert anchor in src
            src=src.replace(anchor,'''window.__nativeFixture={
              snapshot:()=>({coinsCollected,target:CFG.targetScore,running,crashed,traffic:traffic.length}),
              prepareWin:()=>{CFG.speedStart=0;CFG.speedMax=0;CFG.speedAcceleration=0;traffic.forEach(c=>scene.remove(c));traffic.length=0;coins.forEach(c=>scene.remove(c));coins.length=0;coinsCollected=CFG.targetScore-1;spawnCoin();coins[0].position.copy(playerCar.position);},
              prepareLoss:()=>{CFG.speedStart=0;CFG.speedMax=0;CFG.speedAcceleration=0;traffic.forEach(c=>scene.remove(c));traffic.length=0;spawnTraffic();traffic[0].position.copy(playerCar.position);}
            };function animate() {''',1)
            await route.fulfill(response=response,body=src)
        await context.route('**/play-v2/'+path,fixture_scope)
    await context.route('**/__native_round_host__',lambda route:route.fulfill(content_type='text/html',body=HOST.replace('GAME_URL','/play-v2/'+path)))
    await page.goto(BASE+'/__native_round_host__',wait_until='domcontentloaded')
    await page.wait_for_function("document.querySelector('iframe').contentWindow.__baltigo?.status!=='loading' && document.querySelector('iframe').contentWindow.__baltigo?.status")
    frame=page.frames[1]
    await page.wait_for_timeout(250)
    return context,page,frame,errors

async def snapshot(page,frame,state):
    result=await frame.evaluate(SNAP)
    result['native']=await frame.evaluate(state)
    result['hostRoundSequence']=await page.evaluate('roundSequence')
    await page.evaluate('s=>(window.__nativeStates??=[]).push(s)',result)
    return result

async def terminal_snapshot(page,frame,state,expected=None):
    await frame.wait_for_function("expected=>window.__baltigo.status==='finished'&&(!expected||window.__baltigo.outcome===expected)",arg=expected,timeout=2500)
    return await snapshot(page,frame,state)

async def tap_canvas(page,frame,selector='canvas',x=.5,y=.6):
    b=await frame.locator(selector).first.bounding_box();assert b
    await page.touchscreen.tap(b['x']+b['width']*x,b['y']+b['height']*y)

async def tap_control(page,frame,selector):
    b=await frame.locator(selector).first.bounding_box();assert b
    await page.touchscreen.tap(b['x']+b['width']/2,b['y']+b['height']/2)

async def next_document(page,frame,selector,ready_condition,state,start_selector=None):
    before=await snapshot(page,frame,state)
    await tap_control(page,frame,selector)
    await page.wait_for_function("document.querySelector('iframe').contentWindow.performance.timeOrigin!=="+str(before['documentId']))
    await frame.wait_for_function(ready_condition)
    if start_selector:await tap_control(page,frame,start_selector)
    after=await snapshot(page,frame,state)
    assert after['documentId']!=before['documentId']
    return {'before':before,'after':after,'meaning':'A real confirmation starts a clean new match; no invented authored level.'}

async def replay_capture(page,frame,slug,label):
    # Capture the browser compositor directly, without waiting for decorative
    # infinite CSS animations to become stable. This still records real pixels.
    session=await page.context.new_cdp_session(page)
    try:
        data=await asyncio.wait_for(session.send('Page.captureScreenshot',{'format':'png','fromSurface':True,'captureBeyondViewport':False}),timeout=15)
        target=OUT/f'{slug}-{label}.png'
        target.write_bytes(base64.b64decode(data['data']))
        from PIL import Image
        with Image.open(target) as captured:captured.verify()
    finally:await session.detach()

async def line_trap(page,f):
    state='({playing,enemies:enemies.length,lines:lines.length})'
    await f.locator('#start button').tap();await f.wait_for_function('playing')
    initial=await snapshot(page,f,state)
    await f.evaluate('enemies=[{x:w/2,y:h*.25,r:12,speed:0}]')
    b=await f.locator('canvas').bounding_box();cy=b['y']+b['height']*.25
    await page.mouse.move(b['x']+20,cy);await page.mouse.down();await page.mouse.move(b['x']+b['width']-20,cy,steps=12);await page.mouse.up()
    await expect(f.locator('#win')).to_be_visible();won=await terminal_snapshot(page,f,state,'win')
    assert not won['native']['playing'] and won['native']['enemies']==0 and won['inputEvents']>initial['inputEvents'],won
    await replay_capture(page,f,'line-trap','win')
    await f.locator('#win button').tap();await expect(f.locator('#start')).to_be_visible();await f.locator('#start button').tap()
    reset=await snapshot(page,f,state);assert reset['native']['playing'] and reset['native']['enemies']==8
    await f.evaluate('enemies=[{x:core.x+1,y:core.y,r:10,speed:0}]')
    await expect(f.locator('#lose')).to_be_visible();lost=await terminal_snapshot(page,f,state,'lose')
    await f.locator('#lose button').tap();await expect(f.locator('#start')).to_be_visible()
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'fixture':'Last stationary enemy; real pointer drag creates collision line. Loss uses enemy one pixel from core.'}

async def swipe_assassin(page,f):
    state='({playing,player,enemies})'
    await f.wait_for_function('GAME_CONFIG!==null')
    await f.locator('#startOverlay button').tap();initial=await snapshot(page,f,state)
    await f.evaluate("player={x:0,y:0,dir:'right'};enemies=[{x:1,y:0,dir:'right',alive:true}]")
    b=await f.locator('canvas').bounding_box();x=b['x']+b['width']*.3;y=b['y']+b['height']*.5
    await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+80,y,steps=5);await page.mouse.up()
    await expect(f.locator('#winOverlay')).to_be_visible();won=await terminal_snapshot(page,f,state,'win');assert not won['native']['enemies'][0]['alive']
    await replay_capture(page,f,'swipe-assassin','win')
    await f.locator('#winOverlay button').first.tap();reset=await snapshot(page,f,state)
    assert reset['native']['playing'] and len(reset['native']['enemies'])==3
    await f.evaluate("player={x:0,y:0,dir:'right'};enemies=[{x:1,y:0,dir:'left',alive:true}]")
    await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+80,y,steps=5);await page.mouse.up()
    await expect(f.locator('#loseOverlay')).to_be_visible();lost=await terminal_snapshot(page,f,state,'lose')
    await f.locator('#loseOverlay button').tap();assert await f.evaluate('playing&&enemies.length===3')
    await f.evaluate("player={x:0,y:0,dir:'right'};enemies=[{x:1,y:0,dir:'right',alive:true}]")
    await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+80,y,steps=5);await page.mouse.up()
    await f.wait_for_function("getComputedStyle(document.querySelector('#winOverlay')).display!=='none'")
    next_round=await next_document(page,f,'#winOverlay .secondary',"typeof player!=='undefined'&&window.__baltigo.status!=='loading'",state,'#startOverlay button')
    assert next_round['after']['native']['playing'] and len(next_round['after']['native']['enemies'])==3
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'next':next_round,'fixture':'One remaining enemy; real swipe from behind wins, same swipe facing enemy loses.'}

async def stack_tower(page,f):
    state='({playing,score,target:TARGET_SCORE,blocks:blocks.length,falling:falling.length})'
    await f.locator('#startOverlay button').tap();initial=await snapshot(page,f,state)
    await f.evaluate('score=TARGET_SCORE-1;speed=0;current.position.x=blocks.at(-1).position.x')
    await tap_canvas(page,f);await expect(f.locator('#winOverlay')).to_be_visible();won=await terminal_snapshot(page,f,state,'win')
    assert won['native']['score']==won['native']['target'] and not won['native']['playing']
    await replay_capture(page,f,'stack-tower','win');await f.locator('#winOverlay button').first.tap();reset=await snapshot(page,f,state)
    assert reset['native']['playing'] and reset['native']['score']<=1 and reset['native']['blocks']<=2
    await f.evaluate('speed=0;current.position.x=blocks.at(-1).position.x+20')
    await tap_canvas(page,f);await expect(f.locator('#loseOverlay')).to_be_visible();lost=await terminal_snapshot(page,f,state,'lose')
    await f.locator('#loseOverlay button').tap();assert await f.evaluate('playing&&score<=1')
    await f.evaluate('score=TARGET_SCORE-1;speed=0;current.position.x=blocks.at(-1).position.x')
    await tap_canvas(page,f);await expect(f.locator('#winOverlay')).to_be_visible()
    next_round=await next_document(page,f,'#winOverlay .secondary',"typeof current!=='undefined'&&window.__baltigo.status!=='loading'",state,'#startOverlay button')
    assert next_round['after']['native']['playing'] and next_round['after']['native']['score']==0
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'next':next_round,'fixture':'Score one below target; aligned current block and real drop. Loss block outside overlap range and real drop.'}

async def ludo(page,f):
    state='({gameOver,currentPlayer,lastDice,steps:tokens.flat().map(t=>t.steps)})'
    await f.wait_for_function('typeof rollButton!=="undefined"');initial=await snapshot(page,f,state)
    await f.evaluate('Math.random=()=>0;tokens[0].forEach(t=>t.steps=FINAL_STEP);tokens[0][3].steps=FINAL_STEP-1;renderTokens()')
    await f.locator('#rollBtn').tap();await f.locator('.token.p0.token-select').tap();await f.wait_for_function('gameOver')
    won=await terminal_snapshot(page,f,state,'win');assert won['native']['steps'][:4]==[57]*4
    await replay_capture(page,f,'ludo','win');await f.locator('#rollBtn').tap();reset=await snapshot(page,f,state)
    assert not reset['native']['gameOver'] and set(reset['native']['steps'])=={-1}
    await f.evaluate('tokens[1].forEach(t=>t.steps=FINAL_STEP);tokens[1][3].steps=FINAL_STEP-1;currentPlayer=1;turn()')
    await f.wait_for_function('gameOver');lost=await terminal_snapshot(page,f,state,'lose')
    assert lost['native']['steps'][4:8]==[57]*4
    await f.locator('#rollBtn').tap();assert await f.evaluate('!gameOver&&tokens.flat().every(t=>t.steps===-1)')
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'fixture':'Three finished tokens; last token one step away. Real dice and selectable token clicks; native AI finishes opponent fixture.'}

def solve(grid):
    grid=[r[:] for r in grid]
    def fill():
        options=[]
        for r in range(9):
            for c in range(9):
                if not grid[r][c]:
                    used=set(grid[r])|{grid[i][c] for i in range(9)}|{grid[i][j] for i in range(r//3*3,r//3*3+3) for j in range(c//3*3,c//3*3+3)}
                    options.append((r,c,set(range(1,10))-used))
        if not options:return True
        r,c,possible=min(options,key=lambda x:len(x[2]))
        for n in sorted(possible):
            grid[r][c]=n
            if fill():return True
        grid[r][c]=0;return False
    assert fill();return grid

async def sudoku(page,f):
    state='({gameOver,timeLeft,selected,empty:grid.flat().filter(n=>!n).length})'
    initial=await snapshot(page,f,state);solution=solve(await f.evaluate('puzzle'))
    await f.evaluate('s=>{grid=s.map(r=>r.slice());grid[0][0]=0;selected=null;render()}',solution)
    await f.locator('.cell[data-r="0"][data-c="0"]').tap();await f.locator('#numPad .num').filter(has_text=str(solution[0][0])).tap()
    await f.wait_for_function('gameOver');won=await terminal_snapshot(page,f,state,'win');assert won['native']['empty']==0
    await replay_capture(page,f,'sudoku','win')
    buttons=f.locator('#newGameBtn')
    assert await buttons.count(), 'Sudoku has no actual replay control after victory'
    await buttons.tap();await f.wait_for_function('!gameOver');reset=await snapshot(page,f,state)
    assert reset['native']['empty']>0
    await f.evaluate('timeLeft=0');await f.wait_for_function('gameOver');lost=await terminal_snapshot(page,f,state,'lose')
    await replay_capture(page,f,'sudoku','timeout')
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'fixture':'Valid solver grid with one empty editable cell; real cell and number clicks. Native one-second timer reaches zero.'}

async def car_race(page,f):
    state='window.__nativeFixture.snapshot()'
    await f.wait_for_function('window.__nativeFixture');await f.locator('#howto button').tap();initial=await snapshot(page,f,state)
    await f.evaluate('window.__nativeFixture.prepareWin()');await expect(f.locator('#result')).to_be_visible();won=await terminal_snapshot(page,f,state,'win')
    assert won['native']['coinsCollected']>=won['native']['target'] and not won['native']['running']
    await replay_capture(page,f,'car-race','win');await f.locator('#result button').tap();await expect(f.locator('#howto')).to_be_visible()
    reset_before_start=await snapshot(page,f,state);assert reset_before_start['native']['coinsCollected']==0 and not reset_before_start['native']['running']
    await f.locator('#howto button').tap();reset=await snapshot(page,f,state);assert reset['native']['running']
    await f.evaluate('window.__nativeFixture.prepareLoss()');await expect(f.locator('#result')).to_be_visible();lost=await terminal_snapshot(page,f,state,'lose');assert lost['native']['crashed']
    await f.locator('#result button').tap();await expect(f.locator('#howto')).to_be_visible()
    return {'initial':initial,'win':won,'replay_before_start':reset_before_start,'replay':reset,'loss':lost,'fixture':'Test-only lexical exposure, no game logic rewrite: last coin or traffic positioned at player; native animation collision and crash timer finish.'}

async def curve_snake(page,f):
    state='({isRunning,isGameOver,score,target:TARGET_SCORE,snakeLength,trail:trail.length})'
    await tap_control(page,f,'#playButton');initial=await snapshot(page,f,state)
    await f.evaluate('score=TARGET_SCORE-POINTS_PER_FOOD;foodX=headX;foodY=headY;SNAKE_SPEED=0')
    await expect(f.locator('#replayButtonWin')).to_be_visible();won=await terminal_snapshot(page,f,state,'win')
    assert won['native']['isGameOver'] and won['native']['score']>=won['native']['target']
    await replay_capture(page,f,'curve-snake','win');await tap_control(page,f,'#replayButtonWin');await expect(f.locator('#playButton')).to_be_visible()
    reset=await snapshot(page,f,state);assert not reset['native']['isGameOver'] and reset['native']['score']==0
    await tap_control(page,f,'#playButton')
    await f.evaluate('SNAKE_SPEED=0;snakeLength=100;trail=Array.from({length:100},()=>({x:headX,y:headY}));foodX=-10000;foodY=-10000')
    await expect(f.locator('#replayButton')).to_be_visible();lost=await terminal_snapshot(page,f,state,'lose')
    await tap_control(page,f,'#replayButton');await expect(f.locator('#playButton')).to_be_visible()
    await tap_control(page,f,'#playButton');await f.evaluate('score=TARGET_SCORE-POINTS_PER_FOOD;foodX=headX;foodY=headY;SNAKE_SPEED=0')
    await expect(f.locator('#nextButtonWin')).to_be_visible()
    next_round=await next_document(page,f,'#nextButtonWin',"typeof isGameOver!=='undefined'&&window.__baltigo.status!=='loading'",state,'#playButton')
    assert next_round['after']['native']['isRunning'] and next_round['after']['native']['score']==0
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'next':next_round,'fixture':'One food below target at head; natural frame collision. Self-overlap fixture for native loss; actual replay clicks.'}

async def tetris(page,f):
    state='({score,linesCleared,level,started,isGameOver,isWin})'
    await f.locator('#btn-play').tap();initial=await snapshot(page,f,state)
    await f.evaluate("board=createEmptyBoard();board[ROWS-1]=Array(COLS).fill('I');board[ROWS-1][3]=EMPTY;score=TARGET_SCORE-1;currentPiece={type:'I',rotation:1,x:1,y:ROWS-5}")
    await f.locator('#btn-drop').tap();await f.wait_for_function('isWin');won=await terminal_snapshot(page,f,state,'win')
    assert won['native']['linesCleared']>=1 and won['native']['isGameOver']
    await replay_capture(page,f,'tetris','win');await f.locator('#btn-replay').tap();reset=await snapshot(page,f,state)
    assert reset['native']['score']==0 and not reset['native']['isGameOver'] and reset['native']['started']
    await f.evaluate("board=createEmptyBoard();board[0][4]='I';currentPiece={type:'O',rotation:0,x:3,y:ROWS-3};nextPiece={type:'I',rotation:0,x:3,y:-1}")
    await f.locator('#btn-drop').tap();await f.wait_for_function('isGameOver');lost=await terminal_snapshot(page,f,state,'lose')
    await f.locator('#btn-replay').tap();assert await f.evaluate('started&&!isGameOver&&score===0')
    await f.evaluate("board=createEmptyBoard();board[ROWS-1]=Array(COLS).fill('I');board[ROWS-1][3]=EMPTY;score=TARGET_SCORE-1;currentPiece={type:'I',rotation:1,x:1,y:ROWS-5}")
    await f.locator('#btn-drop').tap();await f.wait_for_function('isWin')
    next_round=await next_document(page,f,'#btn-next',"typeof started!=='undefined'&&window.__baltigo.status!=='loading'",state,'#btn-play')
    assert next_round['after']['native']['started'] and not next_round['after']['native']['isGameOver'] and next_round['after']['native']['score']==0
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'next':next_round,'fixture':'Last row has one gap and vertical I; real hard-drop clears row. Filled board and real drop trigger spawn loss.'}

async def crossy_road(page,f):
    state='({score,TARGET_SCORE,currentLane,currentColumn,gameStarted,isGameOver,moves:moves.length})'
    await f.locator('#howToPlay').tap();initial=await snapshot(page,f,state)
    await f.evaluate("score=TARGET_SCORE-scorePerStep;lanes[currentLane+1].occupiedPositions?.clear();lanes[currentLane+1].type='grass'")
    await f.locator('#forward').tap();await f.wait_for_function('isGameOver');won=await terminal_snapshot(page,f,state,'win')
    assert won['native']['score']>=won['native']['TARGET_SCORE'] and won['native']['currentLane']>0
    await replay_capture(page,f,'crossy-road','win');await f.locator('#retry').tap();await expect(f.locator('#howToPlay')).to_be_visible()
    reset=await snapshot(page,f,state);assert reset['native']['score']==0 and not reset['native']['isGameOver']
    await f.locator('#howToPlay').tap();await f.evaluate("score=TARGET_SCORE-scorePerStep;lanes[currentLane+1].occupiedPositions?.clear();lanes[currentLane+1].type='grass'")
    await f.locator('#forward').tap();await f.wait_for_function('isGameOver')
    next_round=await next_document(page,f,'#next',"typeof gameStarted!=='undefined'&&window.__baltigo.status!=='loading'",state,'#howToPlay')
    assert next_round['after']['native']['gameStarted'] and next_round['after']['native']['score']==0
    return {'initial':initial,'win':won,'replay':reset,'next':next_round,'fixture':'One real forward step below target; destination lane is safe grass. Native movement animation awards final point.'}

async def level_devil(page,f):
    state='({distance,speed,x:camera.position.x,z:camera.position.z,obstacles:obstacles.length})'
    initial=await snapshot(page,f,state)
    await f.locator('canvas').tap()
    await page.keyboard.down('ArrowRight');await page.wait_for_timeout(350);await page.keyboard.up('ArrowRight')
    moved=await snapshot(page,f,state);assert moved['native']['x']>initial['native']['x'] and moved['frames']>initial['frames']
    await f.evaluate('obstacles[0].position.copy(camera.position)')
    await page.wait_for_function("document.querySelector('iframe').contentWindow.performance.timeOrigin!=="+str(initial['documentId']))
    await page.wait_for_function("document.querySelector('iframe').contentWindow.__baltigo?.status==='ready'")
    reset=await snapshot(page,f,state);assert reset['native']['distance']<100 and reset['native']['obstacles']==40
    return {'initial':initial,'movement':moved,'replay':reset,'fixture':'Real movement key; one ring placed at camera. Native collision restarts document. Endless source has no authored victory/next level.'}

async def tap_phaser(page,f,pattern):
    point=await f.evaluate(r'''pattern=>{
      const regex=new RegExp(pattern,'i'),g=window.__baltigo.games[0],r=g.canvas.getBoundingClientRect(),objects=[];
      const visible=o=>{for(let p=o;p;p=p.parentContainer)if(p.visible===false||p.alpha===0)return false;return true};
      const walk=o=>{if(visible(o)&&o.input?.enabled&&regex.test([o.texture?.key,o.text,o.name,...(o.list||[]).map(c=>c.text||c.texture?.key)].join(' '))){const b=o.getBounds();objects.push({x:r.x+b.centerX*r.width/g.scale.gameSize.width,y:r.y+b.centerY*r.height/g.scale.gameSize.height,label:o.texture?.key||o.text})}if(o.list)o.list.forEach(walk)};
      g.scene.getScenes(true).forEach(s=>s.children.list.forEach(walk));return objects[0];
    }''',pattern)
    assert point, 'No visible interactive Phaser control matches '+pattern
    await page.touchscreen.tap(point['x'],point['y'])

async def chess(page,f):
    await f.wait_for_function("window.__baltigo.games[0]?.scene.keys.Chess?.pos")
    state="(()=>{const s=window.__baltigo.games[0].scene.keys.Chess;return {started:s.started,gameOver:s.gameOver,side:s.pos.side,pieces:[...s.pos.board].filter(v=>v!==0).length,win:s.winOverlay.visible,lose:s.loseOverlay.visible}})()"
    await tap_phaser(page,f,'playbtn');initial=await snapshot(page,f,state)
    async def board_click(square):
        point=await f.evaluate("sq=>{const g=window.__baltigo.games[0],s=g.scene.keys.Chess,p=s.sqCenter(sq),r=g.canvas.getBoundingClientRect();return {x:r.x+p.x*r.width/g.scale.gameSize.width,y:r.y+p.y*r.height/g.scale.gameSize.height}}",square)
        await page.touchscreen.tap(point['x'],point['y'])
    async def mate_in_one():
        await f.evaluate("()=>{const s=window.__baltigo.games[0].scene.keys.Chess;s.pos=new s.pos.constructor('7k/8/6KQ/8/8/8/8/8 w - - 0 1');s.sel=-1;s.legal=[];s.gameOver=false;s.refreshAll();s.updateStatus()}")
        await board_click(87);await board_click(102)
        await f.wait_for_function('window.__baltigo.games[0].scene.keys.Chess.winOverlay.visible',timeout=25000)
    await mate_in_one()
    won=await terminal_snapshot(page,f,state,'win');assert won['native']['gameOver']
    await replay_capture(page,f,'chess','checkmate-win');await tap_phaser(page,f,'lvl_replay');reset=await snapshot(page,f,state)
    assert reset['native']['started'] and not reset['native']['gameOver'] and reset['native']['pieces']==32
    await f.evaluate("()=>{const s=window.__baltigo.games[0].scene.keys.Chess;s.pos=new s.pos.constructor('8/8/8/8/8/5kq1/8/Q6K w - - 0 1');s.sel=-1;s.legal=[];s.gameOver=false;s.refreshAll();s.updateStatus()}")
    await board_click(0);await board_click(1)
    await f.wait_for_function('window.__baltigo.games[0].scene.keys.Chess.loseOverlay.visible',timeout=25000)
    lost=await terminal_snapshot(page,f,state,'lose');await replay_capture(page,f,'chess','checkmate-loss');await tap_phaser(page,f,'replay')
    assert await f.evaluate('!window.__baltigo.games[0].scene.keys.Chess.gameOver')
    await mate_in_one();await tap_phaser(page,f,'next');await f.wait_for_function('window.__baltigo.games[0].scene.keys.Chess.startOverlay.visible')
    next_round=await snapshot(page,f,state);assert not next_round['native']['started'] and not next_round['native']['gameOver'] and next_round['native']['pieces']==32
    await tap_phaser(page,f,'playbtn');assert await f.evaluate('window.__baltigo.games[0].scene.keys.Chess.started')
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'next':next_round,'fixture':'Three-piece mate in one, real Qh6-g7 clicks. Second legal position allows native AI mate after real Qa1-b1.'}

async def memory(page,f):
    await f.wait_for_function("window.__baltigo.games[0]?.scene.keys.MainScene?.state==='start'")
    state="(()=>{const s=window.__baltigo.games[0].scene.keys.MainScene;return {state:s.state,matched:s.matchedTiles,tiles:s.tiles?.length,time:s.totalTime}})()"
    await tap_phaser(page,f,'play|start');await f.wait_for_function("window.__baltigo.games[0].scene.keys.MainScene.state==='game'");initial=await snapshot(page,f,state)
    async def last_pair():
        pair=await f.evaluate("()=>{const g=window.__baltigo.games[0],s=g.scene.keys.MainScene,r=g.canvas.getBoundingClientRect(),a=s.tiles[0],b=s.tiles.find(t=>t!==a&&t.card===a.card);s.matchedTiles=s.tiles.length-2;s.tiles.forEach(t=>{if(t!==a&&t!==b)t.setAlpha(0).disableInteractive()});return [a,b].map(t=>{const p=t.getBounds();return {x:r.x+p.centerX*r.width/g.scale.gameSize.width,y:r.y+p.centerY*r.height/g.scale.gameSize.height}})}")
        await page.touchscreen.tap(pair[0]['x'],pair[0]['y']);await page.wait_for_timeout(350);await page.touchscreen.tap(pair[1]['x'],pair[1]['y'])
        await f.wait_for_function("window.__baltigo.games[0].scene.keys.MainScene.state==='win'")
    await last_pair();won=await terminal_snapshot(page,f,state,'win')
    await replay_capture(page,f,'memory','win');await tap_phaser(page,f,'replay_button');await f.wait_for_function("window.__baltigo.games[0].scene.keys.MainScene.state==='game'")
    reset=await snapshot(page,f,state);assert reset['native']['matched']==0 and reset['native']['tiles']>=12
    await f.evaluate('window.__baltigo.games[0].scene.keys.MainScene.totalTime=1')
    await f.wait_for_function("window.__baltigo.games[0].scene.keys.MainScene.state==='gameover'");lost=await terminal_snapshot(page,f,state,'lose')
    await tap_phaser(page,f,'retryButton');assert await f.evaluate("window.__baltigo.games[0].scene.keys.MainScene.state==='game'")
    await last_pair();before_next=await snapshot(page,f,state);await tap_phaser(page,f,'next_button')
    await page.wait_for_function("document.querySelector('iframe').contentWindow.performance.timeOrigin!=="+str(before_next['documentId']))
    await f.wait_for_function("window.__baltigo?.status==='ready'&&window.__baltigo.games[0]?.scene.keys.MainScene?.state==='start'")
    await tap_phaser(page,f,'play|start');await f.wait_for_function("window.__baltigo.games[0].scene.keys.MainScene.state==='game'")
    next_round=await snapshot(page,f,state);assert next_round['native']['matched']==0 and next_round['native']['tiles']==initial['native']['tiles']
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'next':next_round,'fixture':'One actual matching pair remains; real two tile taps reveal and match. Native countdown one second triggers loss.'}

async def archer(page,f):
    state='({isGameActive,arrowsUsed,bullseyeCount,MAX_ARROWS,BULLSEYE_TARGET})'
    await f.locator('#instructions').tap();await f.wait_for_function('isGameActive');initial=await snapshot(page,f,state)
    async def shoot(winning):
        await f.evaluate('Math.random=()=>0.5')
        point=await f.evaluate("()=>{const p=svg.createSVGPoint();p.x=50;p.y=257;const q=p.matrixTransform(svg.getScreenCTM());return {x:q.x,y:q.y}}")
        await page.mouse.move(point['x'],point['y']);await page.mouse.down();await page.wait_for_timeout(380)
        if winning:
            await f.evaluate("()=>{bullseyeCount=BULLSEYE_TARGET-1;const p=document.querySelector('#arc'),t=p.getTotalLength()*.4,a=p.getPointAtLength(t),b=p.getPointAtLength(t+1),dx=b.x-a.x,dy=b.y-a.y,n=Math.hypot(dx,dy);target={x:a.x,y:a.y};lineSegment={x1:a.x-dy/n*80,y1:a.y+dx/n*80,x2:a.x+dy/n*80,y2:a.y-dx/n*80}}")
        else:
            await f.evaluate('arrowsUsed=MAX_ARROWS-1;bullseyeCount=0;lineSegment={x1:10000,y1:0,x2:10000,y2:1000}')
        await page.mouse.up()
    await shoot(True);await expect(f.locator('#end-screen')).to_be_visible();won=await terminal_snapshot(page,f,state,'win')
    assert won['native']['bullseyeCount']>=won['native']['BULLSEYE_TARGET'],won
    await replay_capture(page,f,'archer','win');await f.locator('#btn-replay').tap();reset=await snapshot(page,f,state)
    assert reset['native']['isGameActive'] and reset['native']['arrowsUsed']==0 and reset['native']['bullseyeCount']==0
    await shoot(False);await expect(f.locator('#end-screen')).to_be_visible();lost=await terminal_snapshot(page,f,state,'lose')
    assert lost['native']['arrowsUsed']==lost['native']['MAX_ARROWS'] and not lost['native']['isGameActive']
    await f.locator('#btn-replay').tap();assert await f.evaluate('isGameActive&&arrowsUsed===0')
    await shoot(True);await expect(f.locator('#end-screen')).to_be_visible()
    next_round=await next_document(page,f,'#btn-next',"typeof isGameActive!=='undefined'&&window.__baltigo.status!=='loading'",state,'#instructions')
    assert next_round['after']['native']['isGameActive'] and next_round['after']['native']['arrowsUsed']==0
    return {'initial':initial,'win':won,'replay':reset,'loss':lost,'next':next_round,'fixture':'Target placed on actual aimed Bezier path, one bullseye remaining; real pull/release and native arrow hitTest. Last arrow misses distant target for native loss.'}

CASES={'line-trap':line_trap,'swipe-assassin':swipe_assassin,'stack-tower':stack_tower,'ludo':ludo,'sudoku':sudoku,'car-race':car_race,'curve-snake':curve_snake,'tetris':tetris,'crossy-road':crossy_road,'level-devil':level_devil,'chess':chess,'memory':memory,'archer':archer}

async def main():
    OUT.mkdir(parents=True,exist_ok=True);results=[]
    def fingerprints():
        return {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'web/game-runtime.js',ROOT/'web/game-localization.js',ROOT/'app/source_repairs.py',Path(__file__)]}
    environment={'base_url':BASE,'platform':platform.platform(),'renderer':'swiftshader-webgl','before':fingerprints(),'scope':'Headless browser with real game inputs and explicitly documented near-win fixtures; no physical Telegram/device or ranking writes'}
    (OUT/'environment.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows'])
        environment['browser_version']=browser.version
        for slug in os.getenv('TEST_GAMES',','.join(CASES)).split(','):
            context=None;result={'slug':slug,'scope':'Native source end/replay in isolated iframe; no server ranking run id or account writes'}
            try:
                context,page,frame,errors=await open_game(browser,slug)
                result.update(await CASES[slug](page,frame));result['errors']=errors;result['messages']=await page.evaluate('roundMessages')
                await page.wait_for_timeout(120);result['final']=await frame.evaluate(SNAP)
                assert not errors,errors
                result['passed']=True
            except Exception as error:
                result.update(passed=False,error=repr(error))
                if context:
                    try:await page.screenshot(path=str(OUT/f'FAIL-{slug}.png'),timeout=3000)
                    except Exception as capture_error:result['capture_error']=repr(capture_error)
                    try:result['body']=await frame.locator('body').inner_text(timeout=3000);result['messages']=await page.evaluate('roundMessages');result['stack_trace']=await frame.evaluate('window.__stackTrace')
                    except Exception:pass
                    try:result['states']=await page.evaluate('window.__nativeStates');result['errors']=errors;result['engine']=await frame.evaluate("()=>({paused:window.__baltigo.paused,scenes:window.__baltigo.games.map(g=>g.scene.getScenes(true).map(s=>({key:s.sys.settings.key,time:s.time.now,paused:s.time.paused,events:s.time.getPendingEvents?.().map(e=>({delay:e.delay,elapsed:e.elapsed,paused:e.paused})),over:s.gameOver,win:s.winOverlay?.visible,lose:s.loseOverlay?.visible})))})")
                    except Exception:pass
            finally:
                if context:await context.close()
            results.append(result);(OUT/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({key:result[key] for key in ['slug','passed','error'] if key in result},ensure_ascii=False),flush=True)
        await browser.close()
    environment['after']=fingerprints();environment['sources_unchanged']=environment['before']==environment['after']
    (OUT/'environment.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')
    return 0 if all(r['passed'] for r in results) else 1

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(asyncio.run(main()))
