"""Persistent participation rankings, authenticated with Telegram Mini App data.

The server verifies Telegram identity and measures heartbeat intervals. It cannot
verify a game rendered in an untrusted browser, so neither a browser score nor an
"active" heartbeat is advertised as a verified competitive result.
"""
from __future__ import annotations

import hashlib
import asyncio
import contextvars
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from collections.abc import Callable, Iterator
from collections import deque
from concurrent.futures import Future
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt

MIN_ACTIVE_SECONDS = 15
HEARTBEAT_INTERVAL_SECONDS = 10
MAX_HEARTBEAT_GAP = 15
MAX_RUN_SECONDS = 3600
SESSION_SECONDS = 6 * 3600
INIT_DATA_MAX_AGE = 15 * 60
DAILY_POINTS_CAP = 100
RUN_POINTS_CAP = 10
TRUST_POLICY = (
    "Pontos de atividade: 1 ponto a cada 15 segundos de atividade sinalizada, "
    "até 10 por partida e 100 por dia (UTC). O servidor mede os intervalos; "
    "o navegador informa a atividade. A identidade é validada pelo Telegram, "
    "mas a jogabilidade e os placares não têm verificação independente."
)


class RankingRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def validate_request(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                # Do not echo credentials, arbitrary input or non-JSON numeric
                # constants through FastAPI's default validation-error payload.
                raise HTTPException(422, "Os dados enviados para o ranking são inválidos.") from None

        return validate_request


class SessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    init_data: str = Field(min_length=1, max_length=16384)
    display_name: str | None = Field(default=None, max_length=100)


class RunBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class HeartbeatBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: StrictBool = True


class FinishBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Saved only as a browser-reported diagnostic; never used for ranking points.
    score: StrictInt | StrictFloat | None = Field(default=None, ge=0, le=1_000_000_000, allow_inf_nan=False)
    duration_ms: StrictInt | None = Field(default=None, ge=0, le=MAX_RUN_SECONDS * 1000)
    outcome: Literal["completed", "ended", "abandoned"] = "ended"


def clean_display_name(value: Any) -> str:
    text = re.sub(r"<[^>]*>", "", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char)[0] in "LNM" or char in " ._-'")
    return " ".join(text.split())[:32].strip() or "Jogador"


def validate_init_data(init_data: str, bot_token: str, now: float) -> dict[str, Any]:
    """Validate HMAC as documented at core.telegram.org/bots/webapps.

    Duplicate keys and stale/future timestamps are rejected before accepting an
    identity. initDataUnsafe is never accepted by this API.
    """
    if not bot_token:
        raise HTTPException(503, "A autenticação pelo Telegram está indisponível.")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError("duplicate fields")
        supplied_hash = fields.pop("hash")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", supplied_hash):
            raise ValueError("invalid hash")
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied_hash.lower()):
            raise ValueError("invalid signature")
        auth_date = int(fields["auth_date"])
        if not now - INIT_DATA_MAX_AGE <= auth_date <= now + 30:
            raise ValueError("expired authorization")
        user = json.loads(fields["user"])
        if not isinstance(user, dict) or type(user.get("id")) is not int or not 0 < user["id"] < 2**52:
            raise ValueError("invalid user")
        if user.get("is_bot"):
            raise ValueError("bot identity")
        return user
    except (ValueError, TypeError, KeyError, OverflowError):
        raise HTTPException(401, "A sessão do Telegram é inválida ou expirou. Reabra o aplicativo.") from None


