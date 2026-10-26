import asyncio
import hashlib
import html
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from app.bot import (_BotUI, _DESCRIPTION, _SHORT_DESCRIPTION, _game_caption, _game_link,
                     _launch_url, _photo_url, _plain, _search_games, start_bot)


APP_URL = "https://games.example/?v=2"
CATALOG = {"games": [
    {"slug": "snake", "name": "Cobrinha", "category": "arcade", "tags": ["clássico"],
     "description": "Recolha maçãs e evite colidir.", "tutorial": "Deslize para mudar a direção."},
    {"slug": "chess", "name": "Xadrez", "category": "board", "tags": ["estratégia"],
     "description": "Proteja o rei e faça xeque-mate."},
    {"slug": "race", "name": "Corrida aérea", "category": "racing", "tags": ["ação"],
     "description": "Desvie dos aviões e alcance a meta."},
]}


def run(awaitable):
    return asyncio.run(awaitable)


def ui(main=False, named="", catalog=CATALOG):
    return _BotUI(APP_URL, lambda: catalog, "BaltigoGamesBot", main, named)


def home_update(chat_type="private"):
    return SimpleNamespace(effective_chat=SimpleNamespace(type=chat_type),
                           effective_message=SimpleNamespace(reply_photo=AsyncMock(), reply_text=AsyncMock()))


def inline_update(query="", offset=""):
    return SimpleNamespace(inline_query=SimpleNamespace(query=query, offset=offset, answer=AsyncMock()))


def wire_result(result):
    # Exercise the SDK's actual wire representation, not only Python attributes.
    return json.loads(result.to_json())


def test_sharing_without_main_mini_app():
    assert _game_link("BaltigoGamesBot", "snake") == "https://t.me/BaltigoGamesBot?start=game_snake"
    assert _game_link("BaltigoGamesBot") == "https://t.me/BaltigoGamesBot?start=games"


def test_sharing_with_main_or_explicit_named_mini_app():
    assert _game_link("BaltigoGamesBot", "snake", True) == "https://t.me/BaltigoGamesBot?startapp=snake"
    assert _game_link("BaltigoGamesBot", has_main_web_app=True) == "https://t.me/BaltigoGamesBot?startapp"
    assert _game_link("@BaltigoGamesBot", "snake", False, "arcade") == "https://t.me/BaltigoGamesBot/arcade?startapp=snake"
    assert _game_link("BaltigoGamesBot", None, False, "arcade") == "https://t.me/BaltigoGamesBot/arcade?startapp"


@pytest.mark.parametrize("slug", ["", "../secret", "snake?x=y", "snake/foo", "UPPER", "jogão", "x" * 60, None])
def test_invalid_game_slugs_never_become_assets_or_deep_links(slug):
    if slug is None:
        with pytest.raises(ValueError):
            _game_link("bad/user", "snake")
        with pytest.raises(ValueError):
            _game_link("BaltigoGamesBot", "snake", named_app_short_name="../app")
    else:
        with pytest.raises(ValueError):
            _game_link("BaltigoGamesBot", slug)
        with pytest.raises(ValueError):
            _photo_url(APP_URL, slug)


def test_launch_selected_game_preserves_other_query_params():
    assert _launch_url(APP_URL, "snake") == "https://games.example/?v=2&startapp=snake"
    assert _launch_url("https://games.example/", None) == "https://games.example/"
    params = parse_qs(urlsplit(_launch_url("https://games.example/?startapp=chess&blank=&v=2#view", "snake")).query,
                      keep_blank_values=True)
    assert params == {"startapp": ["snake"], "v": ["2"], "blank": [""]}


def test_asset_urls_use_public_origin_without_app_query_or_fragment():
    assert _photo_url(APP_URL) == "https://games.example/static/telegram/baltigo-games.jpg"
    assert _photo_url(APP_URL, "snake") == "https://games.example/static/telegram/games/snake.jpg"
    assert _photo_url(APP_URL + "#view", "snake", thumbnail=True) == "https://games.example/static/telegram/thumbs/snake.jpg"


@pytest.mark.parametrize("query,slug", [("cobrinha", "snake"), ("CLÁSSICO", "snake"),
    ("macas", "snake"), ("estrategia", "chess"), ("tabuleiro", "chess"),
    ("acao", "race"), ("corrida aerea", "race"), ("avioes meta", "race"), ("game:snake", "snake")])
def test_search_normalizes_accents_and_checks_all_public_fields(query, slug):
    assert _search_games(CATALOG, query)[0]["slug"] == slug


