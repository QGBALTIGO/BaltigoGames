import importlib
import json

import pytest
import httpx
from types import SimpleNamespace
from fastapi.testclient import TestClient

FIXTURE = {
    "version": 1,
    "categories": [{"id": "arcade", "label": "Arcade", "emoji": "🕹️"}],
    "games": [{"slug": "snake", "name": "Snake", "category": "arcade", "path": "games/arcade/snake/index.html", "tech": "phaser", "tags": ["classic"]}],
}

@pytest.fixture()
def client(tmp_path, monkeypatch):
    catalog = tmp_path / "registry.json"
    catalog.write_text(json.dumps(FIXTURE), encoding="utf-8")
    monkeypatch.setenv("CATALOG_FILE", str(catalog))
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    import app.main as main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c, main


def test_health(client):
    c, _ = client
    body = c.get("/health").json()
    assert body["ok"] is True
    assert body["games"] == 1
    assert body["bot_configured"] is False


def test_catalog(client):
    c, _ = client
    r = c.get("/api/catalog")
    assert r.status_code == 200
    assert r.json()["games"][0]["slug"] == "snake"
    assert "max-age" in r.headers["cache-control"]


def test_proxy_path_validation(client):
    _, main = client
    assert main.sanitize_proxy_path("games/arcade/snake/index.html") == "games/arcade/snake/index.html"
    for bad in ["../secret", "assets/x.png", "games/../secret", "/../../etc/passwd"]:
        with pytest.raises(ValueError):
            main.sanitize_proxy_path(bad)


def test_railway_url(monkeypatch):
    import app.main as main
    monkeypatch.delenv("APP_URL", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "baltigo-games.up.railway.app")
    assert main.public_app_url() == "https://baltigo-games.up.railway.app"


def test_inline_search_ranking():
    from app.bot import _search_games
    catalog = {"games": [
        {"slug": "snake", "name": "Snake", "category": "arcade", "tags": ["classic"]},
        {"slug": "curve-snake", "name": "Curve Snake", "category": "arcade", "tags": ["snake"]},
        {"slug": "chess", "name": "Chess", "category": "board", "tags": ["strategy"]},
    ]}
    assert _search_games(catalog, "game:snake")[0]["slug"] == "snake"
    assert [g["slug"] for g in _search_games(catalog, "chess")] == ["chess"]


def test_health_detects_bot_stopped(client, monkeypatch):
    c, main = client
    monkeypatch.setattr(main, "BOT_TOKEN", "test-only")
    monkeypatch.setattr(main, "_bot_application", None)
    response = c.get("/health")
    assert response.status_code == 503
    assert response.json()["ok"] is False
    assert response.json()["bot_running"] is False


def test_health_detects_bot_polling(client, monkeypatch):
    c, main = client
    monkeypatch.setattr(main, "BOT_TOKEN", "test-only")
    bot = SimpleNamespace(running=True, updater=SimpleNamespace(running=True))
    monkeypatch.setattr(main, "_bot_application", bot)
    assert c.get("/health").json()["bot_running"] is True
    bot.updater.running = False
    assert c.get("/health").status_code == 503
    monkeypatch.setattr(main, "_bot_application", None)


@pytest.mark.parametrize("status,expected", [(404, 404), (403, 502), (500, 502), (503, 502)])
def test_proxy_upstream_errors(client, monkeypatch, status, expected):
    c, main = client
    transport = httpx.MockTransport(lambda req: httpx.Response(status, text="upstream"))
    monkeypatch.setattr(main, "_proxy_client", httpx.AsyncClient(transport=transport))
    response = c.get("/play/games/arcade/snake/index.html")
    assert response.status_code == expected
    assert response.headers.get("cache-control") is None


def test_proxy_network_failure(client, monkeypatch):
    c, main = client
    def fail(request):
        raise httpx.ConnectError("offline", request=request)
    monkeypatch.setattr(main, "_proxy_client", httpx.AsyncClient(transport=httpx.MockTransport(fail)))
    assert c.get("/play/games/arcade/snake/index.html").status_code == 502


