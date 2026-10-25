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
    monkeypatch.delenv("GAME_ASSET_ACCEL", raising=False)
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
@pytest.mark.parametrize("accelerated", [False, True])
def test_game_aliases_return_adapted_document_and_relative_assets(client, tmp_path, monkeypatch, prefix, accelerated):
    c, main = client
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", accelerated)
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
    (game / "styles.css").write_text("body{background:#123456}", encoding="utf-8")
    monkeypatch.setattr(main, "UPSTREAM_LOCAL_DIR", mirror)

    document = c.get(f"/{prefix}/games/arcade/cache-proof/index.html")
    assert document.status_code == 200
    assert '<meta name="baltigo-adapter"' in document.text
    assert 'data-actual-game="cache-proof"' in document.text
    assert '<html lang="pt-BR">' in document.text
    assert 'src="mechanics.js"' in document.text
    assert document.headers["cache-control"] == "public, max-age=3600"
    assert "x-accel-redirect" not in document.headers
    script = c.get(f"/{prefix}/games/arcade/cache-proof/mechanics.js")
    assert script.status_code == 200
    assert "window.actualGameAsset='cache-proof'" in script.text
    assert script.headers["content-type"].startswith("text/javascript")
    assert "x-accel-redirect" not in script.headers
    config = c.get(f"/{prefix}/games/arcade/cache-proof/config.json")
    assert config.status_code == 200
    assert config.json() == {"actual_config": "cache-proof"}
    assert "x-accel-redirect" not in config.headers
    styles = c.get(f"/{prefix}/games/arcade/cache-proof/styles.css")
    assert styles.status_code == 200 and styles.text == "body{background:#123456}"
    assert styles.headers["content-type"].startswith("text/css")
    assert styles.headers["cache-control"] == "public, max-age=3600"
    assert "x-accel-redirect" not in styles.headers


@pytest.mark.parametrize("accelerated", [False, True])
def test_local_binary_delivery_is_optional_and_validated(client, tmp_path, monkeypatch, accelerated):
    c, main = client
    mirror = tmp_path / "mirror"
    asset = mirror / "games/arcade/proof/assets/obj 1.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"\x89PNG\r\n\x1a\npublic-test-content")
    monkeypatch.setattr(main, "UPSTREAM_LOCAL_DIR", mirror)
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", accelerated)
    response = c.get("/play-v3/games/arcade/proof/assets/obj%201.png", headers={
        "Cookie": "session=private", "Authorization": "Bearer private",
    })
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "set-cookie" not in response.headers
    if accelerated:
        assert response.content == b""
        assert "content-length" not in response.headers
        assert response.headers["x-accel-redirect"] == "/_baltigo_game_assets/games/arcade/proof/assets/obj%201.png"
    else:
        assert response.content == asset.read_bytes()
        assert "x-accel-redirect" not in response.headers
        assert response.headers["content-length"] == str(asset.stat().st_size)
        ranged = c.get("/play-v3/games/arcade/proof/assets/obj%201.png", headers={"Range": "bytes=0-7"})
        assert ranged.status_code == 206 and ranged.content == asset.read_bytes()[:8]


@pytest.mark.parametrize("accelerated", [False, True])
def test_replacement_artwork_keeps_real_svg_type(client, tmp_path, monkeypatch, accelerated):
    c, main = client
    web = tmp_path / "web"
    artwork = web / "game-art/cena pt.svg"
    artwork.parent.mkdir(parents=True)
    artwork.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>PERIGO</text></svg>', encoding="utf-8")
    monkeypatch.setattr(main, "WEB_DIR", web)
    monkeypatch.setattr(main, "ASSET_REPLACEMENTS", {"games/3d/proof/assets/warning.png": "game-art/cena pt.svg"})
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", accelerated)
    response = c.get("/play-v3/games/3d/proof/assets/warning.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert "set-cookie" not in response.headers
    if accelerated:
        assert response.content == b""
        assert response.headers["x-accel-redirect"] == "/_baltigo_game_art/game-art/cena%20pt.svg"
    else:
        assert response.content == artwork.read_bytes()
        assert "x-accel-redirect" not in response.headers


@pytest.mark.parametrize("accelerated", [False, True])
def test_local_font_fallback_redirects_to_actual_font(client, tmp_path, monkeypatch, accelerated):
    c, main = client
    mirror = tmp_path / "mirror"
    font = mirror / "games/arcade/snake/outfit.ttf"
    font.parent.mkdir(parents=True)
    font.write_bytes(b"real-shared-font")
    monkeypatch.setattr(main, "UPSTREAM_LOCAL_DIR", mirror)
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", accelerated)
    response = c.get("/play-v3/games/sports/proof/outfit.ttf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "font/ttf"
    if accelerated:
        assert response.headers["x-accel-redirect"] == "/_baltigo_game_assets/games/arcade/snake/outfit.ttf"
    else:
        assert response.content == font.read_bytes()


def test_acceleration_rejects_traversal_and_outside_files(client, tmp_path, monkeypatch):
    c, main = client
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    outside = tmp_path / "private.png"
    outside.write_bytes(b"must-not-be-served")
    monkeypatch.setattr(main, "UPSTREAM_LOCAL_DIR", mirror)
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", True)
    response = c.get("/play-v3/games/%2e%2e/private.png")
    assert response.status_code == 400 and "x-accel-redirect" not in response.headers
    with pytest.raises(main.HTTPException):
        main.local_game_asset(outside, mirror, "/_baltigo_game_assets/", "image/png", {})


def test_acceleration_rejects_escaping_symlinks(client, tmp_path, monkeypatch):
    c, main = client
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    outside = tmp_path / "private.png"
    outside.write_bytes(b"must-not-be-served")
    monkeypatch.setattr(main, "UPSTREAM_LOCAL_DIR", mirror)
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", True)
    linked = mirror / "games/arcade/proof/outside.png"
    linked.parent.mkdir(parents=True)
    try:
        linked.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation unavailable on this host; traversal/root check was verified")
    response = c.get("/play-v3/games/arcade/proof/outside.png")
    assert response.status_code == 400 and "x-accel-redirect" not in response.headers


def test_acceleration_rejects_invalid_artwork_mapping(client, tmp_path, monkeypatch):
    c, main = client
    web = tmp_path / "web"
    web.mkdir()
    outside = tmp_path / "private.svg"
    outside.write_text("private", encoding="utf-8")
    monkeypatch.setattr(main, "WEB_DIR", web)
    monkeypatch.setattr(main, "ASSET_REPLACEMENTS", {"games/3d/proof/warning.png": "../private.svg"})
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", True)
    response = c.get("/play-v3/games/3d/proof/warning.png")
    assert response.status_code == 503 and "x-accel-redirect" not in response.headers
    assert response.content != outside.read_bytes()


def test_acceleration_does_not_redirect_upstream_fallback(client, tmp_path, monkeypatch):
    c, main = client
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    monkeypatch.setattr(main, "UPSTREAM_LOCAL_DIR", mirror)
    monkeypatch.setattr(main, "GAME_ASSET_ACCEL", True)
    monkeypatch.setattr(main, "_proxy_client", httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"upstream-image", headers={"content-type": "image/png"}))))
    response = c.get("/play-v3/games/arcade/proof/missing.png")
    assert response.status_code == 200 and response.content == b"upstream-image"
    assert "x-accel-redirect" not in response.headers


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