def test_search_determinism_empty_no_matches_and_invalid_catalog_items():
    catalog = {"games": [{"slug": str(i), "name": str(i)} for i in range(60)]}
    assert len(_search_games(catalog, "")) == 25
    assert _search_games(catalog, "no-game-with-this-name") == []
    assert _search_games(catalog, "", 0) == []
    dirty = {"games": [None, {"slug": "bad/path"}, *CATALOG["games"], CATALOG["games"][0]]}
    assert len(_search_games(dirty, "", 100)) == 3
    tied = {"games": [{"slug": "b", "name": "Ação"}, {"slug": "a", "name": "Acao"}]}
    assert [game["slug"] for game in _search_games(tied, "acao")] == ["a", "b"]


def test_caption_is_short_escaped_portuguese_and_has_no_pictographs():
    caption = _game_caption({"slug": "safe", "name": '<b>Olá & "amigos"</b> 🎮', "category": "shooter",
                             "description": "<script>" + "jogo & " * 300 + "</script>"})
    assert "&lt;b&gt;Olá &amp; &quot;amigos&quot;&lt;/b&gt;" in caption
    assert "<script>" not in caption and "🎮" not in caption
    assert "Tiro" in caption and "<b>Objetivo</b>" in caption and "<b>Baltigo Games</b>" in caption
    assert len(html.unescape(re.sub(r"<[^>]*>", "", caption))) <= 1024
    assert _plain("Toque\npara\tjogar 🎮👍🏽", 80) == "Toque para jogar"
    assert "<b>safe</b>" in _game_caption({"slug": "safe", "name": "🎮"})
    for category, label in (("puzzle", "Quebra-cabeças"), ("casual", "Casuais"), ("3d", "Jogos em 3D")):
        assert f"\n{label}\n" in _game_caption({"slug": "safe", "category": category})


@pytest.mark.parametrize("main", [False, True])
@pytest.mark.parametrize("chat_type", ["private", "group", "supergroup"])
@pytest.mark.parametrize("argument", ["", "game_snake", "not-a-game"])
def test_commands_photo_and_button_contract_in_all_chat_contexts(main, chat_type, argument):
    update = home_update(chat_type)
    run(ui(main).send_home(update, SimpleNamespace(args=[argument] if argument else [])))
    message = update.effective_message.reply_photo.await_args.kwargs
    selected = argument == "game_snake"
    assert message["photo"] == _photo_url(APP_URL, "snake" if selected else None)
    assert message["parse_mode"] == "HTML"
    assert "Baltigo Games" in message["caption"]
    assert ("<b>Cobrinha</b>" in message["caption"]) is selected
    if argument == "not-a-game":
        assert "não está disponível" in message["caption"]
    markup = wire_result(message["reply_markup"])
    button = markup["inline_keyboard"][0][0]
    assert markup["inline_keyboard"][1][0]["switch_inline_query_current_chat"] == ""
    if chat_type == "private":
        assert button["web_app"]["url"] == _launch_url(APP_URL, "snake" if selected else None)
        assert "url" not in button
    else:
        assert "web_app" not in json.dumps(markup)
        assert button["url"] == _game_link("BaltigoGamesBot", "snake" if selected else None, main)
        assert ("no bot" in button["text"]) is (not main)


def test_named_app_group_deep_link_and_channel_safe_keyboard():
    update = home_update("channel")
    run(ui(named="arcade").send_home(update, SimpleNamespace(args=["snake"])))
    markup = wire_result(update.effective_message.reply_photo.await_args.kwargs["reply_markup"])
    assert markup["inline_keyboard"][0][0]["url"] == "https://t.me/BaltigoGamesBot/arcade?startapp=snake"
    assert "switch_inline_query_current_chat" not in json.dumps(markup)
    assert markup["inline_keyboard"][1][0]["switch_inline_query"] == ""


