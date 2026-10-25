"""Real API continuity after native Sudoku and Penalty Replay gestures.

Only Telegram identity is synthetic. Sudoku uses a solved-board fixture and a
real final number; Penalty uses its reachable native victory-scene branch.
"""
from __future__ import annotations
import argparse, asyncio, json, sys, time
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from load_test import init_data
from e2e_native_rounds import solve


async def run(args):
    assert urlparse(args.base).hostname in {'127.0.0.1','localhost'}, 'Isolated loopback fixture only'
    out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True)
    rows=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(args=['--use-angle=swiftshader-webgl'])
        for index,slug in enumerate(args.slugs):
            context=await browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,locale='pt-BR')
            sdk="window.Telegram={WebApp:{initData:SIGNED,initDataUnsafe:{user:{id:USER,first_name:'Teste nativo'}},platform:'android',viewportHeight:innerHeight,ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},setBottomBarColor(){},disableVerticalSwipes(){},enableVerticalSwipes(){},onEvent(){},BackButton:{onClick(){},show(){},hide(){}},HapticFeedback:{impactOccurred(){}}}};"
            identity=int(time.time())*10+index
            sdk=sdk.replace('SIGNED',json.dumps(init_data(identity))).replace('USER',str(9_000_000_000+identity))
            await context.route('https://telegram.org/js/telegram-web-app.js',lambda route:route.fulfill(body=sdk,content_type='application/javascript'))
            page=await context.new_page();errors=[];responses=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            async def collect(response):
                path=urlparse(response.url).path
                if '/api/runs' in path:
                    responses.append({'path':path,'status':response.status,'method':response.request.method,'body':await response.json()})
            page.on('response',collect)
            async def count(kind,n):
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    found=[r for r in responses if r['method']=='POST' and r['path'].endswith(kind)]
                    if len(found)>=n:return found
                    await page.wait_for_timeout(100)
                raise AssertionError(f'{slug}: expected {n} actual API responses ending {kind}')
            result={'slug':slug,'passed':False,'scope':__doc__}
            try:
                await page.goto(args.base+'/?startapp='+slug,wait_until='domcontentloaded')
                await page.locator('[data-help-action="start"]').click(timeout=20000)
                await count('/api/runs',1)
                child=page.frames[-1]
                if slug=='sudoku':
                    await child.wait_for_function("typeof puzzle!=='undefined'&&document.querySelectorAll('.cell').length===81")
                    solution=solve(await child.evaluate('puzzle'))
                    await child.evaluate('s=>{grid=s.map(row=>row.slice());grid[0][0]=0;selected=null;render()}',solution)
                    await child.locator('.cell[data-r="0"][data-c="0"]').tap()
                    await child.locator('#numPad .num').filter(has_text=str(solution[0][0])).tap()
                else:
                    await child.wait_for_function("window.__baltigo?.games?.[0].scene.getScenes(true).some(s=>s.children.list.length&&!s.load.isLoading())")
                    await child.evaluate("window.__baltigo.games[0].scene.getScenes(true)[0].scene.start('WinScene',{score:5})")
                await count('/finish',1)
                before=await child.evaluate('({boot:performance.timeOrigin,status:window.__baltigo.status})')
                if slug=='sudoku':await child.locator('#newGameBtn').tap()
                else:await child.locator('canvas').tap()
                starts=await count('/api/runs',2)
                assert len({r['body']['run_id'] for r in starts})==2
                if slug=='sudoku':
                    await child.wait_for_function('old=>performance.timeOrigin!==old&&typeof gameOver!=="undefined"&&!gameOver&&grid.flat().some(n=>!n)',arg=before['boot'])
                else:
                    await child.wait_for_function("window.__baltigo.games[0].scene.getScenes(true).some(s=>s.sys.settings.key==='GameScene')&&window.__baltigo.status==='playing'")
                await page.wait_for_timeout(1000)
                await page.screenshot(path=str(out/(slug+'-new-ranked-run.png')))
                assert not errors and all(r['status']==200 for r in responses)
                result.update(passed=True,before=before,after=await child.evaluate('({boot:performance.timeOrigin,status:window.__baltigo.status,outcome:window.__baltigo.outcome})'),checks=['actual native result sent once','real Replay gesture','distinct run created through real API','source accepts a new game','no JavaScript or API errors'])
            except Exception as error:
                result['error']=repr(error)
                try:await page.screenshot(path=str(out/(slug+'-FAIL.png')))
                except Exception:pass
            finally:
                result.update(errors=errors,responses=responses);rows.append(result)
                (out/'report.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
                await context.close()
            print(json.dumps({k:v for k,v in result.items() if k not in {'responses','scope'}},ensure_ascii=True),flush=True)
        await browser.close()
    return 0 if all(row['passed'] for row in rows) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:8192')
    parser.add_argument('--out',default='artifacts/native-ranking-integration')
    parser.add_argument('slugs',nargs='*',default=['sudoku','penalty'])
    raise SystemExit(asyncio.run(run(parser.parse_args())))
