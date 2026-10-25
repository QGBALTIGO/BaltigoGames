"""Fullscreen protocol and safe-area geometry, without real Telegram/ranking.

SDK events are controlled test fixtures. The browser fullscreen scenario invokes
the actual browser API through a real button click; unsupported engines are
reported explicitly. This does not validate a physical Telegram device.
"""
from __future__ import annotations
import asyncio
from hashlib import sha256
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import traceback
from playwright.async_api import async_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fullscreen_portal_fixture',Path(__file__).with_name('e2e_portal.py'))
ui=importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)
OUT=Path(os.getenv('TEST_OUTPUT_DIR','artifacts/fullscreen-focused'))
SDK='''
window.__tgHandlers={};window.__fullscreenCalls=[];window.__fullscreenMode='async';
window.Telegram={WebApp:{initData:'synthetic-isolated-ui-test',initDataUnsafe:{user:{id:424242,first_name:'Teste'}},
platform:'ios',version:'8.0',isFullscreen:false,viewportHeight:innerHeight,
safeAreaInset:{top:59,bottom:34,left:0,right:0},contentSafeAreaInset:{top:0,bottom:0,left:0,right:0},
isVersionAtLeast(version){return parseFloat(this.version)>=parseFloat(version)},
ready(){},expand(){},setHeaderColor(){},setBackgroundColor(){},setBottomBarColor(){},disableVerticalSwipes(){},enableVerticalSwipes(){},
onEvent(name,handler){__tgHandlers[name]=handler},BackButton:{onClick(){},show(){},hide(){}},HapticFeedback:{impactOccurred(){}},
requestFullscreen(){__fullscreenCalls.push('enter');if(__fullscreenMode==='sync')__confirmFullscreen(true)},
exitFullscreen(){__fullscreenCalls.push('exit');if(__fullscreenMode==='sync')__confirmFullscreen(false)}
}};
window.__confirmFullscreen=value=>{Telegram.WebApp.isFullscreen=value;__tgHandlers.fullscreenChanged?.()};
window.__failFullscreen=error=>__tgHandlers.fullscreenFailed?.({error});
'''


async def setup(browser,sdk=SDK,width=390,height=844):
 context=await browser.new_context(viewport={'width':width,'height':height},has_touch=True,locale='pt-BR')
 page=await context.new_page();page.set_default_timeout(10000)
 errors=[];page.on('pageerror',lambda error:errors.append(error.stack or str(error)))
 requests=await ui.intercept_telegram(page,sdk is not None)
 if sdk is not None:
  await page.route('https://telegram.org/js/telegram-web-app.js',lambda route:route.fulfill(status=200,content_type='application/javascript',body=sdk))
 async def catalog(route):
  response=await route.fetch();data=await response.json()
  for game in data['games']:
   if game['slug']=='snake':game.update(orientation='landscape',logical_width=1920,logical_height=1080)
  await route.fulfill(json=data)
 await page.route('**/api/catalog**',catalog)
 await page.add_init_script("localStorage.setItem('baltigogames:424242:rotations',JSON.stringify({snake:true}));")
 await page.goto(ui.BASE_URL,wait_until='domcontentloaded')
 await page.locator('#featuredRail [data-game="snake"]').click()
 await ui.continue_without_rotation(page)
 await page.locator('[data-help-action="start"]').click()
 await expect(page.locator('#playerLoader')).to_be_hidden()
 return context,page,errors,requests


