"""All142 portal headers, using real catalog and isolated same-origin player fixture."""
import asyncio,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import e2e_portal as ui
from playwright.async_api import async_playwright
OUT=Path(os.getenv('TEST_OUTPUT_DIR','artifacts/player-geometry-final'))
async def main():
 OUT.mkdir(parents=True,exist_ok=True);results=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  for width,height in [(320,740),(360,740),(390,844),(844,390)]:
   context=await browser.new_context(viewport={'width':width,'height':height})
   page=await context.new_page();await ui.intercept_telegram(page,True)
   response=await page.request.get(ui.BASE_URL+'/api/catalog?v=20261025-arcade');catalog=(await response.json())['games']
   slugs=[g['slug'] for g in catalog]
   await page.add_init_script('localStorage.setItem("baltigogames:424242:tutorials",'+json.dumps(json.dumps(slugs))+');')
   async def fixture(route):
    slug=route.request.url.split('?')[0].split('/')[-2]
    await route.fulfill(content_type='text/html',body=ui.GAME_FIXTURE.replace("slug:'snake'","slug:"+json.dumps(slug)))
   await page.route(ui.PLAY_ROUTE,fixture)
   await page.goto(ui.BASE_URL,wait_until='domcontentloaded')
   await ui.choose_view(page,'explore')
   for game in catalog:
    slug=game['slug']
    await page.locator('#exploreGrid [data-game="'+slug+'"]').evaluate('button=>button.click()')
    await page.locator('#playerLoader').wait_for(state='hidden')
    data=await page.evaluate("""()=>{const box=el=>{const r=el.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};const title=document.querySelector('#playerTitle'),meta=document.querySelector('.player-meta'),bar=document.querySelector('.player-bar');return{bar:box(bar),title:box(title),meta:box(meta),name:title.textContent,categorySize:parseFloat(getComputedStyle(document.querySelector('#playerCategory')).fontSize),titleSize:parseFloat(getComputedStyle(title).fontSize),buttons:[...bar.querySelectorAll('button')].filter(b=>b.getClientRects().length).map(b=>({id:b.id,...box(b)})),stage:box(document.querySelector('.player-stage')),overflow:document.documentElement.scrollWidth>innerWidth}}""")
    failures=[]
    if data['bar']['y']<98:failures.append('native safe area')
    if any(b['width']<44 or b['height']<44 for b in data['buttons']):failures.append('44px target')
    if any(b['x']<0 or b['right']>width for b in data['buttons']):failures.append('button outside viewport')
    if data['title']['right']>data['meta']['right']+1:failures.append('title overflow')
    if data['categorySize']<9 or data['titleSize']<12:failures.append('small text')
    if data['stage']['y']<data['bar']['bottom']-1:failures.append('stage overlap')
    if data['stage']['bottom']>height-34+1:failures.append('bottom safe area')
    if data['overflow']:failures.append('horizontal overflow')
    results.append({'slug':slug,'width':width,'height':height,'pass':not failures,'failures':failures,'geometry':data})
    if failures:await page.screenshot(path=str(OUT/('FAIL-'+slug+'-'+str(width)+'.png')))
    if slug in ['buttermilk','fruit-cosmics','cannon-blaster'] and width in [360,844]:await page.screenshot(path=str(OUT/(slug+'-'+str(width)+'.png')))
    await page.locator('#playerBack').evaluate('button=>button.click()')
   await context.close()
  await browser.close()
 report={'base_url':ui.BASE_URL,'scope':'Real142catalog titles and player controls; gameiframe replaced only in isolated browser fixture','cases':len(results),'passed':all(r['pass'] for r in results),'results':results}
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False),flush=True)
 return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(asyncio.run(main()))
