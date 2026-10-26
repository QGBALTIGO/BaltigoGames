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


def test_caption_is_short_escaped_portuguese_with_one_chosen_game_emoji():
    caption = _game_caption({"slug": "safe", "name": '<b>Olá & "amigos"</b> 🎮', "category": "shooter",
                             "description": "<script>" + "jogo & " * 300 + "</script>"})
    assert "&lt;b&gt;Olá &amp; &quot;amigos&quot;&lt;/b&gt;" in caption
    assert "<script>" not in caption and caption.count("🎮") == 1
    assert "Tiro" in caption and "<b>Objetivo</b>" in caption and "<b>Baltigo Games</b>" in caption
    assert len(html.unescape(re.sub(r"<[^>]*>", "", caption))) <= 1024
    assert _plain("Toque\npara\tjogar 🎮👍🏽", 80) == "Toque para jogar"
    assert "<b>🎮 safe</b>" in _game_caption({"slug": "safe", "name": "🎮"})
    for category, label in (("puzzle", "Quebra-cabeças"), ("casual", "Casuais"), ("3d", "Jogos em 3D")):
        assert f"\n{label}\n" in _game_caption({"slug": "safe", "category": category})


@pytest.mark.parametrize("main", [False, True])
@pytest.mark.parametrize("chat_type", ["private", "group", "supergroup"])
@pytest.mark.parametrize("argument", ["", "game_snake", "game_missing"])
def test_commands_photo_and_button_contract_in_all_chat_contexts(main, chat_type, argument):
    update = home_update(chat_type)
    run(ui(main).send_start(update, SimpleNamespace(args=[argument] if argument else [])))
    message = update.effective_message.reply_photo.await_args.kwargs
    selected = argument == "game_snake"
    assert message["photo"] == _photo_url(APP_URL, "snake" if selected else None)
    assert message["parse_mode"] == "HTML"
    assert "Baltigo Games" in message["caption"]
    assert ("<b>🎮 Cobrinha</b>" in message["caption"]) is selected
    markup = wire_result(message["reply_markup"])
    buttons = [button for row in markup["inline_keyboard"] for button in row]
    assert any(button.get("switch_inline_query_current_chat") == "" for button in buttons)
    if argument == "game_missing":
        assert "Não encontrei" in message["caption"]
        assert not any("web_app" in button or "url" in button for button in buttons)
        assert {button.get("callback_data") for button in buttons} >= {"bg:home", "bg:games:all:0"}
        return
    button = buttons[0]
    if chat_type == "private":
        assert button["web_app"]["url"] == _launch_url(APP_URL, "snake" if selected else None)
        assert "url" not in button
    else:
        assert "web_app" not in json.dumps(markup)
        assert button["url"] == _game_link("BaltigoGamesBot", "snake" if selected else None, main)
        assert ("no bot" in button["text"]) is (not main)


def test_named_app_group_deep_link_and_channel_safe_keyboard():
    update = home_update("channel")
    run(ui(named="arcade").send_play(update, SimpleNamespace(args=["snake"])))
    markup = wire_result(update.effective_message.reply_photo.await_args.kwargs["reply_markup"])
    assert markup["inline_keyboard"][0][0]["url"] == "https://t.me/BaltigoGamesBot/arcade?startapp=snake"
    assert "switch_inline_query_current_chat" not in json.dumps(markup)
    assert any(button.get("switch_inline_query") == "" for row in markup["inline_keyboard"] for button in row)


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
    run(ui(main=True).send_start(update, SimpleNamespace(args=["game_snake"])))
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
    assert (button["text"] == "🎮 Jogar agora") is bool(main or named)
    header = wire_result(args.kwargs["button"])
    assert header == {"text": "🕹️ Abrir catálogo de jogos", "web_app": {"url": APP_URL}}
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
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, InlineQueryHandler

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
    assert commands.commands == frozenset({"start"})
    assert {tuple(sorted(handler.commands)) for handler in handlers if isinstance(handler, CommandHandler)} == {
        ("home",), ("start",), ("games",), ("jogar",)}
    assert len({handler.callback.__name__ for handler in handlers if isinstance(handler, CommandHandler)}) == 4
    assert any(isinstance(handler, CallbackQueryHandler) for handler in handlers)
    assert any(isinstance(handler, InlineQueryHandler) for handler in handlers)
    assert commands.callback.__self__.named_app_short_name == "arcade"
    bot.set_my_name.assert_awaited_once_with(name="Baltigo Games")
    bot.set_my_description.assert_awaited_once_with(description=_DESCRIPTION)
    bot.set_my_short_description.assert_awaited_once_with(short_description=_SHORT_DESCRIPTION)
    assert 1 <= len(_DESCRIPTION) <= 512 and 1 <= len(_SHORT_DESCRIPTION) <= 120
    assert "🎮" in _DESCRIPTION and "🎮" in _SHORT_DESCRIPTION
    assert bot.set_chat_menu_button.await_args.kwargs["menu_button"].web_app.url == APP_URL
    assert bot.set_chat_menu_button.await_args.kwargs["menu_button"].text == "🎮 Jogos"
    application.updater.start_polling.assert_awaited_once()
    application.start.assert_awaited_once()


