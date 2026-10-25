from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram.ext import CommandHandler, InlineQueryHandler
from app.bot import start_bot


@pytest.fixture
def fake_application(monkeypatch):
    from telegram.ext import Application
    application = MagicMock()
    application.initialize = AsyncMock()
    application.start = AsyncMock()
    application.updater.start_polling = AsyncMock()
    application.bot.get_me = AsyncMock(return_value=SimpleNamespace(username="ExampleBot", has_main_web_app=False))
    application.bot.set_my_commands = AsyncMock()
    application.bot.set_chat_menu_button = AsyncMock()
    builder = MagicMock()
    builder.token.return_value = builder
    builder.build.return_value = application
    monkeypatch.setattr(Application, "builder", lambda: builder)
    return application


CATALOG = {"games": [{"slug": "snake", "name": "Snake", "category": "arcade"}]}


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type,argument", [("private", None), ("private", "game_snake"), ("group", None), ("private", "game_missing")])
async def test_start_handler(fake_application, chat_type, argument):
    app = await start_bot("test-token", "https://games.example", lambda: CATALOG)
    handler = next(call.args[0] for call in app.add_handler.call_args_list if isinstance(call.args[0], CommandHandler))
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message, effective_chat=SimpleNamespace(type=chat_type))
    await handler.callback(update, SimpleNamespace(args=[argument] if argument else []))
    call = message.reply_text.call_args
    button = call.kwargs["reply_markup"].inline_keyboard[0][0]
    if chat_type == "private":
        expected = "https://games.example?startapp=snake" if argument == "game_snake" else "https://games.example"
        assert button.web_app.url == expected
    else:
        assert button.web_app is None
        assert button.url == "https://t.me/ExampleBot?start=games"
    assert {command.command for command in app.bot.set_my_commands.call_args.args[0]} == {"jogar", "games"}
    assert app.bot.set_chat_menu_button.call_args.kwargs["menu_button"].web_app.url == "https://games.example"


@pytest.mark.asyncio
async def test_inline_handler_shares_selected_game(fake_application):
    app = await start_bot("test-token", "https://games.example", lambda: CATALOG)
    handler = next(call.args[0] for call in app.add_handler.call_args_list if isinstance(call.args[0], InlineQueryHandler))
    query = SimpleNamespace(query="game:snake", answer=AsyncMock())
    await handler.callback(SimpleNamespace(inline_query=query), None)
    results = query.answer.call_args.args[0]
    assert len(results) == 1
    assert results[0].reply_markup.inline_keyboard[0][0].url == "https://t.me/ExampleBot?start=game_snake"
    assert query.answer.call_args.kwargs["button"].web_app.url == "https://games.example"
