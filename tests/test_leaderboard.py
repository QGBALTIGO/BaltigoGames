import hashlib
import hmac
import json
import sqlite3
import asyncio
import contextvars
import threading
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.leaderboard import (
    DAILY_POINTS_CAP,
    INIT_DATA_MAX_AGE,
    SESSION_SECONDS,
    FinishBody,
    DurableWriteQueue,
    LeaderboardStore,
    clean_display_name,
    create_leaderboard_router,
)


TEST_TOKEN = "123456:synthetic-test-credential"
CATALOG = {"games": [{"slug": "snake"}, {"slug": "tetris"}]}


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def signed_data(clock, user_id=123, **overrides):
    fields = {
        "auth_date": str(int(clock())),
        "query_id": "synthetic-query",
        "user": json.dumps({"id": user_id, "first_name": "João", "username": "private_handle"}, ensure_ascii=False),
    }
    fields.update(overrides)
    secret = hmac.new(b"WebAppData", TEST_TOKEN.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.fixture
def setup_api(tmp_path):
    clock = Clock()
    database_path = tmp_path / "private" / "ranking.sqlite"
    writers = []

    def make_app():
        app = FastAPI()
        router = create_leaderboard_router(lambda: CATALOG, TEST_TOKEN, database_path, clock=clock)
        writers.append(router.leaderboard_writer)
        app.include_router(router)
        return app

    client = TestClient(make_app())
    yield client, clock, database_path, make_app
    for writer in writers:
        writer.close()
        writer.store.close()


@pytest.fixture
def make_writer(tmp_path):
    writers = []

    def create(**options):
        store = LeaderboardStore(tmp_path / f"batch-{len(writers)}.sqlite")
        writer = DurableWriteQueue(store, **options)
        writers.append(writer)
        return writer, store

    yield create
    for writer in writers:
        writer.close()
        writer.store.close()


def authenticate(client, clock, user_id=123, **kwargs):
    response = client.post("/api/session", json={"init_data": signed_data(clock, user_id), **kwargs})
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()
    return {"Authorization": f"Bearer {data['token']}"}, data


def start(client, headers, slug="snake"):
    response = client.post("/api/runs", json={"game_slug": slug}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["run_id"]


def round_play(client, clock, headers, slug="snake", seconds=20, score=500):
    run_id = start(client, headers, slug)
    for _ in range(seconds // 10):
        clock.advance(10)
        response = client.post(f"/api/runs/{run_id}/heartbeat", json={"active": True}, headers=headers)
        assert response.status_code == 200, response.text
    clock.advance(seconds % 10)
    response = client.post(f"/api/runs/{run_id}/finish", json={"score": score, "outcome": "completed"}, headers=headers)
    assert response.status_code == 200, response.text
    return run_id, response.json()


def test_guest_can_browse_real_empty_ranking_but_cannot_write(setup_api):
    client, _, _, _ = setup_api
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert data["entries"] == [] and data["me"] is None
    assert data["verified"] is False and data["metric"] == "activity"
    assert "navegador" in data["trust_policy"]
    assert response.headers["Cache-Control"] == "no-store"
    assert client.post("/api/runs", json={"game_slug": "snake"}).status_code == 401


def test_signed_identity_session_opaque_id_and_private_token_storage(setup_api):
    client, clock, path, _ = setup_api
    headers, session = authenticate(client, clock, display_name="<b>Ágata</b> 🎮\u202e")
    assert session["guest"] is False
    assert session["user"]["display_name"] == "Ágata"
    assert session["user"]["id"] != "123"
    assert session["expires_at"] == clock() + SESSION_SECONDS
    with sqlite3.connect(path) as db:
        stored = db.execute("SELECT token_hash FROM ranking_sessions").fetchone()[0]
    assert stored == hashlib.sha256(session["token"].encode()).hexdigest()
    assert session["token"] != stored
    assert client.get("/api/leaderboard", headers=headers).json()["me"]["rank"] is None


@pytest.mark.parametrize("change", ["bad_signature", "expired", "future", "duplicate", "missing_user", "invalid_user", "boolean_id", "bot_user"])
def test_telegram_authentication_rejects_invalid_data(setup_api, change):
    client, clock, _, _ = setup_api
    if change == "bad_signature":
        data = signed_data(clock).replace("Jo%C3%A3o", "Maria")
    elif change == "expired":
        data = signed_data(clock, auth_date=str(int(clock() - INIT_DATA_MAX_AGE - 1)))
    elif change == "future":
        data = signed_data(clock, auth_date=str(int(clock() + 31)))
    elif change == "duplicate":
        data = signed_data(clock) + "&auth_date=1800000000"
    elif change == "missing_user":
        data = signed_data(clock, user="")
    elif change == "invalid_user":
        data = signed_data(clock, user="[]")
    elif change == "boolean_id":
        data = signed_data(clock, user=json.dumps({"id": True}))
    else:
        data = signed_data(clock, user=json.dumps({"id": 123, "is_bot": True}))
    assert client.post("/api/session", json={"init_data": data}).status_code == 401


def test_auth_does_not_accept_init_data_unsafe(setup_api):
    client, clock, _, _ = setup_api
    response = client.post("/api/session", json={"init_data": signed_data(clock), "initDataUnsafe": {"user": {"id": 42}}})
    assert response.status_code == 422


@pytest.mark.parametrize("header", ["Bearer " + "a" * 43, "Basic " + "a" * 43, "Bearer short"])
def test_unknown_or_malformed_tokens_are_rejected_even_for_public_me_query(setup_api, header):
    client, _, _, _ = setup_api
    assert client.get("/api/leaderboard", headers={"Authorization": header}).status_code == 401


def test_sessions_expire_and_cannot_complete_pending_rounds(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    clock.advance(SESSION_SECONDS + 1)
    assert client.post(f"/api/runs/{run_id}/finish", json={}, headers=headers).status_code == 401


def test_activity_ranks_persist_and_browser_score_does_not_multiply_points(setup_api):
    client, clock, _, make_app = setup_api
    first, _ = authenticate(client, clock, 1001)
    second, _ = authenticate(client, clock, 1002, display_name="Ana")
    _, small = round_play(client, clock, first, seconds=20, score=1_000_000_000)
    _, larger = round_play(client, clock, second, seconds=30, score=1)
    assert small["points"] == 1 and larger["points"] == 2
    result = TestClient(make_app()).get("/api/leaderboard", headers=first).json()
    assert result["entries"][0]["display_name"] == "Ana"
    assert result["me"]["rank"] == 2
    assert result["entries"][0]["points"] == 2
    assert all(set(entry) == {"rank", "display_name", "points", "games_played", "is_me"} for entry in result["entries"])
    assert "private_handle" not in json.dumps(result)
    assert "telegram_id" not in json.dumps(result)
    assert result["verified"] is False


def test_game_rankings_are_isolated_and_unknown_games_cannot_start(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    round_play(client, clock, headers, "snake")
    assert client.get("/api/leaderboard?game=tetris").json()["entries"] == []
    assert client.get("/api/leaderboard?game=snake").json()["entries"][0]["games_played"] == 1
    assert client.get("/api/leaderboard?game=unknown").status_code == 404
    assert client.post("/api/runs", json={"game_slug": "unknown"}, headers=headers).status_code == 404
    assert client.get("/api/leaderboard?scope=game").status_code == 422
    assert client.get("/api/leaderboard?period=forever").status_code == 422


def test_period_filters_apply_to_both_public_entries_and_me(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    round_play(client, clock, headers)
    clock.advance(8 * 86400)
    headers, _ = authenticate(client, clock)
    assert client.get("/api/leaderboard?period=week", headers=headers).json()["me"]["points"] == 0
    assert client.get("/api/leaderboard?period=month").json()["entries"][0]["points"] == 1
    clock.advance(23 * 86400)
    assert client.get("/api/leaderboard?period=month").json()["entries"] == []
    assert client.get("/api/leaderboard?period=all").json()["entries"][0]["points"] == 1


def test_round_ownership_enforced_for_heartbeat_and_completion(setup_api):
    client, clock, _, _ = setup_api
    owner, _ = authenticate(client, clock, 1001)
    other, _ = authenticate(client, clock, 1002)
    run_id = start(client, owner)
    assert client.post(f"/api/runs/{run_id}/heartbeat", json={}, headers=other).status_code == 404
    assert client.post(f"/api/runs/{run_id}/finish", json={}, headers=other).status_code == 404


def test_one_active_round_reuses_same_game_and_abandons_previous_game(setup_api):
    client, clock, path, _ = setup_api
    headers, _ = authenticate(client, clock)
    first = start(client, headers)
    assert start(client, headers) == first
    second = start(client, headers, "tetris")
    assert second != first
    result = client.post(f"/api/runs/{first}/finish", json={}, headers=headers).json()
    assert result["accepted"] is False and result["points"] == 0
    assert client.post(f"/api/runs/{first}/heartbeat", json={}, headers=headers).status_code == 409
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM ranking_runs WHERE status='active'").fetchone()[0] == 1


def test_fast_completion_cannot_earn_points_and_duplicate_retains_result(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    response = client.post(f"/api/runs/{run_id}/finish", json={"score": 9999999}, headers=headers).json()
    duplicate = client.post(f"/api/runs/{run_id}/finish", json={"score": 9999999}, headers=headers).json()
    assert response["accepted"] is False
    assert response["reason"] == "atividade_insuficiente"
    assert duplicate["accepted"] is False and duplicate["duplicate"] is True
    assert client.get("/api/leaderboard").json()["entries"] == []


def test_hidden_gap_does_not_count_and_pause_resume_preserves_active_time(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    clock.advance(10)
    client.post(f"/api/runs/{run_id}/heartbeat", json={"active": False}, headers=headers)
    clock.advance(100)
    client.post(f"/api/runs/{run_id}/heartbeat", json={"active": True}, headers=headers)
    clock.advance(10)
    response = client.post(f"/api/runs/{run_id}/finish", json={}, headers=headers).json()
    assert response["active_seconds"] == 20 and response["points"] == 1


def test_unreported_long_gap_and_claimed_duration_cannot_forge_activity(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    clock.advance(1000)
    response = client.post(f"/api/runs/{run_id}/finish", json={"duration_ms": 1000000}, headers=headers).json()
    assert response["points"] == 0 and response["active_seconds"] == 0


def test_expired_runs_do_not_earn_and_a_new_start_replaces_them(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    clock.advance(3601)
    assert client.post(f"/api/runs/{run_id}/heartbeat", json={}, headers=headers).status_code == 409
    response = client.post(f"/api/runs/{run_id}/finish", json={}, headers=headers).json()
    assert response["reason"] == "partida_expirada" and response["points"] == 0
    assert start(client, headers) != run_id


def test_round_and_daily_points_caps(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    for _ in range(DAILY_POINTS_CAP // 10):
        _, response = round_play(client, clock, headers, seconds=150)
        assert response["points"] == 10
    _, capped = round_play(client, clock, headers, seconds=150)
    assert capped["accepted"] is True and capped["points"] == 0
    assert capped["reason"] == "limite_diario"
    assert client.get("/api/leaderboard").json()["entries"][0]["points"] == DAILY_POINTS_CAP
    # Run cap remains 10 even with more server-timed activity on a fresh UTC day.
    clock.advance(86400)
    headers, _ = authenticate(client, clock)
    _, fresh = round_play(client, clock, headers, seconds=180)
    assert fresh["points"] == 10


def test_concurrent_finish_is_atomic_and_awards_exactly_once(setup_api):
    client, clock, path, _ = setup_api
    headers, session = authenticate(client, clock)
    run_id = start(client, headers)
    clock.advance(10)
    client.post(f"/api/runs/{run_id}/heartbeat", json={}, headers=headers)
    clock.advance(10)
    store = LeaderboardStore(path, clock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.finish(session["user"]["id"], run_id, FinishBody()), range(2)))
    assert sorted(result["duplicate"] for result in results) == [False, True]
    assert {result["points"] for result in results} == {1}
    assert client.get("/api/leaderboard").json()["entries"][0]["points"] == 1


def test_concurrent_http_finish_queues_without_duplicate_awards(setup_api):
    import asyncio
    import httpx
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    for _ in range(2):
        clock.advance(10)
        assert client.post(f'/api/runs/{run_id}/heartbeat', json={}, headers=headers).status_code == 200

    async def submit():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url='http://test') as concurrent:
            responses = await asyncio.gather(*(concurrent.post(f'/api/runs/{run_id}/finish', json={}, headers=headers) for _ in range(20)))
            assert all(response.status_code == 200 for response in responses)
            assert sum(not response.json()['duplicate'] for response in responses) == 1
            assert {response.json()['points'] for response in responses} == {1}
            ranking = await concurrent.get('/api/leaderboard', headers=headers)
            assert ranking.status_code == 200 and ranking.json()['me']['points'] == 1

    asyncio.run(submit())


@pytest.mark.parametrize("body", [{"score": -1}, {"score": 1_000_000_001}, {"score": "100"},
                                  {"score": True}, {"duration_ms": -1}, {"duration_ms": 3_600_001},
                                  {"duration_ms": True}, {"outcome": "invented"}, {"points": 999}])
def test_unbounded_or_unexpected_finish_fields_rejected(setup_api, body):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    assert client.post(f"/api/runs/{run_id}/finish", json=body, headers=headers).status_code == 422


@pytest.mark.parametrize("raw", ['{"score":NaN}', '{"score":Infinity}', '{"score":1e1000}', '{"duration_ms":Infinity}'])
def test_nonfinite_numeric_input_returns_validation_error_not_server_error(setup_api, raw):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    run_id = start(client, headers)
    response = client.post(f"/api/runs/{run_id}/finish", content=raw,
                           headers={**headers, "Content-Type": "application/json"})
    assert response.status_code == 422
    assert "inválidos" in response.json()["detail"]


def test_session_rate_limit_is_persistent_and_recovers_next_minute(setup_api):
    client, clock, _, make_app = setup_api
    for _ in range(10):
        assert client.post("/api/session", json={"init_data": "invalid"}).status_code == 401
    response = TestClient(make_app()).post("/api/session", json={"init_data": "invalid"})
    assert response.status_code == 429 and response.headers["Retry-After"] == "60"
    # Invalid traffic on a shared IP must not exclude a valid Telegram user.
    assert client.post("/api/session", json={"init_data": signed_data(clock)}).status_code == 200
    clock.advance(61)
    assert client.post("/api/session", json={"init_data": signed_data(clock)}).status_code == 200


def test_start_and_heartbeat_rate_limits(setup_api):
    client, clock, _, _ = setup_api
    headers, _ = authenticate(client, clock)
    for _ in range(20):
        run_id = start(client, headers)
    assert client.post("/api/runs", json={"game_slug": "snake"}, headers=headers).status_code == 429
    for _ in range(30):
        assert client.post(f"/api/runs/{run_id}/heartbeat", json={}, headers=headers).status_code == 200
    assert client.post(f"/api/runs/{run_id}/heartbeat", json={}, headers=headers).status_code == 429


def test_verified_users_sharing_an_ip_have_independent_budgets(setup_api):
    client, clock, _, _ = setup_api
    for user_id in range(2000, 2012):
        headers, _ = authenticate(client, clock, user_id=user_id)
        run_id = start(client, headers)
        for _ in range(16):
            assert client.post(f"/api/runs/{run_id}/heartbeat", json={"active": True}, headers=headers).status_code == 200


def test_request_transaction_retains_limits_but_rolls_back_failed_operation(tmp_path):
    from fastapi import HTTPException
    store = LeaderboardStore(tmp_path / 'transaction.sqlite')
    session = store.session({'id': 42, 'first_name': 'Original'}, None)
    with pytest.raises(HTTPException, match='controlled rejection'):
        with store.request_transaction():
            store.rate_limit('guard', 'synthetic', 1)
            with store.connection() as db:
                db.execute('UPDATE ranking_users SET display_name=? WHERE id=?', ('Partial', session['user']['id']))
                raise HTTPException(400, 'controlled rejection')
    with store.connection() as db:
        assert db.execute('SELECT display_name FROM ranking_users').fetchone()[0] == 'Original'
        assert db.execute('PRAGMA synchronous').fetchone()[0] == 2
    with pytest.raises(HTTPException) as rejected:
        store.rate_limit('guard', 'synthetic', 1)
    assert rejected.value.status_code == 429
    store.close()


def test_unexpected_request_error_rolls_back_all_changes(tmp_path):
    store = LeaderboardStore(tmp_path / 'unexpected.sqlite')
    with pytest.raises(RuntimeError):
        with store.request_transaction():
            store.rate_limit('guard', 'synthetic', 1)
            raise RuntimeError('unexpected failure')
    store.rate_limit('guard', 'synthetic', 1)
    store.close()


def test_concurrent_request_writers_do_not_compete_for_sqlite_lock(tmp_path, monkeypatch):
    import threading
    import time
    store = LeaderboardStore(tmp_path / 'queued-writers.sqlite')
    original_begin = store._begin_write
    ready = threading.Barrier(8)

    def no_busy_retries(db):
        db.execute('PRAGMA busy_timeout=0')
        original_begin(db)
        time.sleep(.01)

    monkeypatch.setattr(store, '_begin_write', no_busy_retries)

    def open_player(index):
        ready.wait(timeout=10)
        with store.request_transaction():
            store.rate_limit('synthetic-user', str(index), 1)
            session = store.session({'id': 1000 + index, 'first_name': 'Teste'}, None)
            return store.start_run(session['user']['id'], 'snake')['run_id']

    with ThreadPoolExecutor(max_workers=8) as pool:
        runs = list(pool.map(open_player, range(8)))
    assert len(set(runs)) == 8
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM ranking_users').fetchone()[0] == 8
        assert db.execute('SELECT count(*) FROM ranking_runs').fetchone()[0] == 8
        assert db.execute('PRAGMA synchronous').fetchone()[0] == 2
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    store.close()


def test_keepalive_actually_keeps_wal_registered_between_requests(tmp_path):
    path = tmp_path / 'kept-wal.sqlite'
    store = LeaderboardStore(path)
    store.rate_limit('probe', 'one', 10)
    assert path.with_name(path.name + '-wal').exists()
    store.rate_limit('probe', 'two', 10)
    assert path.with_name(path.name + '-wal').exists()
    with store.connection() as db:
        assert db.execute('PRAGMA synchronous').fetchone()[0] == 2
    store.close()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM ranking_limits').fetchone()[0] == 2
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_group_commit_is_full_and_never_acknowledges_before_commit(make_writer, monkeypatch):
    writer, store = make_writer(batch_size=8, batch_window=.03)
    entered = threading.Event()
    release = threading.Event()
    commits = []
    original_commit = store._commit_batch

    def blocked_commit(db):
        commits.append(db.execute('PRAGMA synchronous').fetchone()[0])
        entered.set()
        assert release.wait(5)
        original_commit(db)

    monkeypatch.setattr(store, '_commit_batch', blocked_commit)
    with writer._condition:
        futures = [writer.submit(lambda index=index: store.session({'id': 1000 + index}, None)) for index in range(8)]
    try:
        assert entered.wait(5)
        assert not any(future.done() for future in futures)
        with store.connection() as db:
            assert db.execute('SELECT count(*) FROM ranking_users').fetchone()[0] == 0
    finally:
        release.set()
    assert len({future.result(5)['user']['id'] for future in futures}) == 8
    assert commits == [2]
    writer.close()
    assert writer.snapshot()['batches'] == 1
    assert writer.snapshot()['peak_batch_size'] == 8
    with sqlite3.connect(store.path) as reopened:
        assert reopened.execute('SELECT count(*) FROM ranking_users').fetchone()[0] == 8
        assert reopened.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_group_commit_isolates_unexpected_failure_and_preserves_http_guards(make_writer):
    from fastapi import HTTPException
    writer, store = make_writer(batch_size=4, batch_window=.03)
    original = store.session({'id': 42, 'first_name': 'Original'}, None)

    def controlled_failure():
        store.rate_limit('controlled', 'one', 1)
        with store.connection() as db:
            db.execute('UPDATE ranking_users SET display_name=? WHERE id=?', ('Partial', original['user']['id']))
            raise HTTPException(400, 'controlled failure')

    def unexpected_failure():
        store.rate_limit('unexpected', 'one', 1)
        store.session({'id': 43}, None)
        raise RuntimeError('unexpected failure')

    callbacks = [lambda: store.session({'id': 44}, None), controlled_failure,
                 unexpected_failure, lambda: store.session({'id': 45}, None)]
    with writer._condition:
        futures = [writer.submit(callback) for callback in callbacks]
    assert futures[0].result(5)['user']['id']
    with pytest.raises(HTTPException) as rejected:
        futures[1].result(5)
    assert rejected.value.status_code == 400
    with pytest.raises(RuntimeError, match='unexpected failure'):
        futures[2].result(5)
    assert futures[3].result(5)['user']['id']
    with store.connection() as db:
        assert {row[0] for row in db.execute('SELECT telegram_id FROM ranking_users')} == {42, 44, 45}
        assert db.execute('SELECT display_name FROM ranking_users WHERE telegram_id=42').fetchone()[0] == 'Original'
    with pytest.raises(HTTPException) as limited:
        store.rate_limit('controlled', 'one', 1)
    assert limited.value.status_code == 429
    store.rate_limit('unexpected', 'one', 1)
    assert writer.snapshot()['batches'] == 1


def test_failed_batch_commit_rejects_every_waiter_rolls_back_and_recovers(make_writer, monkeypatch):
    from fastapi import HTTPException
    writer, store = make_writer(batch_size=3, batch_window=.03)
    original_commit = store._commit_batch
    attempts = 0

    def fail_once(db):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError('synthetic commit failure')
        original_commit(db)

    def controlled_rejection():
        store.rate_limit('failed-batch', 'guard', 1)
        raise HTTPException(401, 'invalid synthetic identity')

    monkeypatch.setattr(store, '_commit_batch', fail_once)
    with writer._condition:
        futures = [writer.submit(lambda: store.session({'id': 42}, None)),
                   writer.submit(controlled_rejection), writer.submit(lambda: store.session({'id': 43}, None))]
    for future in futures:
        with pytest.raises(HTTPException) as failed:
            future.result(5)
        assert failed.value.status_code == 503
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM ranking_users').fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM ranking_limits').fetchone()[0] == 0
    assert writer.submit(lambda: store.session({'id': 44}, None)).result(5)['user']['id']
    assert writer.snapshot()['failed_batches'] == 1
    assert writer.snapshot()['batches'] == 1


def test_batch_detects_automatic_transaction_rollback_without_false_ack(make_writer):
    from fastapi import HTTPException
    writer, store = make_writer(batch_size=3, batch_window=.03)

    def simulate_sqlite_automatic_rollback():
        # SQLite may roll back a whole transaction after an I/O/full error.
        # This simulates that state loss, not a normal endpoint operation.
        store._request_context.connection.rollback()
        raise sqlite3.OperationalError('synthetic transaction rollback')

    with writer._condition:
        futures = [writer.submit(lambda: store.session({'id': 42}, None)),
                   writer.submit(simulate_sqlite_automatic_rollback),
                   writer.submit(lambda: store.session({'id': 43}, None))]
    for future in futures:
        with pytest.raises(HTTPException) as failed:
            future.result(5)
        assert failed.value.status_code == 503
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM ranking_users').fetchone()[0] == 0
    assert writer.submit(lambda: store.session({'id': 44}, None)).result(5)['user']['id']


def test_writer_reuses_one_connection_with_bounded_batches(make_writer, monkeypatch):
    writer, store = make_writer(batch_size=8, batch_window=.03)
    opened = []
    committed = []
    original_open = store._open_connection
    original_commit = store._commit_batch

    def count_open():
        db = original_open()
        opened.append(id(db))
        return db

    def count_commit(db):
        committed.append(id(db))
        original_commit(db)

    monkeypatch.setattr(store, '_open_connection', count_open)
    monkeypatch.setattr(store, '_commit_batch', count_commit)
    with writer._condition:
        futures = [writer.submit(lambda index=index: store.rate_limit('probe', str(index), 1)) for index in range(24)]
    writer.close()
    assert all(future.result(0) is None for future in futures)
    assert len(opened) == 1 and len(committed) == 3 and set(committed) == set(opened)
    assert writer.snapshot()['peak_batch_size'] == 8


def test_acknowledged_group_survives_abrupt_process_termination(tmp_path):
    path = tmp_path / 'abrupt-process.sqlite'
    child_source = '''
import sys
from app.leaderboard import DurableWriteQueue, FinishBody, LeaderboardStore
now = [1800000000.0]
store = LeaderboardStore(sys.argv[1], lambda: now[0])
players = []
for identity in (41, 42):
    user = store.session({'id': identity}, None)['user']['id']
    players.append((user, store.start_run(user, 'snake')['run_id']))
now[0] += 10
for user, run in players:
    store.heartbeat(user, run, True)
now[0] += 10
writer = DurableWriteQueue(store, batch_size=2, batch_window=.05)
with writer._condition:
    futures = [writer.submit(lambda user=user, run=run: store.finish(user, run, FinishBody())) for user, run in players]
assert all(future.result(5)['points'] == 1 for future in futures)
assert writer.snapshot()['batches'] == 1
print('durable-acknowledgments:2', flush=True)
sys.stdin.read()
'''
    process = subprocess.Popen([sys.executable, '-c', child_source, str(path)],
                               cwd=Path(__file__).resolve().parents[1],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            line = pool.submit(process.stdout.readline)
            try:
                assert line.result(15).strip() == 'durable-acknowledgments:2'
                assert path.with_name(path.name + '-wal').stat().st_size > 0
            finally:
                # No lifespan, store.close, connection.close or checkpoint.
                process.kill()
                process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    with sqlite3.connect(path) as recovered:
        assert recovered.execute("SELECT count(*), sum(points) FROM ranking_runs WHERE status='finished'").fetchone() == (2, 2)
        assert recovered.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert recovered.execute('PRAGMA synchronous').fetchone()[0] == 2


def test_fatal_writer_failure_rejects_pending_jobs_and_closes(make_writer, monkeypatch):
    from fastapi import HTTPException
    writer, store = make_writer(batch_size=2, batch_window=.03)

    def fatal_failure(db, batch):
        raise RuntimeError('synthetic worker infrastructure failure')

    monkeypatch.setattr(writer, '_process_batch', fatal_failure)
    with writer._condition:
        futures = [writer.submit(lambda: store.session({'id': 42}, None)),
                   writer.submit(lambda: store.session({'id': 43}, None))]
    writer.close()
    for future in futures:
        with pytest.raises(HTTPException) as failed:
            future.result(0)
        assert failed.value.status_code == 503
    with pytest.raises(HTTPException):
        writer.submit(lambda: None)
    assert writer.snapshot()['thread_alive'] is False


def test_uncertain_commit_ack_failure_keeps_finish_retry_idempotent(make_writer, monkeypatch):
    from fastapi import HTTPException
    writer, store = make_writer(batch_window=0)
    clock = Clock()
    store.clock = clock
    session = store.session({'id': 42}, None)
    user_id = session['user']['id']
    run_id = store.start_run(user_id, 'snake')['run_id']
    clock.advance(10)
    store.heartbeat(user_id, run_id, True)
    clock.advance(10)
    original_commit = store._commit_batch
    attempts = 0

    def committed_but_ack_failed(db):
        nonlocal attempts
        original_commit(db)
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError('synthetic uncertainty after durable commit')

    monkeypatch.setattr(store, '_commit_batch', committed_but_ack_failed)
    with pytest.raises(HTTPException) as failed:
        writer.submit(lambda: store.finish(user_id, run_id, FinishBody())).result(5)
    assert failed.value.status_code == 503
    retry = writer.submit(lambda: store.finish(user_id, run_id, FinishBody())).result(5)
    assert retry['duplicate'] is True and retry['points'] == 1
    with store.connection() as db:
        assert db.execute('SELECT sum(points) FROM ranking_runs').fetchone()[0] == 1


def test_cancelled_http_waiter_cannot_cancel_accepted_durable_write(make_writer, monkeypatch):
    writer, store = make_writer(batch_window=0)
    entered = threading.Event()
    release = threading.Event()
    original_commit = store._commit_batch

    def blocked_commit(db):
        entered.set()
        assert release.wait(5)
        original_commit(db)

    monkeypatch.setattr(store, '_commit_batch', blocked_commit)

    async def cancel_waiter():
        request = asyncio.create_task(writer.call(lambda: store.session({'id': 42}, None)))
        assert await asyncio.to_thread(entered.wait, 5)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert writer.snapshot()['completed_requests'] == 0
        release.set()
        await writer.aclose()

    try:
        asyncio.run(cancel_waiter())
    finally:
        release.set()
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT telegram_id FROM ranking_users').fetchone()[0] == 42
    assert writer.snapshot()['completed_requests'] == 1


def test_shutdown_drains_all_accepted_jobs_and_rejects_new_jobs(make_writer):
    from fastapi import HTTPException
    writer, store = make_writer(batch_size=4, batch_window=.03)
    futures = [writer.submit(lambda index=index: store.session({'id': 1000 + index}, None)) for index in range(11)]
    asyncio.run(writer.aclose())
    assert all(future.result(0)['user']['id'] for future in futures)
    assert writer.snapshot()['completed_requests'] == 11
    assert writer.snapshot()['peak_batch_size'] == 4
    assert writer.snapshot()['thread_alive'] is False
    with pytest.raises(HTTPException) as closed:
        writer.submit(lambda: None)
    assert closed.value.status_code == 503
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM ranking_users').fetchone()[0] == 11
        assert db.execute('PRAGMA synchronous').fetchone()[0] == 2
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_writer_queue_is_bounded_without_dropping_accepted_jobs(make_writer):
    from fastapi import HTTPException
    writer, store = make_writer(batch_size=1, batch_window=0, max_pending=2)
    entered = threading.Event()
    release = threading.Event()

    def blocked_request():
        entered.set()
        assert release.wait(5)
        return store.session({'id': 42}, None)

    first = writer.submit(blocked_request)
    try:
        assert entered.wait(5)
        pending = [writer.submit(lambda index=index: store.session({'id': 43 + index}, None)) for index in range(2)]
        with pytest.raises(HTTPException) as overflow:
            writer.submit(lambda: store.session({'id': 99}, None))
        assert overflow.value.status_code == 503
        assert overflow.value.headers['Retry-After'] == '1'
        assert writer.snapshot()['pending'] == 2
    finally:
        release.set()
    assert all(future.result(5)['user']['id'] for future in [first, *pending])
    with store.connection() as db:
        assert {row[0] for row in db.execute('SELECT telegram_id FROM ranking_users')} == {42, 43, 44}


def test_writer_keeps_context_and_works_across_event_loops(make_writer):
    writer, store = make_writer(batch_window=0)
    identity = contextvars.ContextVar('synthetic_identity')

    async def call_with_identity(value):
        identity.set(value)
        return await writer.call(lambda: (identity.get(), store._request_context.depth))

    assert asyncio.run(call_with_identity('first')) == ('first', 1)
    assert asyncio.run(call_with_identity('second')) == ('second', 1)
    assert writer.submit(lambda: getattr(store._request_context, 'depth')).result(5) == 1


def test_async_writer_never_occupies_starlette_workers_while_queued(make_writer, monkeypatch):
    import anyio
    from starlette.concurrency import run_in_threadpool
    writer, store = make_writer(batch_size=4, batch_window=.005)
    entered = threading.Event()
    release = threading.Event()
    original_commit = store._commit_batch

    def blocked_commit(db):
        entered.set()
        assert release.wait(5)
        original_commit(db)

    monkeypatch.setattr(store, '_commit_batch', blocked_commit)

    async def prove_independent_asset_worker():
        limiter = anyio.to_thread.current_default_thread_limiter()
        previous = limiter.total_tokens
        limiter.total_tokens = 1
        try:
            requests = [asyncio.create_task(writer.call(lambda index=index: store.session({'id': 1000 + index}, None)))
                        for index in range(12)]
            assert await asyncio.to_thread(entered.wait, 5)
            assert await asyncio.wait_for(run_in_threadpool(lambda: 'game asset'), .5) == 'game asset'
            release.set()
            assert len(await asyncio.gather(*requests)) == 12
        finally:
            limiter.total_tokens = previous
            release.set()

    asyncio.run(prove_independent_asset_worker())


def test_router_lifespan_closes_writer_after_durable_http_requests(tmp_path):
    path = tmp_path / 'lifespan.sqlite'
    clock = Clock()
    router = create_leaderboard_router(lambda: CATALOG, TEST_TOKEN, path, clock=clock)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        authenticate(client, clock)
        assert router.leaderboard_writer.snapshot()['thread_alive'] is True
    assert router.leaderboard_writer.snapshot()['thread_alive'] is False
    assert router.leaderboard_writer.snapshot()['accepting'] is False
    assert router.leaderboard_writer.store._keepalive is None
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM ranking_sessions').fetchone()[0] == 1


def test_new_session_reuses_user_without_resetting_existing_points(setup_api):
    client, clock, _, _ = setup_api
    headers, session = authenticate(client, clock)
    round_play(client, clock, headers)
    new_headers, renewed = authenticate(client, clock, display_name="Novo nome")
    assert renewed["user"]["id"] == session["user"]["id"]
    assert renewed["token"] != session["token"]
    assert client.get("/api/leaderboard", headers=new_headers).json()["me"]["points"] == 1
    assert client.get("/api/leaderboard").json()["entries"][0]["display_name"] == "Novo nome"


def test_database_cannot_be_put_in_public_static_directory(tmp_path):
    from pathlib import Path
    public = Path(__file__).resolve().parents[1] / "web" / "should-never-exist.sqlite"
    with pytest.raises(ValueError, match="outside"):
        LeaderboardStore(public)
    assert not public.exists()


def test_display_name_is_plain_text_without_emoji_or_direction_controls():
    assert clean_display_name("<script>alert(1)</script>🎮\u202e") == "alert1"
    assert clean_display_name("" ) == "Jogador"
    assert len(clean_display_name("a" * 200)) == 32