def callback_update(data, chat_type='private', *, caption=None, photo=True):
    message = SimpleNamespace(photo=[object()] if photo else [], caption=caption, text=None,
                              reply_photo=AsyncMock(), reply_text=AsyncMock())
    query = SimpleNamespace(data=data, message=message, answer=AsyncMock(),
                            edit_message_media=AsyncMock(), edit_message_text=AsyncMock())
    return SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(type=chat_type))


def has_button_emoji(text):
    return any(ord(char) >= 0x1F000 or 0x2300 <= ord(char) <= 0x2BFF for char in text)


def test_home_arguments_do_not_become_deep_links_and_legacy_start_games_opens_catalog():
    home, catalog, invalid = home_update(), home_update(), home_update()
    run(ui().send_home(home, SimpleNamespace(args=['game_snake'])))
    run(ui().send_start(catalog, SimpleNamespace(args=['games'])))
    run(ui().send_start(invalid, SimpleNamespace(args=['game_sna'])))
    a = home.effective_message.reply_photo.await_args.kwargs
    b = catalog.effective_message.reply_photo.await_args.kwargs
    c = invalid.effective_message.reply_photo.await_args.kwargs
    assert a['photo'] == b['photo'] == c['photo'] == _photo_url(APP_URL)
    assert 'Escolha por onde começar' in a['caption']
    assert 'Página 1 de 1' in b['caption'] and 'Catálogo de jogos' in b['caption']
    assert 'Jogo não encontrado' in c['caption']  # Never fuzzy-match a /start payload.
    assert len({a['caption'], b['caption'], c['caption']}) == 3


@pytest.mark.parametrize('args,slug', [(['cóbrinha'], 'snake'), (['Corrida', 'aerea'], 'race'), (['chess'], 'chess')])
def test_play_uses_whole_normalized_name_or_slug(args, slug):
    update = home_update()
    run(ui().send_play(update, SimpleNamespace(args=args)))
    sent = update.effective_message.reply_photo.await_args.kwargs
    assert sent['photo'] == _photo_url(APP_URL, slug)
    assert sent['reply_markup'].inline_keyboard[0][0].web_app.url == _launch_url(APP_URL, slug)


def test_play_missing_name_is_escaped_and_provides_recovery_actions():
    update = home_update()
    run(ui().send_play(update, SimpleNamespace(args=['<script>', 'inexistente', '&'])))
    sent = update.effective_message.reply_photo.await_args.kwargs
    assert 'Jogo não encontrado' in sent['caption'] and '&lt;script&gt;' in sent['caption'] and '&amp;' in sent['caption']
    assert '<script>' not in sent['caption']
    buttons = [button for row in sent['reply_markup'].inline_keyboard for button in row]
    assert not any(button.url or button.web_app for button in buttons)
    assert {button.callback_data for button in buttons} >= {'bg:home', 'bg:games:all:0'}


