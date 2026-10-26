"""Real SDK/handlers and wire serialization against a local fake Bot API transport."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram import Update
from telegram.ext import Application, Updater
from telegram.request import BaseRequest

from app.bot import _DESCRIPTION, _SHORT_DESCRIPTION, start_bot
from app.bot_transport import ChatUpdateProcessor


APP_URL = "https://games.example"
MEDIA = Path(__file__).resolve().parents[1] / "web" / "telegram"
CATALOG = {"games": [{"slug": "snake", "name": "Cobrinha", "category": "arcade",
                       "description": "Recolha maçãs e evite colidir."}]}


class LocalBotAPI(BaseRequest):
    """Stop at the SDK's public HTTP boundary; never open a network socket."""

    def __init__(self, *, polling=False):
        self.polling = polling
        self.initialized = self.closed = False
        self.calls = []
        self.sent = []
        self.hold_chat = None
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    @property
    def read_timeout(self):
        return 2.0

    async def initialize(self):
        self.initialized = True

    async def shutdown(self):
        self.closed = True

    async def do_request(self, url, method, request_data=None, **kwargs):
        assert not self.polling, "The test must never poll Telegram."
        endpoint = url.rsplit("/", 1)[-1]
        params = request_data.parameters if request_data is not None else {}
        files = request_data.multipart_data if request_data is not None else {}
        call = {"endpoint": endpoint, "params": params, "files": files,
                "contains_files": request_data.contains_files if request_data is not None else False}
        self.calls.append(call)
        if endpoint == "getMe":
            result = {"id": 123456, "is_bot": True, "first_name": "Synthetic Games",
                      "username": "SyntheticGamesBot", "has_main_web_app": True}
        elif endpoint == "getMyName":
            result = {"name": "Baltigo Games"}
        elif endpoint == "getMyDescription":
            result = {"description": _DESCRIPTION}
        elif endpoint == "getMyShortDescription":
            result = {"short_description": _SHORT_DESCRIPTION}
        elif endpoint == "getMyCommands":
            result = [{"command": "jogar", "description": "🎲 Receber uma sugestão ou buscar um jogo"},
                      {"command": "games", "description": "🕹️ Navegar pelo catálogo e categorias"},
                      {"command": "home", "description": "🏠 Voltar ao início"}]
        elif endpoint == "getChatMenuButton":
            result = {"type": "web_app", "text": "🎮 Jogos", "web_app": {"url": APP_URL}}
        elif endpoint == "sendPhoto":
            if self.hold_chat == params["chat_id"] and not self.entered.is_set():
                self.entered.set()
                await self.release.wait()
            if files:
                filename = next(iter(files.values()))[0]
                file_id = "file-snake" if filename == "snake.jpg" else "file-banner"
            else:
                file_id = params["photo"]
            result = {"message_id": len(self.sent) + 100, "date": 1700000000,
                      "chat": {"id": params["chat_id"], "type": "private"},
                      "caption": params["caption"],
                      "photo": [{"file_id": file_id, "file_unique_id": file_id + "-unique",
                                 "width": 640, "height": 360}]}
            self.sent.append(result)
        else:
            raise AssertionError(f"Unexpected fake Bot API method: {endpoint}")
        return 200, json.dumps({"ok": True, "result": result}).encode()


async def initialize_bot(monkeypatch):
    transport, poll = LocalBotAPI(), LocalBotAPI(polling=True)
    original_builder = Application.builder
    monkeypatch.setattr(Application, "builder",
                        lambda: original_builder().request(transport).get_updates_request(poll))
    start = AsyncMock()
    polling = AsyncMock()
    monkeypatch.setattr(Application, "start", start)
    monkeypatch.setattr(Updater, "start_polling", polling)
    monkeypatch.delenv("TELEGRAM_MINI_APP_SHORT_NAME", raising=False)
    app = await start_bot("123456:synthetic-not-real", APP_URL, lambda: CATALOG, media_root=MEDIA)
    errors = []

    async def capture_error(update, context):
        errors.append(context.error)

    app.add_error_handler(capture_error)
    start.assert_awaited_once()
    polling.assert_awaited_once()
    assert isinstance(app.update_processor, ChatUpdateProcessor)
    assert app.concurrent_updates == 64
    assert transport.initialized and poll.initialized
    assert poll.calls == []
    return SimpleNamespace(app=app, transport=transport, poll=poll, errors=errors)


