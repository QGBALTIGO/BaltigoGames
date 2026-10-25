import importlib
import json

import pytest
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