@pytest.mark.parametrize("chat_type", ["private", "group"])
@pytest.mark.parametrize("error_type,message", [
    ("BadRequest", "Not enough rights to send photos to the chat"),
    ("BadRequest", "CHAT_SEND_PHOTOS_FORBIDDEN"),
    ("Forbidden", "Forbidden: CHAT_SEND_MEDIA_FORBIDDEN"),
    ("Forbidden", "Not enough rights to send media messages to the chat"),
])
def test_photo_permission_rejection_falls_back_once_to_same_text_and_keyboard(chat_type, error_type, message):
    from telegram import error

    update = home_update(chat_type)
    update.effective_message.reply_photo.side_effect = getattr(error, error_type)(message)
    run(ui(main=True).send_home(update, SimpleNamespace(args=["game_snake"])))
    photo = update.effective_message.reply_photo.await_args.kwargs
    text = update.effective_message.reply_text.await_args
    assert text.args == (photo["caption"],)
    assert text.kwargs == {"parse_mode": "HTML", "reply_markup": photo["reply_markup"]}
    update.effective_message.reply_photo.assert_awaited_once()
    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.parametrize("error_type,message", [
    ("TimedOut", "Timed out"), ("NetworkError", "CHAT_SEND_PHOTOS_FORBIDDEN"),
    ("Forbidden", "Forbidden: bot was blocked by the user"),
    ("BadRequest", "Wrong type of the web page content"),
    ("BadRequest", "Not enough rights to send messages to the chat"),
    ("BadRequest", "Failed to get HTTP URL content"),
])
def test_uncertain_or_unrelated_photo_errors_propagate_without_duplicate_send(error_type, message):
    from telegram import error

    update = home_update("group")
    failure = getattr(error, error_type)(message)
    update.effective_message.reply_photo.side_effect = failure
    with pytest.raises(type(failure)):
        run(ui().send_home(update, SimpleNamespace(args=[])))
    update.effective_message.reply_photo.assert_awaited_once()
    update.effective_message.reply_text.assert_not_awaited()


def test_text_permission_failure_is_not_swallowed_after_definitive_photo_rejection():
    from telegram.error import BadRequest, Forbidden

    update = home_update("group")
    update.effective_message.reply_photo.side_effect = BadRequest("CHAT_SEND_PHOTOS_FORBIDDEN")
    update.effective_message.reply_text.side_effect = Forbidden("bot was kicked")
    with pytest.raises(Forbidden):
        run(ui().send_home(update, SimpleNamespace(args=[])))
    update.effective_message.reply_text.assert_awaited_once()


@pytest.mark.parametrize("main,named", [(False, ""), (True, ""), (False, "arcade")])
def test_inline_photo_payload_header_and_card_compatibility(main, named):
    update = inline_update("snake")
    run(ui(main, named).inline_query(update, None))
    args = update.inline_query.answer.await_args
    assert len(args.args[0]) == 1
    result = wire_result(args.args[0][0])
    assert result["type"] == "photo"
    assert result["photo_url"] == _photo_url(APP_URL, "snake")
    assert result["thumbnail_url"] == _photo_url(APP_URL, "snake", thumbnail=True)
    assert "input_message_content" not in result  # This would replace the actual photo.
    assert result["parse_mode"] == "HTML" and result["title"] == "Cobrinha"
    assert "Objetivo" in result["caption"] and "Fliperama" in result["caption"]
    assert "web_app" not in json.dumps(result["reply_markup"])
    button = result["reply_markup"]["inline_keyboard"][0][0]
    assert button["url"] == _game_link("BaltigoGamesBot", "snake", main, named)
    assert (button["text"] == "Jogar agora") is bool(main or named)
    header = wire_result(args.kwargs["button"])
    assert header == {"text": "Abrir catálogo de jogos", "web_app": {"url": APP_URL}}
    assert args.kwargs["is_personal"] is False and args.kwargs["cache_time"] == 20
    assert args.kwargs["next_offset"] == ""


def test_inline_pagination_unique_ids_payload_limits_and_final_page():
    slug59 = "x" * 59
    catalog = {"games": [{"slug": f"game-{i:03}", "name": f"Jogo {i}"} for i in range(62)] +
                        [{"slug": slug59, "name": "Nome longo"}]}
    handler = ui(catalog=catalog)
    ids, offset, sizes = [], "", []
    for _ in range(4):
        update = inline_update(offset=offset)
        run(handler.inline_query(update, None))
        args = update.inline_query.answer.await_args
        results = [wire_result(result) for result in args.args[0]]
        sizes.append(len(results))
        for result in results:
            assert 1 <= len(result["id"].encode()) <= 64
            payload = parse_qs(urlsplit(result["reply_markup"]["inline_keyboard"][0][0]["url"]).query)["start"][0]
            assert len(payload.encode()) <= 64
        ids.extend(result["id"] for result in results)
        offset = args.kwargs["next_offset"]
        if not offset:
            break
    assert sizes == [25, 25, 13]
    assert len(ids) == len(set(ids)) == 63


@pytest.mark.parametrize("offset", ["-1", "abc", "1e4", "9" * 1000, "25/../", "01"])
def test_inline_invalid_offsets_reset_safely(offset):
    update = inline_update(offset=offset)
    run(ui().inline_query(update, None))
    assert [result.id for result in update.inline_query.answer.await_args.args[0]] == ["snake", "chess", "race"]


