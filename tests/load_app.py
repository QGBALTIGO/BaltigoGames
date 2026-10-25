"""Loopback-only synthetic load fixture. Never used by production entry points."""
import os
import statistics
import time
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager

if os.getenv("BALTIGO_LOAD_TEST") != "1":
    raise RuntimeError("This fixture requires an explicit isolated load-test environment")
if os.getenv("BOT_TOKEN"):
    raise RuntimeError("Production Telegram credentials must not be present in load tests")

from fastapi import FastAPI
from app import main
from app import leaderboard

timings = defaultdict(list)


class MeasuredStore(leaderboard.LeaderboardStore):
    def _commit_batch(self, db):
        began = time.perf_counter()
        try:
            return super()._commit_batch(db)
        finally:
            timings['writer_commit_ms'].append((time.perf_counter()-began)*1000)



leaderboard.LeaderboardStore = MeasuredStore

TEST_TOKEN = "1200:synthetic-isolated-capacity-test"
async def loop_probe():
    while True:
        began=time.perf_counter()
        await asyncio.sleep(.05)
        timings['event_loop_lag_ms'].append(max(0,(time.perf_counter()-began-.05)*1000))


@asynccontextmanager
async def profiling_lifespan(_):
    task=asyncio.create_task(loop_probe())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=profiling_lifespan)
synthetic_router=leaderboard.create_leaderboard_router(main.load_catalog, TEST_TOKEN)
writer = synthetic_router.leaderboard_writer
# Observation only: no replacement of the queue, worker, clock or transactions.
writer.observe = lambda name, value: timings[name].append(value)
app.include_router(synthetic_router)


@app.middleware('http')
async def request_duration(request,call_next):
    began=time.perf_counter()
    response=await call_next(request)
    elapsed=(time.perf_counter()-began)*1000
    path=request.url.path
    if path.startswith('/api/'):
        kind=path.rsplit('/',1)[-1] if '/runs/' in path else path.replace('/api/','')
        timings['asgi_'+kind+'_ms'].append(elapsed)
        response.headers['X-Load-Elapsed-Ms']=str(round(elapsed,3))
    return response


@app.get('/__load_metrics')
def load_metrics():
    result = {}
    for name, values in list(timings.items()):
        ordered = sorted(values)
        result[name] = {'count': len(values), 'mean':statistics.mean(ordered),'sum':sum(ordered),'median':statistics.median(ordered), 'p95':ordered[int((len(ordered)-1)*.95)], 'p99':ordered[int((len(ordered)-1)*.99)], 'max':max(ordered)}
    return {'timings':result, 'writer':writer.snapshot()}


app.mount("/", main.app)
