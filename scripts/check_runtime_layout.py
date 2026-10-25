"""Measure actual player and game text bounds in isolated browser sessions."""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
INSPECT = r"""() => {
 const game=window.__baltigo?.games?.[0];if(!game)return null;
 const cr=game.canvas.getBoundingClientRect();
 const ratio=cr.width/game.scale.width;
 const items=[];
 const visit=o=>{if(typeof o.text==='string'&&o.text){const b=o.getBounds();items.push({text:o.text,font:o.style?.fontSize,cssFont:parseFloat(o.style?.fontSize||0)*ratio,x:b.x,y:b.y,width:b.width,height:b.height,visible:o.visible,depth:o.depth});}if(o.list)o.list.forEach(visit);};
 const scenes=game.scene.getScenes(true).map(s=>{s.children.list.forEach(visit);return {key:s.sys.settings.key,paused:s.sys.isPaused(),state:s.gameState||s.state,score:s.score};});
 return {viewport:[innerWidth,innerHeight],canvas:{x:cr.x,y:cr.y,width:cr.width,height:cr.height},logical:[game.scale.width,game.scale.height],paused:window.__baltigo.paused,scenes,text:items,overflow:document.documentElement.scrollWidth>innerWidth+2};
}"""
TARGETS = r"""() => {
 const game=window.__baltigo.games[0];const cr=game.canvas.getBoundingClientRect();
 const out=[];const visit=o=>{if(o.visible&&o.input?.enabled&&/play|start|jogar/i.test([o.texture?.key,o.texture?.__baltigoLabel,o.text].join(' '))){const b=o.getBounds();out.push({x:cr.x+b.centerX*cr.width/game.scale.width,y:cr.y+b.centerY*cr.height/game.scale.height});}if(o.list)o.list.forEach(visit);};
 game.scene.getScenes(true).forEach(s=>s.children.list.forEach(visit));return out;
}"""

async def run(args):
    out=ROOT/'artifacts'/'runtime-layout'
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--enable-webgl','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader'])
        for slug in args.slugs:
            for profile,w,h in [('mobile',390,780),('desktop',1280,800)]:
                context=await browser.new_context(viewport={'width':w,'height':h},has_touch=profile=='mobile',is_mobile=profile=='mobile',locale='pt-BR')
                await context.route('**/telegram-web-app.js',lambda route:route.fulfill(body=''))
                page=await context.new_page()
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                await page.goto(args.base+'/?startapp='+slug)
                await page.locator('#helpDialog').wait_for(state='visible',timeout=20000)
                rotate=page.locator('[data-help-action="rotate-start"]')
                rotated=await rotate.count()>0
                if rotated:
                    await rotate.click()
                await page.locator('[data-help-action="start"]').click()
                await page.wait_for_function("document.querySelector('#gameFrame').contentWindow.__baltigo?.status==='ready'",timeout=40000)
                frame=page.frames[-1]
                before=await frame.evaluate(INSPECT)
                await page.screenshot(path=str(out/f'{slug}-{profile}-menu.png'))
                targets=await frame.evaluate(TARGETS)
                box=await page.locator('#gameFrame').bounding_box()
                if targets:
                    t=targets[0]
                    if rotated and h>w:
                        # The authored landscape viewport is rotated clockwise.
                        x=box['x']+box['width']-t['y']
                        y=box['y']+t['x']
                    else:
                        x=box['x']+t['x'];y=box['y']+t['y']
                    await page.mouse.click(x,y)
                await page.wait_for_timeout(1300)
                after=await frame.evaluate(INSPECT)
                await page.screenshot(path=str(out/f'{slug}-{profile}-playing.png'))
                result={'slug':slug,'profile':profile,'before':before,'after':after,'errors':errors}
                results.append(result)
                print(json.dumps(result,ensure_ascii=False),flush=True)
                await context.close()
        await browser.close()
    (out/'measurements.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:8190')
    parser.add_argument('slugs',nargs='*',default=['buttermilk','fruit-cosmics','demon','cannon-blaster'])
    asyncio.run(run(parser.parse_args()))