def test_real_catalog_navigation_covers_every_game_once_with_bounded_emoji_buttons():
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / 'data/registry.json').read_text(encoding='utf8'))
    metadata = json.loads((root / 'data/catalog-pt.json').read_text(encoding='utf8'))
    for game in catalog['games']:
        game.update(metadata.get(game['slug'], {}))
    handler, slugs, sizes = ui(main=True, catalog=catalog), [], []
    for offset in range(0, len(catalog['games']), 6):
        update = callback_update(f'bg:games:all:{offset}')
        run(handler.callback_query(update, None))
        update.callback_query.answer.assert_awaited_once()
        edit = update.callback_query.edit_message_media.await_args.kwargs
        buttons = [button for row in edit['reply_markup'].inline_keyboard for button in row]
        launches = [button for button in buttons if button.web_app]
        sizes.append(len(launches))
        slugs.extend(parse_qs(urlsplit(button.web_app.url).query)['startapp'][0] for button in launches)
        assert all(has_button_emoji(button.text) for button in buttons)
        assert all(not button.callback_data or len(button.callback_data.encode()) <= 64 for button in buttons)
        assert len(html.unescape(re.sub(r'<[^>]*>', '', edit['media'].caption))) <= 1024
        update.callback_query.message.reply_photo.assert_not_awaited()
        update.callback_query.message.reply_text.assert_not_awaited()
    assert all(size == 6 for size in sizes[:-1]) and 1 <= sizes[-1] <= 6
    assert len(slugs) == len(set(slugs)) == len(catalog['games'])
    assert set(slugs) == {game['slug'] for game in catalog['games']}
    categories = callback_update('bg:categories')
    run(handler.callback_query(categories, None))
    rows = categories.callback_query.edit_message_media.await_args.kwargs['reply_markup'].inline_keyboard
    assert all(has_button_emoji(button.text) for row in rows for button in row)


def test_long_slug_suggestion_remains_bounded_and_changes_without_global_user_state(monkeypatch):
    slug = 'x' * 59
    games = {'games': [{'slug': slug, 'name': 'Jogo comprido'}, {'slug': 'other', 'name': 'Outro jogo'}]}
    monkeypatch.setattr('app.bot.random.choice', lambda choices: choices[0])
    handler, update = ui(catalog=games), home_update()
    run(handler.send_play(update, SimpleNamespace(args=[slug])))
    first = update.effective_message.reply_photo.await_args.kwargs
    swap = next(button for row in first['reply_markup'].inline_keyboard for button in row if button.text == '🔀 Outra sugestão')
    assert swap.callback_data == 'bg:play' and len(swap.callback_data.encode()) <= 64
    callback = callback_update(swap.callback_data, caption=html.unescape(re.sub(r'</?b>', '', first['caption'])))
    run(handler.callback_query(callback, None))
    assert callback.callback_query.edit_message_media.await_args.kwargs['media'].media == _photo_url(APP_URL, 'other')


def test_callback_acknowledgment_failure_and_invalid_utf8_never_edit_or_load_catalog():
    from telegram.error import TimedOut

    handler, loader = ui(), Mock(return_value=CATALOG)
    handler.catalog_loader = loader
    invalid = callback_update('\ud800')
    run(handler.callback_query(invalid, None))
    invalid.callback_query.answer.assert_awaited_once()
    invalid.callback_query.edit_message_media.assert_not_awaited()
    loader.assert_not_called()
    failed = callback_update('bg:home')
    failed.callback_query.answer.side_effect = TimedOut()
    with pytest.raises(TimedOut):
        run(handler.callback_query(failed, None))
    failed.callback_query.edit_message_media.assert_not_awaited()
    loader.assert_not_called()


@pytest.mark.parametrize('timeout', [False, True])
def test_callback_photo_permission_fallback_preserves_markup_without_retrying_uncertain_edit(timeout):
    from telegram.error import BadRequest, TimedOut

    update = callback_update('bg:games:all:0', chat_type='group')
    query = update.callback_query
    query.edit_message_media.side_effect = TimedOut() if timeout else BadRequest('CHAT_SEND_PHOTOS_FORBIDDEN')
    if timeout:
        with pytest.raises(TimedOut):
            run(ui().callback_query(update, None))
        query.message.reply_text.assert_not_awaited()
    else:
        run(ui().callback_query(update, None))
        attempted = query.edit_message_media.await_args.kwargs
        fallback = query.message.reply_text.await_args
        assert fallback.args == (attempted['media'].caption,)
        assert fallback.kwargs['reply_markup'] == attempted['reply_markup']
        assert fallback.kwargs['parse_mode'] == 'HTML'
    query.answer.assert_awaited_once()
    query.edit_message_media.assert_awaited_once()
    query.edit_message_text.assert_not_awaited()
    query.message.reply_photo.assert_not_awaited()
