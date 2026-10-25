"""Exercise isolated signed sessions and active runs; never targets public hosts."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import hmac
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode, urlparse
import httpx

TEST_TOKEN = "1200:synthetic-isolated-capacity-test"


def init_data(index):
    fields = {'auth_date': str(int(time.time())), 'user': json.dumps({'id': 9_000_000_000 + index, 'first_name': f'Teste {index}'})}
    secret = hmac.new(b'WebAppData', TEST_TOKEN.encode(), hashlib.sha256).digest()
    check = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
    fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def percentile(values, value):
    if not values:
        return None
    return round(sorted(values)[min(len(values)-1, math.ceil(len(values)*value)-1)] * 1000, 2)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8058')
    parser.add_argument('--users', type=int, default=1200)
    parser.add_argument('--ramp', type=float, default=60)
    parser.add_argument('--hold', type=float, default=180)
    parser.add_argument('--finish-window', type=float, default=30)
    parser.add_argument('--asset-manifest')
    parser.add_argument('--output', default='artifacts/capacity')
    args = parser.parse_args()
    parsed = urlparse(args.base)
    if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise SystemExit('Use an isolated loopback fixture, never a public service')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    profiles = json.loads(Path(args.asset_manifest).read_text()) if args.asset_manifest else []
    times = defaultdict(list)
    errors = []
    statuses = Counter()
    active = completed = bytes_received = 0
    peak_active = 0
    active_history = []
    started = time.monotonic()
    stop_at = started + args.ramp + args.hold
    limits = httpx.Limits(max_connections=max(100, args.users+20), max_keepalive_connections=max(100, args.users+20))
    async with httpx.AsyncClient(base_url=args.base, timeout=15, limits=limits, follow_redirects=True) as client:
        async def request(category, method, path, **kwargs):
            nonlocal bytes_received
            began = time.monotonic()
            try:
                response = await client.request(method, path, **kwargs)
                elapsed = time.monotonic()-began
                times[category].append(elapsed)
                statuses[str(response.status_code)] += 1
                bytes_received += len(response.content)
                if response.status_code != 200:
                    errors.append({'category': category, 'status': response.status_code, 'at': round(time.monotonic()-started, 2)})
                    return None
                return response
            except Exception as exc:
                times[category].append(time.monotonic()-began)
                errors.append({'category': category, 'error': type(exc).__name__, 'at': round(time.monotonic()-started, 2)})
                return None

        async def user(index):
            nonlocal active, completed, peak_active
            await asyncio.sleep(max(0, started + index * args.ramp / args.users - time.monotonic()))
            opened = time.monotonic()
            session = await request('session', 'POST', '/api/session', json={'init_data': init_data(index)})
            if session is None:
                return
            headers = {'Authorization': 'Bearer ' + session.json()['token']}
            if profiles:
                profile = profiles[index % len(profiles)]
                await asyncio.gather(*(request('opening-assets', 'GET', path) for path in profile['paths']))
                slug = profile['slug']
            else:
                await request('opening-assets', 'GET', '/api/catalog?v=load-test')
                slug = 'snake'
            times['opening-http'].append(time.monotonic()-opened)
            run = await request('start', 'POST', '/api/runs', json={'game_slug': slug}, headers=headers)
            if run is None:
                return
            run_id = run.json()['run_id']
            active += 1
            peak_active = max(peak_active, active)
            # Stagger the first heartbeat so all users remain simultaneously
            # active without turning the steady profile into an artificial burst.
            next_heartbeat = time.monotonic() + 8 + index % 20 / 10
            while next_heartbeat < stop_at:
                await asyncio.sleep(max(0, next_heartbeat-time.monotonic()))
                await request('heartbeat', 'POST', f'/api/runs/{run_id}/heartbeat', json={'active': True}, headers=headers)
                next_heartbeat += 10
            await asyncio.sleep(max(0, stop_at + index * args.finish_window / args.users - time.monotonic()))
            finish = await request('finish', 'POST', f'/api/runs/{run_id}/finish', json={'outcome': 'ended', 'score': index}, headers=headers)
            if finish is not None:
                data = finish.json()
                if not 1 <= data.get('points', -1) <= 10:
                    errors.append({'category': 'points', 'points': data.get('points')})
                completed += 1
            active -= 1

        async def monitor():
            while completed < args.users and time.monotonic()-started < args.ramp+args.hold+args.finish_window+30:
                active_history.append({'seconds': round(time.monotonic()-started, 1), 'active': active, 'completed': completed})
                print(json.dumps({'active': active, 'completed': completed, 'errors': len(errors), 'seconds': round(time.monotonic()-started)}, ensure_ascii=True), flush=True)
                await asyncio.sleep(10)

        monitor_task = asyncio.create_task(monitor())
        await asyncio.gather(*(user(index) for index in range(args.users)))
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)
        leaderboard = await request('ranking', 'GET', '/api/leaderboard')
        ranking = leaderboard.json() if leaderboard else {}
    metrics = {key: {'requests': len(values), 'p50_ms': percentile(values, .5), 'p95_ms': percentile(values, .95), 'p99_ms': percentile(values, .99), 'max_ms': round(max(values)*1000, 2)} for key, values in times.items() if values}
    criteria = {'all_users_completed': completed == args.users, 'concurrent_users_reached': peak_active == args.users, 'no_request_errors': not errors, 'heartbeat_p95_below_500ms': bool(times['heartbeat']) and percentile(times['heartbeat'], .95) < 500, 'heartbeat_p99_below_1500ms': bool(times['heartbeat']) and percentile(times['heartbeat'], .99) < 1500, 'opening_http_p95_below_2500ms': bool(times['opening-http']) and percentile(times['opening-http'], .95) < 2500}
    result = {'qualified': all(criteria.values()), 'criteria': criteria, 'users': args.users, 'peak_active': peak_active, 'completed': completed, 'ramp_seconds': args.ramp, 'steady_hold_seconds': args.hold, 'finish_window_seconds': args.finish_window, 'duration_seconds': round(time.monotonic()-started, 2), 'metrics': metrics, 'statuses': dict(statuses), 'bytes_received': bytes_received, 'errors': errors[:100], 'error_count': len(errors), 'activity': active_history, 'ranking_entries_returned': len(ranking.get('entries', [])), 'scope': 'Synthetic signed identities, real HTTP/SQLite persistence and assets on isolated loopback; no Telegram polling, real payments, 1200 physical browsers, public Internet bandwidth or phone graphics claim'}
    (out/'report.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'activity','errors'}}, ensure_ascii=True), flush=True)
    if not result['qualified']:
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
