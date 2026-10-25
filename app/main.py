from __future__ import annotations

import json
import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
CATALOG_FILE = Path(os.getenv("CATALOG_FILE", ROOT / "data" / "registry.json"))
UPSTREAM_BASE = os.getenv("UPSTREAM_GAMES_BASE", "https://sausi-7.github.io/games").rstrip("/")
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CONFIG_OVERRIDES_FILE = ROOT / "data" / "config-overrides.json"
CONFIG_OVERRIDES = (
    json.loads(CONFIG_OVERRIDES_FILE.read_text(encoding="utf-8")).get("configs", {})
    if CONFIG_OVERRIDES_FILE.exists() else {}
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("baltigogames")
# Telegram request URLs contain the bot credential.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

_bot_application = None
_proxy_client: httpx.AsyncClient | None = None


def public_app_url() -> str:
    explicit = os.getenv("APP_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    railway = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
    if railway:
        return f"https://{railway}"
    render = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render:
        return render
    vercel = os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "").strip()
    if vercel:
        return f"https://{vercel}"
    return "http://localhost:8000"


def load_catalog() -> dict[str, Any]:
    if not CATALOG_FILE.exists():
        return {"version": 1, "categories": [], "games": []}
    with CATALOG_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sanitize_proxy_path(raw_path: str) -> str:
    decoded = raw_path.replace("\\", "/").lstrip("/")
    parts = PurePosixPath(decoded).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid game path")
    if parts[0] != "games":
        raise ValueError("only game assets can be proxied")
    return "/".join(parts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_application, _proxy_client
    _proxy_client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(25.0, connect=10.0),
        headers={"User-Agent": "BaltigoGames/1.0 (+Telegram Mini App)"},
    )

    if BOT_TOKEN:
        try:
            from .bot import start_bot

            _bot_application = await start_bot(BOT_TOKEN, public_app_url(), load_catalog)
            logger.info("Telegram bot connected")
        except Exception as exc:
            logger.error("Telegram bot failed to start (%s)", type(exc).__name__)
            await _proxy_client.aclose()
            raise RuntimeError("Telegram bot startup failed") from None
    else:
        logger.info("BOT_TOKEN not configured; running web app only")

    yield

    if _bot_application is not None:
        try:
            await _bot_application.updater.stop()
            await _bot_application.stop()
            await _bot_application.shutdown()
        except Exception:
            logger.exception("Error while shutting down Telegram bot")

    if _proxy_client is not None:
        await _proxy_client.aclose()


app = FastAPI(title="Baltigo Games", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/health")
async def health() -> dict[str, Any]:
    catalog = load_catalog()
    bot_running = bool(_bot_application and _bot_application.running
                       and _bot_application.updater.running)
    ready = bool(catalog.get("games")) and (not BOT_TOKEN or bot_running)
    return JSONResponse({
        "ok": ready,
        "service": "baltigo-games",
        "games": len(catalog.get("games", [])),
        "bot_configured": bool(BOT_TOKEN),
        "bot_running": bot_running,
    }, status_code=200 if ready else 503)


@app.get("/api/catalog")
async def catalog() -> JSONResponse:
    data = load_catalog()
    return JSONResponse(
        data,
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=3600"},
    )


@app.get("/api/config")
async def config() -> dict[str, Any]:
    return {
        "app_url": public_app_url(),
        "telegram_enabled": bool(BOT_TOKEN),
        "brand": "Baltigo Games",
    }


@app.get("/play/{asset_path:path}")
async def play_proxy(asset_path: str, request: Request) -> Response:
    global _proxy_client
    try:
        safe_path = sanitize_proxy_path(asset_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if safe_path in CONFIG_OVERRIDES:
        return JSONResponse(CONFIG_OVERRIDES[safe_path], headers={"Cache-Control": "public, max-age=3600"})

    if _proxy_client is None:
        raise HTTPException(status_code=503, detail="proxy not ready")

    url = f"{UPSTREAM_BASE}/{quote(safe_path, safe='/._-')}"
    if request.url.query:
        url += f"?{request.url.query}"

    try:
        upstream = await _proxy_client.get(url)
        # Several upstream games reference a shared font one directory too high.
        if upstream.status_code == 404 and PurePosixPath(safe_path).name == "outfit.ttf":
            upstream = await _proxy_client.get(f"{UPSTREAM_BASE}/games/arcade/snake/outfit.ttf")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="upstream game unavailable") from exc

    if upstream.status_code == 404:
        raise HTTPException(status_code=404, detail="game asset not found")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"upstream returned {upstream.status_code}")

    content_type = upstream.headers.get("content-type")
    if not content_type:
        content_type = mimetypes.guess_type(safe_path)[0] or "application/octet-stream"

    headers = {
        "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
        "X-Content-Type-Options": "nosniff",
        "Cross-Origin-Resource-Policy": "cross-origin",
    }
    for header in ("etag", "last-modified"):
        if header in upstream.headers:
            headers[header.title()] = upstream.headers[header]

    return Response(
        content=upstream.content,
        status_code=200,
        media_type=content_type.split(";", 1)[0],
        headers=headers,
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:
    candidate = (WEB_DIR / full_path).resolve()
    if candidate.is_file() and WEB_DIR.resolve() in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(WEB_DIR / "index.html")
