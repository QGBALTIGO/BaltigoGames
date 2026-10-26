"""Independent startup gate: no Telegram network or real bot is initialized."""
import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import (BotCommand, BotDescription, BotName, BotShortDescription,
                      MenuButtonDefault, MenuButtonWebApp, WebAppInfo)
from telegram.error import BadRequest, Forbidden, InvalidToken, NetworkError, RetryAfter, TimedOut

from app.bot import _DESCRIPTION, _SHORT_DESCRIPTION, start_bot


APP_URL = "https://games.example/?release=resilience"
TOKEN = "synthetic-startup-token-not-real"
COMMANDS = [BotCommand("jogar", "🎲 Receber uma sugestão ou buscar um jogo"),
            BotCommand("games", "🕹️ Navegar pelo catálogo e categorias"),
            BotCommand("home", "🏠 Voltar ao início")]
MENU = MenuButtonWebApp(text="🎮 Jogos", web_app=WebAppInfo(APP_URL))
PROFILE = [
    ("get_my_name", "set_my_name", BotName("Baltigo Games"), {"name": "Baltigo Games"}),
    ("get_my_description", "set_my_description", BotDescription(_DESCRIPTION), {"description": _DESCRIPTION}),
    ("get_my_short_description", "set_my_short_description", BotShortDescription(_SHORT_DESCRIPTION), {"short_description": _SHORT_DESCRIPTION}),
    ("get_my_commands", "set_my_commands", tuple(COMMANDS), {"commands": COMMANDS}),
    ("get_chat_menu_button", "set_chat_menu_button", MENU, {"menu_button": MENU}),
]
DIFFERENT = [BotName("Previous name"), BotDescription("Previous description"),
             BotShortDescription("Previous short description"), (), MenuButtonDefault()]


def fake_startup(monkeypatch):
    from telegram.ext import Application

    events = []
    bot = SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username="StartupGamesBot", has_main_web_app=True)))
    for getter, setter, current, _ in PROFILE:
        setattr(bot, getter, AsyncMock(return_value=current))
        setattr(bot, setter, AsyncMock())
    updater = SimpleNamespace(running=False)
    app = SimpleNamespace(bot=bot, running=False, initialize=AsyncMock(), add_handler=Mock(), updater=updater)
    async def start_polling(**kwargs):
        events.append("polling")
        updater.running = True
    async def start_app():
        events.append("app")
        app.running = True
    updater.start_polling = AsyncMock(side_effect=start_polling)
    app.start = AsyncMock(side_effect=start_app)
    builder = Mock()
    builder.token.return_value = builder
    builder.build.return_value = app
    monkeypatch.setattr(Application, "builder", Mock(return_value=builder))
    monkeypatch.delenv("TELEGRAM_MINI_APP_SHORT_NAME", raising=False)
    # An optional profile failure must not add retry sleeps before starting the service.
    sleep = AsyncMock(side_effect=AssertionError("Startup must not sleep for optional profile failures"))
    monkeypatch.setattr(asyncio, "sleep", sleep)
    return SimpleNamespace(app=app, bot=bot, events=events, sleep=sleep)


def start(fake):
    result = asyncio.run(start_bot(TOKEN, APP_URL, lambda: {"games": []}))
    assert result is fake.app and fake.app.running and fake.app.updater.running
    assert fake.events == ["polling", "app"]
    fake.app.initialize.assert_awaited_once()
    fake.bot.get_me.assert_awaited_once()
    fake.app.updater.start_polling.assert_awaited_once()
    fake.app.start.assert_awaited_once()
    fake.sleep.assert_not_awaited()
    return result


def test_identical_profile_performs_no_optional_setters(monkeypatch):
    fake = fake_startup(monkeypatch)
    start(fake)
    for getter, setter, _, _ in PROFILE:
        getattr(fake.bot, getter).assert_awaited_once_with()
        getattr(fake.bot, setter).assert_not_awaited()


@pytest.mark.parametrize("index", range(5), ids=[item[1] for item in PROFILE])
def test_only_the_changed_profile_field_is_updated(monkeypatch, index):
    fake = fake_startup(monkeypatch)
    getattr(fake.bot, PROFILE[index][0]).return_value = DIFFERENT[index]
    start(fake)
    for position, (getter, setter, _, expected) in enumerate(PROFILE):
        getattr(fake.bot, getter).assert_awaited_once_with()
        operation = getattr(fake.bot, setter)
        if position == index:
            operation.assert_awaited_once_with(**expected)
        else:
            operation.assert_not_awaited()