async def geometry(page,minimum_top):
 header=await page.locator('.player-bar').bounding_box();stage=await page.locator('.player-stage').bounding_box()
 viewport=await page.evaluate('({width:innerWidth,height:innerHeight})')
 assert header and stage and header['y']>=minimum_top-1,(header,minimum_top)
 assert stage['y']>=header['y']+header['height']-1,(stage,header)
 assert header['x']>=-1 and header['x']+header['width']<=viewport['width']+1,header
 for button in await page.locator('.player-bar button:visible').all():
  box=await button.bounding_box()
  assert box and box['width']>=44 and box['height']>=44,box
  assert box['x']>=header['x']-1 and box['x']+box['width']<=header['x']+header['width']+1,box
  assert box['y']>=header['y']-1 and box['y']+box['height']<=header['y']+header['height']+1,box
 assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
 return {'header':header,'stage':stage,'viewport':viewport,'safe_top':await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--tg-safe-top')")}


async def sdk_async(browser,name):
 context,page,errors,requests=await setup(browser)
 result={'scenario':'sdk_async_safe_area_rotation_cleanup','checks':[]}
 try:
  button=page.locator('#playerFullscreen')
  await expect(button).to_have_attribute('aria-pressed','false');await expect(button).to_have_attribute('aria-busy','true')
  assert await page.evaluate('__fullscreenCalls')==['enter']
  await expect(page.locator('#playerRotate')).to_have_attribute('aria-pressed','false')
  result['checks'].extend(['async_request_does_not_fake_fullscreen','legacy_rotation_preference_not_reused'])
  await page.evaluate('__confirmFullscreen(true)')
  await expect(button).to_have_attribute('aria-pressed','true');await expect(button).to_be_enabled()
  result['portrait']=await geometry(page,115)
  await expect(page.locator('#playerRotate')).to_have_attribute('aria-pressed','false')
  await page.locator('#playerHelp').click()
  box=await page.locator('#helpDialog').bounding_box()
  assert box['y']>=114 and box['y']+box['height']<=844-34+1,box
  await page.locator('[data-help-action="resume"]').click()
  await page.screenshot(path=str(OUT/(name+'-native-portrait.png')),timeout=10000)
  await page.locator('#playerRotate').click();await expect(page.locator('#playerRotate')).to_have_attribute('aria-pressed','true')
  await expect(button).to_have_attribute('aria-pressed','true')
  result['checks'].extend(['safe59_content0_reserves_native_control_row','tutorial_respects_safe_area','44px_six_controls_fit','fullscreen_does_not_rotate','rotation_does_not_exit_fullscreen'])
  await page.set_viewport_size({'width':844,'height':390})
  await page.evaluate('Telegram.WebApp.safeAreaInset={top:0,bottom:0,left:24,right:24};Telegram.WebApp.contentSafeAreaInset={top:54,bottom:0,left:0,right:0};__tgHandlers.contentSafeAreaChanged()')
  result['landscape_provided_insets']=await geometry(page,54)
  assert result['landscape_provided_insets']['header']['y']==54
  await page.evaluate('Telegram.WebApp.contentSafeAreaInset=undefined;__tgHandlers.contentSafeAreaChanged()')
  result['landscape']=await geometry(page,56)
  assert result['landscape']['header']['y']==56
  await expect(page.locator('.player-stage')).not_to_have_class('is-rotated')
  await page.screenshot(path=str(OUT/(name+'-native-landscape.png')),timeout=10000)
  await page.set_viewport_size({'width':320,'height':740})
  await page.evaluate('Telegram.WebApp.safeAreaInset=undefined;__tgHandlers.safeAreaChanged()')
  result['missing_insets_320']=await geometry(page,96)
  await expect(page.locator('.player-stage')).to_have_class('player-stage is-rotated')
  result['checks'].extend(['resize_recomputes_real_game_viewport','missing_and_zero_content_insets_safe','explicit_rotation_returns_after_portrait_resize'])
  await button.click()
  await expect(button).to_have_attribute('aria-pressed','true');await expect(button).to_have_attribute('aria-busy','true')
  await page.evaluate('__confirmFullscreen(false)');await expect(button).to_have_attribute('aria-pressed','false')
  await button.click();await page.evaluate('__confirmFullscreen(true)');await expect(button).to_have_attribute('aria-pressed','true')
  await page.evaluate("__fullscreenMode='sync'")
  await page.locator('#playerBack').click();await expect(page.locator('#player')).to_be_hidden()
  assert not await page.evaluate('Telegram.WebApp.isFullscreen')
  assert not await page.evaluate("document.body.classList.contains('is-player-fullscreen')")
  # Once exit is confirmed, a later native fullscreen action at home is allowed.
  await page.evaluate('__confirmFullscreen(true)')
  assert await page.evaluate('Telegram.WebApp.isFullscreen')
  await page.evaluate("__confirmFullscreen(false);__fullscreenMode='async'")
  await page.locator('#featuredRail [data-game="snake"]').click()
  await page.locator('[data-help-action="cancel"]').click()
  await page.evaluate("__fullscreenMode='sync';__confirmFullscreen(true)")
  assert not await page.evaluate('Telegram.WebApp.isFullscreen')
  await page.evaluate('__confirmFullscreen(true)')
  assert await page.evaluate('Telegram.WebApp.isFullscreen')
  await page.evaluate('__confirmFullscreen(false)')
  result['checks'].extend(['exit_waits_for_confirmation','reenter_confirmed','close_exits_and_clears_layout','late_cancelled_enter_exits_once','native_fullscreen_at_home_is_not_permanently_cancelled','positive_landscape_inset_has_no96px_floor'])
  assert not errors,errors
  result.update(passed=True,errors=errors,fullscreen_calls=await page.evaluate('__fullscreenCalls'))
  return result
 finally:await context.close()


async def sdk_failure(browser,name):
 context,page,errors,_=await setup(browser)
 try:
  button=page.locator('#playerFullscreen')
  await page.evaluate("__confirmFullscreen(true);__fullscreenMode='sync'")
  await button.click();await expect(button).to_have_attribute('aria-pressed','false')
  await page.evaluate("__fullscreenMode='async'")
  await button.click();await page.evaluate("__failFullscreen('UNSUPPORTED')")
  await expect(button).to_have_attribute('aria-pressed','false');await expect(button).to_be_enabled()
  await expect(page.locator('#playerFullscreenStatus')).to_be_visible()
  await expect(page.locator('#playerFullscreenMessage')).to_contain_text('não está disponível')
  await page.evaluate("() => {window.__browserAttempts=0;document.documentElement.requestFullscreen=()=>{__browserAttempts++;return Promise.reject(new DOMException('Synthetic denied','NotAllowedError'))};}")
  await page.locator('#playerFullscreenRetry').click()
  await expect(page.locator('#player')).to_have_attribute('data-fullscreen-error','NOT_ALLOWED')
  await expect(button).to_have_attribute('aria-pressed','false');await expect(button).to_be_enabled()
  await page.locator('#playerFullscreenRetry').click()
  await expect(page.locator('#player')).to_have_attribute('data-fullscreen-error','NOT_ALLOWED')
  assert await page.evaluate('__browserAttempts')==2
  assert not errors,errors
  return {'scenario':'sdk_failure_browser_rejection_retry','passed':True,'checks':['native_failure_keeps_false_state','native_failure_is_visible','fallback_only_after_new_user_tap','browser_rejection_is_reported','retry_remains_available'],'errors':errors}
 finally:await context.close()


async def sdk_old(browser,name):
 sdk=SDK+"Telegram.WebApp.version='7.10';document.documentElement.requestFullscreen=undefined;document.documentElement.webkitRequestFullscreen=undefined;"
 context,page,errors,_=await setup(browser,sdk=sdk)
 try:
  button=page.locator('#playerFullscreen')
  assert not await page.evaluate('__fullscreenCalls.length')
  await button.click()
  await expect(page.locator('#player')).to_have_attribute('data-fullscreen-error','NOT_SUPPORTED')
  await expect(button).to_have_attribute('aria-pressed','false');await expect(button).to_be_enabled()
  await expect(page.locator('#playerFullscreenStatus')).to_be_visible()
  assert not await page.evaluate('__fullscreenCalls.length')
  assert not errors,errors
  return {'scenario':'unsupported_old_sdk','passed':True,'checks':['version8_guard','unsupported_does_not_fake_active_state','unsupported_is_explained','unsupported_keeps_game_available'],'errors':errors}
 finally:await context.close()


async def browser_actual(browser,name):
 context,page,errors,requests=await setup(browser,sdk=None)
 try:
  button=page.locator('#playerFullscreen')
  supported=await page.evaluate("Boolean(document.fullscreenEnabled&&document.documentElement.requestFullscreen)")
  if not supported:
   await button.click();await expect(button).to_have_attribute('aria-pressed','false')
   await expect(page.locator('#playerFullscreenStatus')).to_be_visible()
   return {'scenario':'actual_browser_fullscreen','passed':True,'browser_api_supported':False,'actual_fullscreen_verified':False,'capability_note':'This engine does not expose the browser fullscreen API; its visible unsupported path was checked.','checks':['browser_unsupported_is_honest'],'errors':errors}
  await button.click();await page.wait_for_function('document.fullscreenElement===document.documentElement')
  await expect(button).to_have_attribute('aria-pressed','true')
  await expect(page.locator('#playerRotate')).to_have_attribute('aria-pressed','false')
  first=await geometry(page,0)
  await page.locator('#playerHelp').click();await expect(page.locator('#helpDialog')).to_be_visible()
  await page.locator('[data-help-action="resume"]').click()
  await page.screenshot(path=str(OUT/(name+'-actual-browser-fullscreen.png')),timeout=10000)
  await button.click();await page.wait_for_function('!document.fullscreenElement')
  await expect(button).to_have_attribute('aria-pressed','false')
  await button.click();await page.wait_for_function('document.fullscreenElement===document.documentElement')
  await page.locator('#playerBack').click();await page.wait_for_function('!document.fullscreenElement')
  assert not requests and not errors,(requests,errors)
  return {'scenario':'actual_browser_fullscreen','passed':True,'browser_api_supported':True,'actual_fullscreen_verified':True,'geometry':first,'checks':['real_user_click_enters_browser_fullscreen','actual_fullscreen_element_confirmed','real_browser_fullscreen_does_not_rotate','dialog_remains_in_fullscreen_tree','real_exit_reentry_and_close','no_guest_ranking_requests'],'errors':errors}
 finally:await context.close()


async def sdk_timeout(browser,name):
 context,page,errors,_=await setup(browser)
 try:
  await page.wait_for_function("document.getElementById('player').dataset.fullscreenError==='TIMEOUT'",timeout=10000)
  await expect(page.locator('#playerFullscreen')).to_have_attribute('aria-pressed','false')
  await expect(page.locator('#playerFullscreen')).to_be_enabled()
  await page.locator('#playerBack').click()
  await page.evaluate("__fullscreenMode='sync';__confirmFullscreen(true)")
  assert not await page.evaluate('Telegram.WebApp.isFullscreen')
  await page.evaluate('__confirmFullscreen(true)')
  assert await page.evaluate('Telegram.WebApp.isFullscreen')
  assert not errors,errors
  return {'scenario':'sdk_timeout_then_late_confirmation','passed':True,'checks':['timeout_does_not_fake_active_state','timeout_releases_button_for_retry','close_cancels_even_timed_out_entry','late_entry_exits_once','native_home_fullscreen_is_allowed_after_cleanup'],'errors':errors}
 finally:await context.close()


async def main():
 OUT.mkdir(parents=True,exist_ok=True);results=[]
 files=['web/app.js','web/index.html','web/styles.css','tests/e2e_portal.py','tests/e2e_fullscreen.py']
 hashes=lambda:{file:sha256((ROOT/file).read_bytes()).hexdigest() for file in files}
 before=hashes()
 engines=os.getenv('TEST_BROWSERS','chromium,firefox,webkit').split(',')
 async with async_playwright() as p:
  for name in engines:
   browser=None
   try:
    browser=await getattr(p,name).launch(headless=True)
    for scenario in [sdk_async,sdk_failure,sdk_old,browser_actual,sdk_timeout]:
     try:result=await scenario(browser,name)
     except Exception as error:result={'scenario':scenario.__name__,'passed':False,'error':str(error),'traceback':traceback.format_exc()}
     result['browser']=name;result['browser_version']=browser.version;results.append(result)
     print(json.dumps(result,ensure_ascii=False),flush=True)
     (OUT/'partial.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
   except Exception as error:
    results.extend({'browser':name,'scenario':scenario,'passed':False,'status':'blocked','error':str(error)} for scenario in ['sdk_async','sdk_failure','sdk_old','browser_actual','sdk_timeout'])
   finally:
    if browser:await browser.close()
 report={'passed':len(results)==len(engines)*5 and all(r['passed'] for r in results),'prepared':len(engines)*5,'executed':sum(r.get('status')!='blocked' for r in results),'results':results,'hashes_before':before,'hashes_after':hashes(),'scope':'Controlled Telegram SDK events plus actual browser API. No physical Telegram/iOS/Android validation. Session/run calls intercepted, game iframe synthetic, catalog and portal assets real.','documentation':'https://core.telegram.org/bots/webapps#initializing-mini-apps'}
 report['hashes_unchanged']=report['hashes_before']==report['hashes_after'];report['passed']=report['passed'] and report['hashes_unchanged']
 report['failed']=sum(not r['passed'] and r.get('status')!='blocked' for r in results);report['blocked']=sum(r.get('status')=='blocked' for r in results)
 report['playwright_version']=importlib.metadata.version('playwright')
 (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:report[k] for k in ['passed','prepared','executed','hashes_unchanged']},ensure_ascii=False),flush=True)
 return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