def test_empty_query_results_still_offer_direct_inline_catalog():
    update = inline_update("no game matches")
    run(ui().inline_query(update, None))
    args = update.inline_query.answer.await_args
    assert args.args[0] == [] and args.kwargs["next_offset"] == ""
    assert wire_result(args.kwargs["button"])["web_app"]["url"] == APP_URL
    update = inline_update(offset="999999")
    run(ui().inline_query(update, None))
    assert update.inline_query.answer.await_args.args[0] == []
    run(ui().inline_query(SimpleNamespace(inline_query=None), None))
    run(ui().send_home(SimpleNamespace(effective_message=None), SimpleNamespace(args=[])))


def test_real_catalog_all_games_are_searchable_and_pageable_without_unsafe_ids():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "data/registry.json").read_text(encoding="utf-8"))
    metadata = json.loads((root / "data/catalog-pt.json").read_text(encoding="utf-8"))
    for game in catalog["games"]:
        game.update(metadata.get(game["slug"], {}))
    handler, seen, offset = ui(catalog=catalog), [], ""
    while True:
        update = inline_update(offset=offset)
        run(handler.inline_query(update, None))
        args = update.inline_query.answer.await_args
        seen.extend(result.id for result in args.args[0])
        offset = args.kwargs["next_offset"]
        if not offset:
            break
    assert len(seen) == len(set(seen)) == len(catalog["games"])
    for game in catalog["games"]:
        assert _search_games(catalog, "game:" + game["slug"])[0]["slug"] == game["slug"]


def test_generated_photo_urls_match_packaged_jpeg_manifest_and_payloads():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "web/telegram/manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((root / "data/registry.json").read_text(encoding="utf-8"))
    assert {game["slug"] for game in manifest["games"]} == {game["slug"] for game in catalog["games"]}
    for game in manifest["games"]:
        for field, thumbnail in (("photo", False), ("thumb", True)):
            image = game[field]
            assert _photo_url(APP_URL, game["slug"], thumbnail=thumbnail) == "https://games.example" + image["url"]
            payload = (root / image["path"]).read_bytes()
            assert payload.startswith(b"\xff\xd8\xff") and payload.endswith(b"\xff\xd9")
            assert hashlib.sha256(payload).hexdigest() == image["sha256"]
            assert 0 < len(payload) == image["bytes"] < 5_000_000
    banner = manifest["banner"]
    assert _photo_url(APP_URL) == "https://games.example" + banner["url"]
    payload = (root / banner["path"]).read_bytes()
    assert payload.startswith(b"\xff\xd8\xff") and payload.endswith(b"\xff\xd9")
    assert hashlib.sha256(payload).hexdigest() == banner["sha256"]


def test_startup_registers_handlers_bios_menu_without_network(monkeypatch):
    from telegram.ext import Application, CommandHandler, InlineQueryHandler

    bot = SimpleNamespace(**{name: AsyncMock() for name in (
        "get_me", "set_my_name", "set_my_description", "set_my_short_description",
        "set_my_commands", "set_chat_menu_button")})
    bot.get_me.return_value = SimpleNamespace(username="BaltigoGamesBot", has_main_web_app=False)
    application = SimpleNamespace(bot=bot, initialize=AsyncMock(), add_handler=Mock(), start=AsyncMock(),
                                  updater=SimpleNamespace(start_polling=AsyncMock()))
    builder = Mock()
    builder.token.return_value = builder
    builder.build.return_value = application
    monkeypatch.setattr(Application, "builder", Mock(return_value=builder))
    monkeypatch.setenv("TELEGRAM_MINI_APP_SHORT_NAME", "arcade")
    assert run(start_bot("synthetic-test-token", APP_URL, lambda: CATALOG)) is application
    application.initialize.assert_awaited_once()
    handlers = [call.args[0] for call in application.add_handler.call_args_list]
    commands = next(handler for handler in handlers if isinstance(handler, CommandHandler))
    assert commands.commands == frozenset({"start", "jogar", "games", "home"})
    assert any(isinstance(handler, InlineQueryHandler) for handler in handlers)
    assert commands.callback.__self__.named_app_short_name == "arcade"
    bot.set_my_name.assert_awaited_once_with(name="Baltigo Games")
    bot.set_my_description.assert_awaited_once_with(description=_DESCRIPTION)
    bot.set_my_short_description.assert_awaited_once_with(short_description=_SHORT_DESCRIPTION)
    assert 1 <= len(_DESCRIPTION) <= 512 and 1 <= len(_SHORT_DESCRIPTION) <= 120
    assert all(ord(char) < 0x1F000 for char in _DESCRIPTION + _SHORT_DESCRIPTION)
    assert bot.set_chat_menu_button.await_args.kwargs["menu_button"].web_app.url == APP_URL
    application.updater.start_polling.assert_awaited_once()
    application.start.assert_awaited_once()