@pytest.mark.parametrize("index", range(5), ids=[item[1] for item in PROFILE])
def test_each_optional_setter_retry_after_still_starts_polling(monkeypatch, caplog, index):
    fake = fake_startup(monkeypatch)
    getter, setter, _, _ = PROFILE[index]
    getattr(fake.bot, getter).return_value = DIFFERENT[index]
    getattr(fake.bot, setter).side_effect = RetryAfter(23)
    with caplog.at_level(logging.WARNING):
        start(fake)
    getattr(fake.bot, setter).assert_awaited_once()
    for position, (get_name, set_name, _, _) in enumerate(PROFILE):
        if position <= index:
            getattr(fake.bot, get_name).assert_awaited_once()
        else:
            getattr(fake.bot, get_name).assert_not_awaited()
        if position != index:
            getattr(fake.bot, set_name).assert_not_awaited()
    assert setter in caplog.text and "23" in caplog.text
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("index", range(5), ids=[item[0] for item in PROFILE])
def test_each_optional_getter_retry_after_still_starts_polling(monkeypatch, caplog, index):
    fake = fake_startup(monkeypatch)
    getter = PROFILE[index][0]
    getattr(fake.bot, getter).side_effect = RetryAfter(31)
    with caplog.at_level(logging.WARNING):
        start(fake)
    for position, (get_name, set_name, _, _) in enumerate(PROFILE):
        if position <= index:
            getattr(fake.bot, get_name).assert_awaited_once()
        else:
            getattr(fake.bot, get_name).assert_not_awaited()
        getattr(fake.bot, set_name).assert_not_awaited()
    assert getter in caplog.text and "31" in caplog.text
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("phase", ["initialize", "get_me", "start_polling", "start"])
def test_required_startup_failures_propagate_instead_of_returning_healthy(monkeypatch, phase):
    fake = fake_startup(monkeypatch)
    failure = InvalidToken("isolated invalid credential") if phase == "get_me" else NetworkError("isolated required startup failure")
    target = (fake.bot.get_me if phase == "get_me" else fake.app.updater.start_polling
              if phase == "start_polling" else getattr(fake.app, phase))
    target.side_effect = failure
    with pytest.raises(type(failure)) as caught:
        asyncio.run(start_bot(TOKEN, APP_URL, lambda: {"games": []}))
    assert caught.value is failure and not fake.app.running
    fake.sleep.assert_not_awaited()
    if phase in {"initialize", "get_me"}:
        fake.app.updater.start_polling.assert_not_awaited()
    if phase != "start":
        fake.app.start.assert_not_awaited()


@pytest.mark.parametrize("index", range(5), ids=[item[0] for item in PROFILE])
@pytest.mark.parametrize("operation", ["getter", "setter"])
@pytest.mark.parametrize("error_type", [TimedOut, NetworkError])
def test_transient_optional_profile_failure_stops_batch_but_starts_bot(monkeypatch, caplog, index, operation, error_type):
    fake = fake_startup(monkeypatch)
    getter, setter, _, expected = PROFILE[index]
    sensitive_details = "synthetic-sensitive-profile-detail-do-not-log"
    failure = error_type(sensitive_details)
    failed_operation = getter if operation == "getter" else setter
    if operation == "setter":
        getattr(fake.bot, getter).return_value = DIFFERENT[index]
    getattr(fake.bot, failed_operation).side_effect = failure
    with caplog.at_level(logging.WARNING):
        start(fake)

    # The failed operation is attempted once, then polling starts without trying
    # later optional fields, sleeps, or a network retry from this reconciliation.
    for position, (get_name, set_name, _, _) in enumerate(PROFILE):
        if position <= index:
            getattr(fake.bot, get_name).assert_awaited_once_with()
        else:
            getattr(fake.bot, get_name).assert_not_awaited()
        if position == index and operation == "setter":
            getattr(fake.bot, set_name).assert_awaited_once_with(**expected)
        else:
            getattr(fake.bot, set_name).assert_not_awaited()
    assert failed_operation in caplog.text and error_type.__name__ in caplog.text
    assert sensitive_details not in caplog.text and TOKEN not in caplog.text
    assert "retry_after_seconds=" not in caplog.text
    assert "RetryAfter" not in caplog.text
    fake.sleep.assert_not_awaited()


@pytest.mark.parametrize("index", range(5), ids=[item[0] for item in PROFILE])
@pytest.mark.parametrize("operation", ["getter", "setter"])
@pytest.mark.parametrize("error_type", [BadRequest, Forbidden, InvalidToken])
def test_permanent_optional_profile_errors_propagate(monkeypatch, index, operation, error_type):
    fake = fake_startup(monkeypatch)
    getter, setter, _, _ = PROFILE[index]
    failure = error_type("isolated permanent configuration failure")
    failed_operation = getter if operation == "getter" else setter
    if operation == "setter":
        getattr(fake.bot, getter).return_value = DIFFERENT[index]
    getattr(fake.bot, failed_operation).side_effect = failure
    with pytest.raises(error_type) as caught:
        asyncio.run(start_bot(TOKEN, APP_URL, lambda: {"games": []}))
    assert caught.value is failure
    getattr(fake.bot, failed_operation).assert_awaited_once()
    fake.app.updater.start_polling.assert_not_awaited()
    fake.app.start.assert_not_awaited()
    fake.sleep.assert_not_awaited()
