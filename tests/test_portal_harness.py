"""Fault injection for the browser-test lifecycle; no browser/network is used."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def harness():
    source=Path(__file__).with_name('e2e_portal.py')
    spec=importlib.util.spec_from_file_location('portal_harness_under_test',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeLocator:
    @property
    def first(self):return self
    async def count(self):return 1
    async def is_hidden(self):return True
    async def click(self):raise TimeoutError('PRIMARY NAVIGATION TIMEOUT')


class FakePage:
    def __init__(self,stalled_capture=False):
        self.default_timeout=None
        self.stalled_capture=stalled_capture
        self.screenshot_timeout=None
    def set_default_timeout(self,value):self.default_timeout=value
    def on(self,*args):pass
    async def route(self,*args):pass
    async def add_init_script(self,*args):pass
    async def goto(self,*args,**kwargs):pass
    def locator(self,*args):return FakeLocator()
    async def evaluate(self,*args):return False
    async def screenshot(self,**kwargs):
        self.screenshot_timeout=kwargs.get('timeout')
        if self.stalled_capture:await asyncio.Future()
        raise RuntimeError('DIAGNOSTIC SCREENSHOT FAILED')


class FakeContext:
    def __init__(self,page,close_error=False):
        self.page=page;self.close_error=close_error;self.close_calls=0
    async def new_page(self):return self.page
    async def close(self):
        self.close_calls+=1
        if self.close_error:raise RuntimeError('CONTEXT CLEANUP FAILED')


class FakeBrowser:
    def __init__(self,context=None):
        self.context=context;self.contexts=[];self.connected=True;self.close_calls=0
    async def new_context(self,**kwargs):
        self.contexts.append(self.context);return self.context
    def is_connected(self):return self.connected
    async def close(self):self.close_calls+=1


@pytest.mark.asyncio
@pytest.mark.parametrize('stalled_capture',[False,True])
@pytest.mark.parametrize('close_error',[False,True])
async def test_original_viewport_failure_survives_capture_and_cleanup_faults(harness,monkeypatch,stalled_capture,close_error):
    async def visible():pass
    monkeypatch.setattr(harness,'expect',lambda locator:SimpleNamespace(to_be_visible=visible))
    monkeypatch.setattr(harness,'DIAGNOSTIC_TIMEOUT_SECONDS',.01)
    page=FakePage(stalled_capture);context=FakeContext(page,close_error);browser=FakeBrowser(context)
    result=await harness.run_viewport(browser,'webkit',360,740)
    assert result['passed'] is False
    assert result['viewport']=='360x740' and result['browser']=='webkit'
    assert result['error']=='PRIMARY NAVIGATION TIMEOUT'
    assert result['checks']==['catalog_loaded','no_unsolicited_modal','no_horizontal_overflow']
    assert 'screenshot_error' in result
    assert context.close_calls==1
    assert bool(result.get('cleanup_errors'))==close_error
    assert page.default_timeout==10000 and page.screenshot_timeout==10000


@pytest.mark.asyncio
async def test_engine_continues_after_failed_scenario_and_closes_browser(harness,monkeypatch):
    browser=FakeBrowser();calls=[]
    async def launch(**kwargs):return browser
    async def failed(*args):calls.append('failed');raise ValueError('SCENARIO FAILURE')
    async def passed(*args):calls.append('passed');return {'passed':True,'checks':['real assertion placeholder']}
    plan=[({'browser':'webkit','viewport':'360x740'},failed,()),({'browser':'webkit','viewport':'390x844'},passed,())]
    monkeypatch.setattr(harness,'scenario_plan',lambda name:plan)
    results,infrastructure=await harness.run_engine(SimpleNamespace(launch=launch),'webkit')
    summary=harness.summarize(results,len(plan),infrastructure)
    assert calls==['failed','passed'] and browser.close_calls==1
    assert summary['prepared']==summary['executed']==2
    assert summary['failed']==1 and summary['passed_scenarios']==1 and summary['blocked']==0
    assert summary['passed'] is False and not infrastructure


@pytest.mark.asyncio
async def test_disconnected_browser_blocks_only_unstarted_scenarios(harness,monkeypatch):
    browser=FakeBrowser()
    async def launch(**kwargs):return browser
    async def first(*args):browser.connected=False;return {'passed':False,'checks':[],'error':'BROWSER DISCONNECTED'}
    async def unstarted(*args):raise AssertionError('Blocked scenario must never run')
    plan=[({'browser':'webkit','viewport':'360x740'},first,()),({'browser':'webkit','viewport':'390x844'},unstarted,())]
    monkeypatch.setattr(harness,'scenario_plan',lambda name:plan)
    results,infrastructure=await harness.run_engine(SimpleNamespace(launch=launch),'webkit')
    summary=harness.summarize(results,2,infrastructure)
    assert summary['prepared']==2 and summary['executed']==1
    assert summary['failed']==1 and summary['blocked']==1
    assert results[1]['status']=='blocked' and results[1]['passed'] is False
    assert browser.close_calls==1


@pytest.mark.asyncio
async def test_failed_context_cleanup_blocks_contaminated_following_scenarios(harness,monkeypatch):
    browser=FakeBrowser()
    async def launch(**kwargs):return browser
    async def first(*args):return {'passed':False,'checks':[],'error':'PRIMARY FAILURE','cleanup_errors':['CONTEXT CLOSE FAILED']}
    async def unstarted(*args):raise AssertionError('Unisolated scenario must never run')
    plan=[({'browser':'webkit','viewport':'360x740'},first,()),({'browser':'webkit','viewport':'390x844'},unstarted,())]
    monkeypatch.setattr(harness,'scenario_plan',lambda name:plan)
    results,infrastructure=await harness.run_engine(SimpleNamespace(launch=launch),'webkit')
    summary=harness.summarize(results,2,infrastructure)
    assert summary['executed']==summary['failed']==summary['blocked']==1
    assert summary['prepared']==2 and summary['passed'] is False
    assert 'isolation' in results[1]['error'] and browser.close_calls==1


@pytest.mark.asyncio
async def test_browser_launch_failure_records_all_prepared_scenarios_blocked(harness):
    async def launch(**kwargs):raise RuntimeError('BROWSER COULD NOT LAUNCH')
    results,infrastructure=await harness.run_engine(SimpleNamespace(launch=launch),'webkit')
    summary=harness.summarize(results,len(harness.scenario_plan('webkit')),infrastructure)
    assert summary['prepared']==summary['blocked']==6
    assert summary['executed']==summary['failed']==summary['passed_scenarios']==0
    assert summary['passed'] is False


@pytest.mark.asyncio
async def test_browser_close_fault_is_a_separate_infrastructure_failure(harness,monkeypatch):
    browser=FakeBrowser()
    async def launch(**kwargs):return browser
    async def passed(*args):return {'passed':True,'checks':['completed']}
    async def close():browser.close_calls+=1;raise RuntimeError('BROWSER CLOSE FAILED')
    browser.close=close
    monkeypatch.setattr(harness,'scenario_plan',lambda name:[({'browser':'webkit','viewport':'360x740'},passed,())])
    results,infrastructure=await harness.run_engine(SimpleNamespace(launch=launch),'webkit')
    summary=harness.summarize(results,1,infrastructure)
    assert results[0]['status']=='passed' and summary['passed'] is False
    assert summary['executed']==1 and summary['failed']==summary['blocked']==0
    assert infrastructure[0]['operation']=='browser.close' and browser.close_calls==1


def test_original_twenty_scenarios_remain_prepared(harness):
    assert sum(len(harness.scenario_plan(name)) for name in ['chromium','firefox','webkit'])==20
