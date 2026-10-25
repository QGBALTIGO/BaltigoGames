"""Capture network IDs and the engine bootstrap after a real result confirmation."""
import asyncio
import argparse
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright
from audit_round_transitions import INSPECT, FIXTURE, start_game, click

ROOT=Path(__file__).resolve().parents[1]

async def run(args):
    out=ROOT/args.out
    out.mkdir(exist_ok=True,parents=True)
    records=[];requests={};errors=[]
    async with async_playwright() as p:
        flags=['--enable-webgl','--use-angle='+args.angle,'--enable-unsafe-swiftshader','--disable-background-timer-throttling','--disable-renderer-backgrounding','--disable-backgrounding-occluded-windows']
        if args.software_canvas:flags.append('--disable-accelerated-2d-canvas')
        browser=await p.chromium.launch(headless=True,args=flags)
        page=await browser.new_page(viewport={'width':390,'height':780},is_mobile=True,has_touch=True)
        cdp=await page.context.new_cdp_session(page)
        await cdp.send('Network.enable')
        await cdp.send('Performance.enable')
        def requested(event):
            requests[event['requestId']]={'url':event['request']['url'],'started':time.monotonic(),'type':event.get('type')}
        def done(event):
            entry=requests.pop(event['requestId'],None)
            if entry:records.append({**entry,'elapsed':time.monotonic()-entry['started'],'result':event})
        cdp.on('Network.requestWillBeSent',requested)
        cdp.on('Network.loadingFinished',done)
        cdp.on('Network.loadingFailed',done)
        page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
        try:
            print('opening',flush=True)
            await page.goto('http://127.0.0.1:8190/play-v2/games/puzzle/2048/index.html',wait_until='domcontentloaded')
            await page.wait_for_function('window.__baltigo?.status==="ready"',polling=100,timeout=25000)
            await start_game(page,page.main_frame)
            print('playing',flush=True)
            fixture=await page.evaluate(FIXTURE)
            previous=await page.evaluate('window.__baltigo.games[0].loop.frame')
            await page.wait_for_function('n=>window.__baltigo.games[0].loop.frame>n+2',arg=previous,polling=100,timeout=15000)
            terminal=await page.evaluate(INSPECT)
            target=next(t for t in terminal['targets'] if 'next' in t['label'].lower())
            await click(page,target)
            print('confirmed',flush=True)
            for attempt in range(7):
                await asyncio.sleep(3)
                snapshot=await page.evaluate('''() => ({state:('''+INSPECT+''')(),engines:(window.__baltigo?.games||[]).map(g=>({booted:g.isBooted,running:g.isRunning,ready:g.isReady,texturesReady:g.textures?.isReady,textureKeys:Object.keys(g.textures?.list||{}),pending:g.textures?._pending,renderer:g.renderer?.type})),scripts:[...document.scripts].map(s=>({src:s.src,type:s.type,ready:s.readyState})),resources:performance.getEntriesByType('resource').map(r=>({name:r.name,start:r.startTime,duration:r.duration,responseEnd:r.responseEnd,initiatorType:r.initiatorType})),document:document.documentElement.outerHTML.slice(-3000)})''')
                data={'attempt':attempt,'flags':flags,'snapshot':snapshot,'pending':requests,'metrics':await cdp.send('Performance.getMetrics'),'records':records,'errors':errors,'fixture':fixture}
                (out/'2048.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps({'attempt':attempt,'state':snapshot['state'],'pending':requests},ensure_ascii=False),flush=True)
                if snapshot['state'].get('status')=='ready':break
        finally:
            await browser.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--angle',default='swiftshader')
    parser.add_argument('--software-canvas',action='store_true')
    parser.add_argument('--out',default='artifacts/round-bootstrap-diagnostic')
    asyncio.run(run(parser.parse_args()))