def command(app, chat_id, text, update_id=1):
    raw = {"update_id": update_id, "message": {
        "message_id": update_id, "date": 1700000000,
        "chat": {"id": chat_id, "type": "private"},
        "from": {"id": chat_id, "is_bot": False, "first_name": "Synthetic"},
        "text": text, "entities": [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}],
    }}
    return Update.de_json(raw, app.bot)


async def dispatch(harness, chat_id, text, update_id=1):
    incoming = command(harness.app, chat_id, text, update_id)
    await harness.app.update_processor.process_update(incoming, harness.app.process_update(incoming))


@pytest.mark.asyncio
async def test_real_command_sdk_uploads_multipart_then_reuses_telegram_file_id(monkeypatch):
    harness = await initialize_bot(monkeypatch)
    try:
        await dispatch(harness, 10, "/home")
        await dispatch(harness, 10, "/games", 2)
        sends = [call for call in harness.transport.calls if call["endpoint"] == "sendPhoto"]
        assert len(sends) == 2
        first, second = sends
        assert first["contains_files"] and len(first["files"]) == 1
        filename, content, mimetype = next(iter(first["files"].values()))
        assert filename == "baltigo-games.jpg" and mimetype == "image/jpeg"
        assert content == (MEDIA / filename).read_bytes()
        # sendPhoto uses the named photo multipart part; an attachment URL is
        # needed only when a file is nested in an InputMedia object.
        assert "photo" in first["files"] and "photo" not in first["params"]
        assert not second["contains_files"] and not second["files"]
        assert second["params"]["photo"] == "file-banner"
        assert "Escolha por onde começar" in first["params"]["caption"]
        assert "Catálogo de jogos" in second["params"]["caption"]
        assert harness.errors == []
    finally:
        await harness.app.shutdown()
    assert harness.transport.closed and harness.poll.closed and harness.poll.calls == []


@pytest.mark.asyncio
async def test_real_command_sdk_keeps_game_and_banner_ids_separate(monkeypatch):
    harness = await initialize_bot(monkeypatch)
    try:
        for i, text in enumerate(("/home", "/jogar snake", "/games", "/jogar snake"), 1):
            await dispatch(harness, 20, text, i)
        sends = [call for call in harness.transport.calls if call["endpoint"] == "sendPhoto"]
        assert len(sends) == 4
        assert [call["contains_files"] for call in sends] == [True, True, False, False]
        assert sends[2]["params"]["photo"] == "file-banner"
        assert sends[3]["params"]["photo"] == "file-snake"
        assert "Cobrinha" in sends[1]["params"]["caption"]
        assert harness.errors == []
    finally:
        await harness.app.shutdown()
    assert harness.poll.calls == []


@pytest.mark.asyncio
async def test_real_commands_parallel_between_chats_and_ordered_within_one_chat(monkeypatch):
    harness = await initialize_bot(monkeypatch)
    harness.transport.hold_chat = 10
    first = second = third = None
    try:
        first = asyncio.create_task(dispatch(harness, 10, "/home", 1))
        await asyncio.wait_for(harness.transport.entered.wait(), 2)
        second = asyncio.create_task(dispatch(harness, 20, "/home", 2))
        await asyncio.wait_for(second, 2)
        assert not first.done()
        third = asyncio.create_task(dispatch(harness, 10, "/games", 3))
        await asyncio.sleep(0)
        assert not third.done()
        sends = [call for call in harness.transport.calls if call["endpoint"] == "sendPhoto"]
        assert [call["params"]["chat_id"] for call in sends] == [10, 20]
        assert [message["chat"]["id"] for message in harness.transport.sent] == [20]
        harness.transport.release.set()
        await asyncio.wait_for(asyncio.gather(first, third), 2)
        sends = [call for call in harness.transport.calls if call["endpoint"] == "sendPhoto"]
        assert [call["params"]["chat_id"] for call in sends] == [10, 20, 10]
        assert sends[2]["params"]["photo"] == "file-banner"
        assert "Catálogo de jogos" in sends[2]["params"]["caption"]
        assert [message["chat"]["id"] for message in harness.transport.sent] == [20, 10, 10]
        assert harness.errors == []
        assert harness.app.update_processor.current_concurrent_updates == 0
    finally:
        harness.transport.release.set()
        pending = [task for task in (first, second, third) if task is not None]
        await asyncio.gather(*pending, return_exceptions=True)
        await harness.app.shutdown()
    assert harness.poll.calls == []