@pytest.mark.parametrize("prefix", ["play", "play-v2", "play-v3"])
def test_proxy_asset_and_private_headers(client, monkeypatch, prefix):
    c, main = client
    seen = []
    def respond(request):
        seen.append(request)
        return httpx.Response(200, content=b"game bytes", headers={
            "content-type": "text/javascript; charset=utf-8", "etag": "abc",
            "set-cookie": "private=value", "last-modified": "Wed, 21 Oct 2026 07:28:00 GMT",
        })
    monkeypatch.setattr(main, "_proxy_client", httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    response = c.get(f"/{prefix}/games/arcade/snake/main.js?v=2", headers={
        "Cookie": "session=private", "Authorization": "Bearer private",
    })
    assert response.status_code == 200
    assert response.content == b"game bytes"
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["etag"] == "abc"
    assert "set-cookie" not in response.headers
    assert "cookie" not in seen[0].headers
    assert "authorization" not in seen[0].headers
    assert seen[0].url.query == b"v=2"


@pytest.mark.parametrize("prefix", ["play", "play-v2", "play-v3"])
def test_game_aliases_return_adapted_document_and_relative_assets(client, tmp_path, monkeypatch, prefix):
    c, main = client
    mirror = tmp_path / "mirror"
    game = mirror / "games/arcade/cache-proof"
    game.mkdir(parents=True)
    (game / "index.html").write_text(
        '<html lang="en"><head><title>Cache route proof</title></head>'
        '<body data-actual-game="cache-proof"><script src="mechanics.js"></script></body></html>',
        encoding="utf-8",
    )
    (game / "mechanics.js").write_text("window.actualGameAsset='cache-proof';", encoding="utf-8")
    (game / "config.json").write_text('{"actual_config":"cache-proof"}', encoding="utf-8")
    monkeypatch.setattr(main, "UPSTREAM_LOCAL_DIR", mirror)

    document = c.get(f"/{prefix}/games/arcade/cache-proof/index.html")
    assert document.status_code == 200
    assert '<meta name="baltigo-adapter"' in document.text
    assert 'data-actual-game="cache-proof"' in document.text
    assert '<html lang="pt-BR">' in document.text
    assert 'src="mechanics.js"' in document.text
    assert document.headers["cache-control"] == "public, max-age=3600"
    script = c.get(f"/{prefix}/games/arcade/cache-proof/mechanics.js")
    assert script.status_code == 200
    assert "window.actualGameAsset='cache-proof'" in script.text
    assert script.headers["content-type"].startswith("text/javascript")
    config = c.get(f"/{prefix}/games/arcade/cache-proof/config.json")
    assert config.status_code == 200
    assert config.json() == {"actual_config": "cache-proof"}


@pytest.mark.parametrize("path", ["assets/main.js", "secret.env", "games/../secret", "games\\..\\secret"])
def test_proxy_rejects_invalid_paths(client, path):
    _, main = client
    with pytest.raises(ValueError):
        main.sanitize_proxy_path(path)


def test_config_has_no_token(client, monkeypatch):
    c, main = client
    monkeypatch.setattr(main, "BOT_TOKEN", "test-only-secret")
    response = c.get("/api/config")
    assert response.json()["telegram_enabled"] is True
    assert "test-only-secret" not in response.text
    assert response.json()["access"] == {"mode": "free", "lives_limited": False}
    assert response.json()["features"]["payments"] is False
    assert response.json()["features"]["versus"] is False


def test_bot_http_logs_suppressed(client):
    import logging
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING


def test_missing_shared_font_uses_upstream_copy(client, monkeypatch):
    c, main = client
    seen = []
    def respond(request):
        seen.append(str(request.url))
        if request.url.path.endswith("/games/arcade/snake/outfit.ttf"):
            return httpx.Response(200, content=b"font bytes", headers={"content-type": "font/ttf"})
        return httpx.Response(404)
    monkeypatch.setattr(main, "_proxy_client", httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    response = c.get("/play/games/puzzle/outfit.ttf")
    assert response.status_code == 200
    assert response.content == b"font bytes"
    assert response.headers["content-type"] == "font/ttf"
    assert len(seen) == 2


def test_game_config_overrides_remove_missing_preloads(client):
    c, _ = client
    snake = c.get("/play/games/arcade/snake/config.json")
    assert snake.status_code == 200
    assert snake.json()["spritesheets"] == {}
    assert snake.json()["images1"]["body"] == "assets/body.png"
    chess = c.get("/play/games/board/chess/config.json").json()
    assert "attack" not in chess["ui"]
    assert chess["ui"]["playbtn"] == "assets/images/playbtn.png"
