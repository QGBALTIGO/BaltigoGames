from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_telegram_sdk_and_mobile_viewport_present():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "telegram-web-app.js" in html
    assert "viewport-fit=cover" in html
    assert 'id="player"' in html
    assert 'id="categoryStrip"' in html


def test_deeplink_fullscreen_inline_hooks_present():
    js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    for token in ["start_param", "tgWebAppStartParam", "requestFullscreen", "BackButton", "switchInlineQuery", "disableVerticalSwipes"]:
        assert token in js


def test_no_hardcoded_bot_token():
    for path in list((ROOT / "app").glob("*.py")) + list((ROOT / "web").glob("*.*")):
        text = path.read_text(encoding="utf-8")
        assert "bot" not in text.lower() or "AAG" not in text