class LeaderboardStore:
    def __init__(self, database_path: str | Path, clock: Callable[[], float] = time.time):
        self.path = Path(database_path).resolve()
        web_root = Path(__file__).resolve().parents[1] / "web"
        if self.path == web_root or web_root in self.path.parents:
            raise ValueError("Ranking database must be outside the public web directory")
        self.clock = clock
        self._request_context = threading.local()
        self._writer_lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ranking_users (
                    id TEXT PRIMARY KEY,
                    telegram_id INTEGER NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ranking_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES ranking_users(id),
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ranking_sessions_user ON ranking_sessions(user_id);
                CREATE TABLE IF NOT EXISTS ranking_runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES ranking_users(id),
                    game_slug TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    last_heartbeat REAL NOT NULL,
                    active_window INTEGER NOT NULL DEFAULT 1,
                    active_seconds REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    finished_at REAL,
                    points INTEGER NOT NULL DEFAULT 0,
                    browser_score REAL,
                    outcome TEXT,
                    reason TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS ranking_one_active_run
                    ON ranking_runs(user_id) WHERE status = 'active';
                CREATE INDEX IF NOT EXISTS ranking_runs_finished ON ranking_runs(status, finished_at, game_slug);
                CREATE TABLE IF NOT EXISTS ranking_limits (
                    bucket TEXT PRIMARY KEY,
                    minute INTEGER NOT NULL,
                    requests INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ranking_limits_minute ON ranking_limits(minute);
            """)
        if os.name != "nt":
            self.path.chmod(0o600)
        # Keep WAL open for the lifetime of the store. Closing the last SQLite
        # connection after each small operation otherwise checkpoints and
        # recreates WAL/SHM repeatedly, serializing concurrent heartbeats.
        # Write durability remains SQLite's FULL synchronous default.
        self._keepalive = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        # sqlite3.connect() alone is lazy: without reading the schema the handle
        # has not joined WAL and other connections still tear WAL/SHM down.
        self._keepalive.execute('SELECT count(*) FROM sqlite_master').fetchone()

    def close(self) -> None:
        connection = getattr(self, "_keepalive", None)
        if connection is not None:
            self._keepalive = None
            connection.close()

    def __del__(self):
        self.close()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        shared = getattr(self._request_context, "connection", None)
        if shared is not None:
            depth = getattr(self._request_context, "depth", 0) + 1
            self._request_context.depth = depth
            savepoint = f"operation_{depth}"
            shared.execute(f"SAVEPOINT {savepoint}")
            try:
                yield shared
            except BaseException:
                shared.execute(f"ROLLBACK TO {savepoint}")
                raise
            finally:
                shared.execute(f"RELEASE {savepoint}")
                self._request_context.depth = depth - 1
            return
        db = self._open_connection()
        try:
            with db:
                yield db
        finally:
            db.close()

    def _open_connection(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=10000")
            # Every acknowledged batch is durable even without a checkpoint.
            db.execute("PRAGMA synchronous=FULL")
        except BaseException:
            db.close()
            raise
        return db

    def _commit_batch(self, db: sqlite3.Connection) -> None:
        db.commit()

    @contextmanager
    def batch_transaction(self, db: sqlite3.Connection):
        """One FULL commit, with independent request savepoints inside it.

        The dedicated writer owns this connection. Default WAL checkpointing
        stays on that same writer; no concurrent checkpoint is introduced.
        """
        with self._writer_lock:
            if db.in_transaction or getattr(self._request_context, "connection", None) is not None:
                raise RuntimeError("A ranking batch cannot nest another transaction")
            self._begin_write(db)
            self._request_context.connection = db
            self._request_context.depth = 0
            try:
                yield
                if not db.in_transaction:
                    raise sqlite3.OperationalError("Ranking batch lost its transaction")
                self._commit_batch(db)
            except BaseException:
                try:
                    db.rollback()
                except sqlite3.Error:
                    pass
                raise
            finally:
                self._request_context.connection = None
                self._request_context.depth = 0

    @staticmethod
    def _begin_write(db: sqlite3.Connection) -> None:
        if not db.in_transaction:
            db.execute("BEGIN IMMEDIATE")

    @contextmanager
    def write_connection(self) -> Iterator[sqlite3.Connection]:
        # SQLite permits one WAL writer. Queue writers before opening their
        # connections instead of letting worker threads compete through its
        # busy-handler backoff. Reentrant for operations inside a request.
        with self._writer_lock:
            with self.connection() as db:
                yield db

    @contextmanager
    def request_transaction(self):
        """An isolated request, committed alone or within a durable batch.

        A controlled HTTP rejection retains previous rate-limit increments,
        while the failing operation rolls back its own partial changes. An
        unexpected exception rolls back the whole request.
        """
        if getattr(self._request_context, "connection", None) is not None:
            rejection = None
            with self.connection():
                try:
                    yield
                except HTTPException as error:
                    # The failing inner operation already rolled back its own
                    # savepoint. Keep earlier guards, without committing other
                    # requests or clearing the batch's shared connection.
                    rejection = error
            if rejection is not None:
                raise rejection
            return
        with self.write_connection() as db:
            self._begin_write(db)
            self._request_context.connection = db
            try:
                yield
            except HTTPException:
                db.commit()
                raise
            finally:
                self._request_context.connection = None

    def rate_limit(self, namespace: str, identity: str, maximum: int) -> None:
        minute = int(self.clock() // 60)
        # The database does not retain the requester's raw IP address or token.
        bucket = hashlib.sha256(f"{namespace}:{identity}:{minute}".encode()).hexdigest()
        with self.write_connection() as db:
            self._begin_write(db)
            row = db.execute("SELECT requests FROM ranking_limits WHERE bucket=?", (bucket,)).fetchone()
            if row and row["requests"] >= maximum:
                raise HTTPException(429, "Muitas solicitações. Aguarde um minuto.", headers={"Retry-After": "60"})
            db.execute("""INSERT INTO ranking_limits VALUES (?, ?, 1)
                ON CONFLICT(bucket) DO UPDATE SET requests=requests+1""", (bucket, minute))
            db.execute("DELETE FROM ranking_limits WHERE minute < ?", (minute - 10,))

    def authenticate(self, authorization: str | None, *, optional: bool = False) -> dict[str, Any] | None:
        if not authorization:
            if optional:
                return None
            raise HTTPException(401, "Abra o aplicativo pelo Telegram para participar do ranking.")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not 32 <= len(token) <= 128:
            raise HTTPException(401, "Sessão inválida. Reabra o aplicativo pelo Telegram.")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.connection() as db:
            row = db.execute("""SELECT u.id, u.display_name FROM ranking_sessions s
                JOIN ranking_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?""",
                (digest, self.clock())).fetchone()
        if row is None:
            raise HTTPException(401, "Sessão inválida ou expirada. Reabra o aplicativo pelo Telegram.")
        return dict(row)

    def session(self, user: dict[str, Any], display_name: str | None) -> dict[str, Any]:
        now = self.clock()
        token = secrets.token_urlsafe(32)
        name = clean_display_name(display_name if display_name is not None else user.get("first_name"))
        with self.write_connection() as db:
            self._begin_write(db)
            existing = db.execute("SELECT id FROM ranking_users WHERE telegram_id=?", (user["id"],)).fetchone()
            user_id = existing["id"] if existing else secrets.token_hex(16)
            db.execute("""INSERT INTO ranking_users VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET display_name=excluded.display_name""",
                (user_id, user["id"], name, now))
            db.execute("DELETE FROM ranking_sessions WHERE expires_at<=?", (now,))
            db.execute("""DELETE FROM ranking_sessions WHERE token_hash IN
                (SELECT token_hash FROM ranking_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT -1 OFFSET 4)""", (user_id,))
            db.execute("INSERT INTO ranking_sessions VALUES (?, ?, ?, ?)",
                       (hashlib.sha256(token.encode()).hexdigest(), user_id, now, now + SESSION_SECONDS))
        return {"token": token, "user": {"id": user_id, "display_name": name}, "guest": False,
                "expires_at": int(now + SESSION_SECONDS)}

    def start_run(self, user_id: str, game_slug: str) -> dict[str, Any]:
        now = self.clock()
        reused = False
        with self.write_connection() as db:
            self._begin_write(db)
            active = db.execute("SELECT * FROM ranking_runs WHERE user_id=? AND status='active'", (user_id,)).fetchone()
            if active and active["game_slug"] == game_slug and now - active["started_at"] <= MAX_RUN_SECONDS:
                run_id = active["id"]
                reused = True
            else:
                # A game switch abandons the previous round without awarding points.
                db.execute("""UPDATE ranking_runs SET status='abandoned',finished_at=?,reason='substituida'
                    WHERE user_id=? AND status='active'""", (now, user_id))
                run_id = secrets.token_urlsafe(24)
                db.execute("""INSERT INTO ranking_runs
                    (id,user_id,game_slug,started_at,last_heartbeat) VALUES (?,?,?,?,?)""",
                    (run_id, user_id, game_slug, now, now))
        return {"run_id": run_id, "reused": reused, "minimum_active_seconds": MIN_ACTIVE_SECONDS,
                "heartbeat_interval_seconds": HEARTBEAT_INTERVAL_SECONDS}

    @staticmethod
    def _active_increment(row: sqlite3.Row, now: float) -> float:
        delta = now - row["last_heartbeat"]
        return delta if row["active_window"] and 0 <= delta <= MAX_HEARTBEAT_GAP else 0

    def heartbeat(self, user_id: str, run_id: str, active: bool) -> dict[str, Any]:
        now = self.clock()
        with self.write_connection() as db:
            self._begin_write(db)
            row = db.execute("SELECT * FROM ranking_runs WHERE id=? AND user_id=?", (run_id, user_id)).fetchone()
            if row is None:
                raise HTTPException(404, "Partida não encontrada.")
            if row["status"] != "active":
                raise HTTPException(409, "Esta partida já foi encerrada.")
            if not 0 <= now - row["started_at"] <= MAX_RUN_SECONDS:
                raise HTTPException(409, "A partida expirou. Inicie uma nova partida.")
            seconds = min(MAX_RUN_SECONDS, row["active_seconds"] + self._active_increment(row, now))
            db.execute("""UPDATE ranking_runs SET active_seconds=?,last_heartbeat=?,active_window=? WHERE id=?""",
                       (seconds, now, int(active), run_id))
        return {"active_seconds": int(seconds), "active": active}

    def finish(self, user_id: str, run_id: str, body: FinishBody) -> dict[str, Any]:
        now = self.clock()
        with self.write_connection() as db:
            # Serializes duplicate/concurrent submissions and daily-cap accounting.
            self._begin_write(db)
            row = db.execute("SELECT * FROM ranking_runs WHERE id=? AND user_id=?", (run_id, user_id)).fetchone()
            if row is None:
                raise HTTPException(404, "Partida não encontrada.")
            if row["status"] != "active":
                return {"accepted": row["reason"] in {"registrada", "limite_diario"}, "points": row["points"],
                        "active_seconds": int(row["active_seconds"]), "reason": row["reason"],
                        "duplicate": True, "score_source": "browser", "verified": False}
            elapsed = now - row["started_at"]
            seconds = row["active_seconds"] + self._active_increment(row, now)
            day_start = int(now // 86400) * 86400
            earned_today = db.execute("""SELECT COALESCE(SUM(points),0) FROM ranking_runs
                WHERE user_id=? AND status='finished' AND finished_at>=?""", (user_id, day_start)).fetchone()[0]
            if not 0 <= elapsed <= MAX_RUN_SECONDS:
                points, reason = 0, "partida_expirada"
            elif seconds < MIN_ACTIVE_SECONDS:
                points, reason = 0, "atividade_insuficiente"
            else:
                points = min(RUN_POINTS_CAP, math.floor(seconds / MIN_ACTIVE_SECONDS), max(0, DAILY_POINTS_CAP - earned_today))
                reason = "registrada" if points else "limite_diario"
            db.execute("""UPDATE ranking_runs SET status='finished',finished_at=?,active_seconds=?,
                points=?,browser_score=?,outcome=?,reason=?,active_window=0 WHERE id=?""",
                (now, seconds, points, body.score, body.outcome, reason, run_id))
        return {"accepted": reason in {"registrada", "limite_diario"}, "points": points,
                "active_seconds": int(seconds), "reason": reason, "duplicate": False,
                "score_source": "browser", "verified": False}

    def leaderboard(self, user: dict[str, Any] | None, game: str | None, period: str) -> dict[str, Any]:
        now = self.clock()
        since = {"all": 0, "week": now - 7 * 86400, "month": now - 30 * 86400}[period]
        params: list[Any] = [since]
        game_filter = ""
        if game:
            game_filter = " AND r.game_slug=?"
            params.append(game)
        with self.connection() as db:
            rows = db.execute(f"""SELECT u.id,u.display_name,SUM(r.points) AS points,
                COUNT(*) AS games_played,MIN(r.finished_at) AS first_finish
                FROM ranking_runs r JOIN ranking_users u ON u.id=r.user_id
                WHERE r.status='finished' AND r.points>0 AND r.finished_at>=? {game_filter}
                GROUP BY u.id ORDER BY points DESC,games_played DESC,first_finish ASC,u.id ASC""", params).fetchall()
        entries = []
        me = None
        for index, row in enumerate(rows, 1):
            entry = {"rank": index, "display_name": row["display_name"], "points": row["points"],
                     "games_played": row["games_played"], "is_me": bool(user and user["id"] == row["id"])}
            if index <= 100:
                entries.append(entry)
            if entry["is_me"]:
                me = entry
        if user and me is None:
            me = {"rank": None, "display_name": user["display_name"], "points": 0, "games_played": 0, "is_me": True}
        return {"entries": entries, "me": me, "verified": False, "metric": "activity",
                "scope": "game" if game else "global", "period": period, "game": game,
                "trust_policy": TRUST_POLICY}


@dataclass(slots=True)
class _WriteJob:
    callback: Callable[[], Any]
    context: contextvars.Context
    future: Future
    submitted_at: float


class DurableWriteQueue:
    """A bounded, single-threaded writer with durable group commit.

    Accepted requests survive cancellation of their HTTP waiter. Futures are
    completed only after the whole batch's FULL commit, including controlled
    HTTP rejections whose earlier rate-limit increments must be retained.
    The thread-side queue also works with callers on different event loops.
    """

    def __init__(self, store: LeaderboardStore, *, batch_size: int = 32,
                 batch_window: float = .002, max_pending: int = 4096):
        if batch_size < 1 or not 0 <= batch_window <= .1 or max_pending < 1:
            raise ValueError("Invalid durable writer queue limits")
        self.store = store
        self.batch_size = batch_size
        self.batch_window = batch_window
        self.max_pending = max_pending
        self._condition = threading.Condition()
        self._pending: deque[_WriteJob] = deque()
        self._thread: threading.Thread | None = None
        self._closing = False
        self._closed: Future = Future()
        self._closed.set_running_or_notify_cancel()
        self._batches = 0
        self._completed = 0
        self._failed_batches = 0
        self._peak_batch = 0
        # Optional isolated-load observer: (metric, value). Durations use ms;
        # writer_batch_size is a count. Observers cannot change write behavior.
        self.observe: Callable[[str, float], None] | None = None

    @staticmethod
    def _unavailable() -> HTTPException:
        return HTTPException(503, "O ranking está ocupado. Tente novamente em instantes.",
                             headers={"Retry-After": "1"})

    def _record(self, name: str, value: float) -> None:
        if self.observe is not None:
            try:
                self.observe(name, value)
            except Exception:
                pass

    def snapshot(self) -> dict[str, Any]:
        with self._condition:
            return {"batches": self._batches, "completed_requests": self._completed,
                    "failed_batches": self._failed_batches, "peak_batch_size": self._peak_batch,
                    "pending": len(self._pending), "accepting": not self._closing,
                    "thread_alive": bool(self._thread and self._thread.is_alive())}

    def submit(self, callback: Callable[[], Any]) -> Future:
        with self._condition:
            if self._closing or len(self._pending) >= self.max_pending:
                raise self._unavailable()
            future: Future = Future()
            # Once accepted, cancellation cannot retract an in-flight write or
            # a guard update. A retry is handled by the existing idempotency.
            future.set_running_or_notify_cancel()
            self._pending.append(_WriteJob(callback, contextvars.copy_context(), future, time.monotonic()))
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="ranking-writer", daemon=True)
                try:
                    self._thread.start()
                except BaseException:
                    self._pending.pop()
                    self._thread = None
                    raise
            self._condition.notify()
            return future

    @staticmethod
    def _consume_abandoned(future: asyncio.Future) -> None:
        if not future.cancelled():
            future.exception()

    async def call(self, callback: Callable[[], Any]) -> Any:
        future = asyncio.wrap_future(self.submit(callback))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # Retrieve a later failure even when the disconnected HTTP caller
            # no longer awaits it; the accepted job is still drained durably.
            future.add_done_callback(self._consume_abandoned)
            raise

    def _next_batch(self) -> list[_WriteJob]:
        with self._condition:
            while not self._pending:
                if self._closing:
                    return []
                self._condition.wait()
            batch = [self._pending.popleft()]
            deadline = time.monotonic() + self.batch_window
            while len(batch) < self.batch_size:
                if self._pending:
                    batch.append(self._pending.popleft())
                else:
                    remaining = deadline - time.monotonic()
                    if self._closing or remaining <= 0:
                        break
                    self._condition.wait(remaining)
            return batch

    def _execute(self, job: _WriteJob) -> Any:
        with self.store.request_transaction():
            return job.callback()

    def _process_batch(self, db: sqlite3.Connection | None, batch: list[_WriteJob]) -> sqlite3.Connection | None:
        outcomes: list[tuple[Any, BaseException | None]] = []
        started = time.monotonic()
        try:
            if db is None:
                db = self.store._open_connection()
            with self.store.batch_transaction(db):
                for job in batch:
                    before_request = time.monotonic()
                    self._record("writer_queue_wait", (before_request - job.submitted_at) * 1000)
                    try:
                        outcomes.append((job.context.run(self._execute, job), None))
                    except BaseException as error:
                        # request_transaction rolls back unexpected failures,
                        # retaining controlled HTTP guard increments. Neither
                        # failure poisons successful neighboring requests.
                        outcomes.append((None, error))
                    if not db.in_transaction or self.store._request_context.depth != 0:
                        raise sqlite3.OperationalError("Ranking request lost its batch savepoint")
                    self._record("writer_request_body", (time.monotonic() - before_request) * 1000)
        except BaseException:
            # No success or controlled rejection may escape a failed COMMIT.
            # Its outcome may be uncertain, so callers retry using run IDs.
            outcomes = [(None, self._unavailable()) for _ in batch]
            if db is not None:
                try:
                    db.close()
                except sqlite3.Error:
                    pass
                db = None
            with self._condition:
                self._failed_batches += 1
        else:
            with self._condition:
                self._batches += 1
        self._record("writer_batch_duration", (time.monotonic() - started) * 1000)
        self._record("writer_batch_size", len(batch))
        with self._condition:
            self._completed += len(batch)
            self._peak_batch = max(self._peak_batch, len(batch))
        # This is deliberately outside the transaction and after COMMIT.
        for job, (value, error) in zip(batch, outcomes):
            if error is None:
                job.future.set_result(value)
            else:
                job.future.set_exception(error)
        return db

    def _run(self) -> None:
        db = None
        batch = []
        try:
            while batch := self._next_batch():
                db = self._process_batch(db, batch)
        except BaseException:
            # Even an unforeseen writer failure must not leave accepted HTTP
            # waiters hanging or allow new writes into an abandoned queue.
            with self._condition:
                self._closing = True
                abandoned = [*batch, *self._pending]
                self._pending.clear()
            for job in abandoned:
                if not job.future.done():
                    job.future.set_exception(self._unavailable())
        finally:
            try:
                if db is not None:
                    db.close()
            finally:
                self._closed.set_result(None)

    def _stop_accepting(self) -> threading.Thread | None:
        with self._condition:
            self._closing = True
            if self._thread is None and not self._closed.done():
                self._closed.set_result(None)
            self._condition.notify_all()
            return self._thread

    def close(self) -> None:
        """Stop accepting, drain accepted writes, then close the connection."""
        thread = self._stop_accepting()
        if thread is not None and thread is not threading.current_thread():
            thread.join()

    async def aclose(self) -> None:
        thread = self._stop_accepting()
        await asyncio.shield(asyncio.wrap_future(self._closed))
        # _closed is signaled only after the connection is closed; the thread
        # now has no work left and joining it cannot wait for a write.
        if thread is not None and thread is not threading.current_thread():
            thread.join()


def create_leaderboard_router(
    catalog_loader: Callable[[], dict[str, Any]],
    bot_token: str | None = None,
    database_path: str | Path | None = None,
    *,
    clock: Callable[[], float] = time.time,
) -> APIRouter:
    """Create once at app startup; include before any catch-all SPA route."""
    token = bot_token if bot_token is not None else os.getenv("BOT_TOKEN", "").strip()
    default_path = Path(__file__).resolve().parents[1] / ".private-data" / "leaderboard.sqlite"
    store = LeaderboardStore(database_path or os.getenv("DATABASE_PATH", str(default_path)), clock)
    writer = DurableWriteQueue(store)
    @asynccontextmanager
    async def lifespan(_):
        try:
            yield
        finally:
            await writer.aclose()
            store.close()

    router = APIRouter(prefix="/api", tags=["ranking"], route_class=RankingRoute, lifespan=lifespan)
    router.leaderboard_writer = writer
    known_games = frozenset(game.get("slug") for game in catalog_loader().get("games", []))

    def transactional(endpoint):
        @wraps(endpoint)
        async def handle(*args, **kwargs):
            return await writer.call(lambda: endpoint(*args, **kwargs))
        handle.leaderboard_writer = writer
        return handle

    def ip(request: Request) -> str:
        # Only the ASGI server's trusted-proxy handling may interpret forwarded IPs.
        return request.client.host if request.client else "unknown"

    def game_exists(slug: str) -> None:
        if slug not in known_games:
            raise HTTPException(404, "Jogo não encontrado.")

    def auth(request: Request, authorization: str | None, optional: bool = False) -> dict[str, Any] | None:
        try:
            user = store.authenticate(authorization, optional=optional)
        except HTTPException:
            store.rate_limit("invalid-auth-ip", ip(request), 180)
            raise
        if user is None:
            store.rate_limit("public-ranking-ip", ip(request), 3000)
        else:
            # A carrier, school or household can share one public IP. Signed
            # identities have independent budgets; invalid credentials retain
            # an IP budget and never consume a legitimate user's allowance.
            store.rate_limit("auth-user", user["id"], 180)
        return user

    @router.post("/session")
    @transactional
    def session(body: SessionBody, request: Request, response: Response) -> dict[str, Any]:
        try:
            user = validate_init_data(body.init_data, token, clock())
        except HTTPException:
            store.rate_limit("invalid-session-ip", ip(request), 10)
            raise
        store.rate_limit("session-user", str(user["id"]), 10)
        response.headers["Cache-Control"] = "no-store"
        return store.session(user, body.display_name)

    @router.get("/leaderboard")
    @transactional
    def leaderboard(request: Request, response: Response,
                    scope: Literal["global", "game"] = "global",
                    period: Literal["all", "week", "month"] = "all",
                    game: str | None = Query(default=None, max_length=100),
                    authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = auth(request, authorization, optional=True)
        if game:
            game_exists(game)
        elif scope == "game":
            raise HTTPException(422, "Selecione um jogo para este ranking.")
        response.headers["Cache-Control"] = "no-store"
        return store.leaderboard(user, game, period)

    @router.post("/runs")
    @transactional
    def start_run(body: RunBody, request: Request, response: Response,
                  authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = auth(request, authorization)
        store.rate_limit("run-user", user["id"], 20)
        game_exists(body.game_slug)
        response.headers["Cache-Control"] = "no-store"
        return store.start_run(user["id"], body.game_slug)

    @router.post("/runs/{run_id}/heartbeat")
    @transactional
    def heartbeat(run_id: str, body: HeartbeatBody, request: Request,
                  authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = auth(request, authorization)
        store.rate_limit("heartbeat-user", user["id"], 30)
        return store.heartbeat(user["id"], run_id, body.active)

    @router.post("/runs/{run_id}/finish")
    @transactional
    def finish(run_id: str, body: FinishBody, request: Request,
               authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = auth(request, authorization)
        store.rate_limit("finish-user", user["id"], 30)
        return store.finish(user["id"], run_id, body)

    return router
