"""Independent bot navigation contracts; all Telegram methods are async fakes.

These exercise the registered handlers and SDK wire payloads. They do not send a
message or establish real chat permissions, BotFather settings or image fetching.
"""
import asyncio
from html.parser import HTMLParser
import json
import re
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from telegram import InputMediaPhoto, MenuButtonDefault
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, InlineQueryHandler

from app.bot import start_bot


APP_URL = "https://games.example/?release=navigation"
USERNAME = "NavigationGamesBot"
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF]")
CATALOG = {"games": [
    {"slug": f"arcade-{i}", "name": "Ação no Céu" if i == 3 else f"Fliperama {i:02}",
     "category": "arcade", "description": f"Desafio independente {i}."} for i in range(8)
] + [
    {"slug": f"board-{i}", "name": f"Tabuleiro {i}", "category": "board", "description": "Planeje suas jogadas."}
    for i in range(2)
] + [
    {"slug": f"puzzle-{i}", "name": f"Quebra-cabeça {i}", "category": "puzzle", "description": "Resolva o desafio."}
    for i in range(3)
]}
BY_SLUG = {game["slug"]: game for game in CATALOG["games"]}


def run(awaitable):
    return asyncio.run(awaitable)


def wire(value):
    return json.loads(value.to_json())


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.tags = []

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)


def visible_text(value):
    parser = TextHTML()
    parser.feed(value)
    assert set(parser.tags) <= {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "a", "code", "pre", "blockquote", "tg-spoiler"}
    return "".join(parser.text)


def buttons(payload):
    assert payload.get("reply_markup") is not None, "Every response must retain actionable buttons"
    markup = wire(payload["reply_markup"])
    flat = [button for row in markup["inline_keyboard"] for button in row]
    assert flat
    for button in flat:
        assert EMOJI.search(button["text"]), button
        assert len(button["text"].encode("utf-16-le")) // 2 <= 64, button
        if "callback_data" in button:
            assert 1 <= len(button["callback_data"].encode("utf-8")) <= 64
    return flat


def game_buttons(payload):
    found = {}
    for button in buttons(payload):
        url = button.get("web_app", {}).get("url") or button.get("url")
        if not url:
            continue
        args = parse_qs(urlsplit(url).query)
        slug = args.get("startapp", [None])[0]
        if not slug and args.get("start", [""])[0].startswith("game_"):
            slug = args["start"][0][5:]
        if slug:
            assert slug not in found, "A game must appear once on a catalog page"
            found[slug] = button
    return found


def text_payload(payload):
    text = payload.get("caption", payload.get("text", ""))
    assert text and payload["parse_mode"] == "HTML"
    plain = visible_text(text)
    limit = 1024 if "caption" in payload else 4096
    assert len(plain.encode("utf-16-le")) // 2 <= limit
    assert EMOJI.search(plain), "The bot's own text should include the requested emoji styling"
    buttons(payload)
    return plain


def message(chat_type="private", photo=True):
    return SimpleNamespace(
        chat=SimpleNamespace(type=chat_type), photo=(SimpleNamespace(file_id="existing-photo"),) if photo else (),
        reply_photo=AsyncMock(), reply_text=AsyncMock(),
    )


def command_payload(msg):
    assert msg.reply_photo.await_count + msg.reply_text.await_count == 1
    call = msg.reply_photo.await_args or msg.reply_text.await_args
    payload = dict(call.kwargs)
    if call.args:
        payload["text"] = call.args[0]
    text_payload(payload)
    return payload


def harness(monkeypatch, *, main=False, named="", catalog=CATALOG):
    from telegram.ext import Application

    bot = SimpleNamespace(**{name: AsyncMock() for name in (
        "get_me", "set_my_name", "set_my_description", "set_my_short_description", "set_my_commands", "set_chat_menu_button")})
    bot.get_me.return_value = SimpleNamespace(username=USERNAME, has_main_web_app=main)
    bot.get_my_name = AsyncMock(return_value=SimpleNamespace(name=""))
    bot.get_my_description = AsyncMock(return_value=SimpleNamespace(description=""))
    bot.get_my_short_description = AsyncMock(return_value=SimpleNamespace(short_description=""))
    bot.get_my_commands = AsyncMock(return_value=[])
    bot.get_chat_menu_button = AsyncMock(return_value=MenuButtonDefault())
    app = SimpleNamespace(bot=bot, initialize=AsyncMock(), add_handler=Mock(), start=AsyncMock(),
                          updater=SimpleNamespace(start_polling=AsyncMock()))
    builder = Mock()
    builder.token.return_value = builder
    builder.build.return_value = app
    monkeypatch.setattr(Application, "builder", Mock(return_value=builder))
    monkeypatch.setenv("TELEGRAM_MINI_APP_SHORT_NAME", named)
    assert run(start_bot("synthetic-not-a-real-token", APP_URL, lambda: catalog)) is app
    handlers = [call.args[0] for call in app.add_handler.call_args_list]
    return SimpleNamespace(app=app, handlers=handlers)


def command(h, name, args=(), chat_type="private"):
    matches = [handler for handler in h.handlers if isinstance(handler, CommandHandler) and name in handler.commands]
    assert len(matches) == 1
    msg = message(chat_type)
    update = SimpleNamespace(effective_message=msg, effective_chat=msg.chat)
    run(matches[0].callback(update, SimpleNamespace(args=list(args))))
    return command_payload(msg)


def callback(h, data, *, chat_type="private", photo=True, failure=None):
    matches = [handler for handler in h.handlers if isinstance(handler, CallbackQueryHandler)]
    assert len(matches) == 1
    msg, events = message(chat_type, photo), []
    async def answered(*args, **kwargs):
        events.append("answer")
    async def edited_media(*args, **kwargs):
        events.append("media")
        if failure:
            raise failure
    async def edited_text(*args, **kwargs):
        events.append("text")
        if failure:
            raise failure
    query = SimpleNamespace(data=data, message=msg, answer=AsyncMock(side_effect=answered),
                            edit_message_media=AsyncMock(side_effect=edited_media),
                            edit_message_text=AsyncMock(side_effect=edited_text))
    update = SimpleNamespace(callback_query=query, effective_message=msg, effective_chat=msg.chat)
    context = SimpleNamespace(args=[], user_data=MappingProxyType({}), chat_data=MappingProxyType({}))
    run(matches[0].callback(update, context))
    query.answer.assert_awaited_once()
    assert events[0] == "answer"
    msg.reply_photo.assert_not_awaited()
    msg.reply_text.assert_not_awaited()
    return query, events


def callback_payload(query, *, photo=True):
    edited = query.edit_message_media if photo else query.edit_message_text
    edited.assert_awaited_once()
    other = query.edit_message_text if photo else query.edit_message_media
    other.assert_not_awaited()
    call = edited.await_args
    payload = dict(call.kwargs)
    if photo:
        media = payload.pop("media", call.args[0] if call.args else None)
        assert isinstance(media, InputMediaPhoto)
        payload.update(wire(media))
    elif call.args:
        payload["text"] = call.args[0]
    text_payload(payload)
    return payload


def test_three_commands_have_distinct_observable_purposes(monkeypatch):
    h = harness(monkeypatch)
    home = command(h, "home")
    games = command(h, "games")
    play = command(h, "jogar")
    assert len({visible_text(p.get("caption", p.get("text", ""))) for p in [home, games, play]}) == 3
    assert not game_buttons(home)
    assert len(game_buttons(games)) == 6
    chosen = game_buttons(play)
    assert len(chosen) == 1 and set(chosen) <= BY_SLUG.keys()
    slug = next(iter(chosen))
    assert BY_SLUG[slug]["name"] in visible_text(play.get("caption", play.get("text", "")))
    assert play["photo"] == f"https://games.example/static/telegram/games/{slug}.jpg"
    assert {"bg:home", "bg:categories"} <= {b.get("callback_data") for b in buttons(games)}
    assert any("switch_inline_query" in b or "switch_inline_query_current_chat" in b for b in buttons(games))


def test_home_always_resets_to_welcome_while_start_preserves_existing_links(monkeypatch):
    h = harness(monkeypatch)
    home = command(h, "home")
    for args in [("game_arcade-3",), ("games",), ("unknown",)]:
        payload = command(h, "home", args)
        assert payload["caption"] == home["caption"] and not game_buttons(payload)
    assert command(h, "start")["caption"] == home["caption"]
    assert set(game_buttons(command(h, "start", ("games",)))) == set(game_buttons(command(h, "games")))
    assert set(game_buttons(command(h, "start", ("game_arcade-3",)))) == {"arcade-3"}
    # A valid-looking prefix must never silently open a different fuzzy match.
    missing = command(h, "start", ("game_arcade",))
    assert not game_buttons(missing) and "não" in visible_text(missing["caption"]).casefold()


@pytest.mark.parametrize("args", [("arcade-3",), ("Ação", "no", "Céu"), ("acao", "no", "ceu")])
@pytest.mark.parametrize("chat_type,main,named", [("private", False, ""), ("group", True, ""),
    ("supergroup", False, ""), ("group", False, "arcade")])
def test_play_resolves_name_or_slug_and_preserves_actual_chat_destination(monkeypatch, args, chat_type, main, named):
    payload = command(harness(monkeypatch, main=main, named=named), "jogar", args, chat_type)
    selected = game_buttons(payload)
    assert set(selected) == {"arcade-3"}
    button = selected["arcade-3"]
    if chat_type == "private":
        assert button["web_app"]["url"] == APP_URL + "&startapp=arcade-3"
        assert "url" not in button
    else:
        assert not any("web_app" in b for b in buttons(payload))
        expected = (f"https://t.me/{USERNAME}/{named}?startapp=arcade-3" if named else
                    f"https://t.me/{USERNAME}?startapp=arcade-3" if main else
                    f"https://t.me/{USERNAME}?start=game_arcade-3")
        assert button["url"] == expected


def test_unmatched_play_and_empty_catalog_keep_recovery_buttons(monkeypatch):
    h = harness(monkeypatch)
    payload = command(h, "jogar", ("<script>missing & impossible</script>",))
    assert not game_buttons(payload)
    plain = visible_text(payload.get("caption", payload.get("text", ""))).casefold()
    assert "não" in plain and ("encontr" in plain or "dispon" in plain)
    assert "<script>" not in payload.get("caption", payload.get("text", ""))
    recovery = {b.get("callback_data") for b in buttons(payload)}
    assert "bg:home" in recovery
    assert recovery & {"bg:play", "bg:categories", "bg:games:all:0"} or any(
        "switch_inline_query" in b or "switch_inline_query_current_chat" in b for b in buttons(payload))
    empty = harness(monkeypatch, catalog={"games": []})
    for name in ["home", "games", "jogar"]:
        payload = command(empty, name)
        assert not game_buttons(payload)
        assert buttons(payload)


def test_all_catalog_pages_have_six_games_without_gaps_or_session_state(monkeypatch):
    h = harness(monkeypatch)
    pages = []
    for offset, expected_size in [(0, 6), (6, 6), (12, 1)]:
        # A fresh handler instance must understand the button without prior commands.
        fresh = harness(monkeypatch)
        query, events = callback(fresh, f"bg:games:all:{offset}")
        assert events == ["answer", "media"]
        payload = callback_payload(query)
        selected = game_buttons(payload)
        assert len(selected) == expected_size
        pages.append(set(selected))
        callbacks = {b.get("callback_data") for b in buttons(payload)}
        assert "bg:home" in callbacks and "bg:categories" in callbacks
        if offset < 12:
            assert f"bg:games:all:{offset + 6}" in callbacks
        if offset:
            assert f"bg:games:all:{offset - 6}" in callbacks
    assert set.union(*pages) == BY_SLUG.keys()
    assert not (pages[0] & pages[1] or pages[0] & pages[2] or pages[1] & pages[2])
    assert set(game_buttons(command(h, "games"))) == pages[0]


def test_packaged_catalog_is_reachable_through_all_six_game_pages(monkeypatch):
    from app.main import load_catalog

    # Use the same effective catalog loader passed to the production bot.
    catalog = load_catalog()
    expected = {game["slug"] for game in catalog["games"]}
    assert expected
    h = harness(monkeypatch, catalog=catalog)

    def follow_pages(payload, category, expected_slugs):
        seen, offset = [], 0
        for _ in range((len(expected_slugs) + 5) // 6):
            page = game_buttons(payload)
            assert len(page) == min(6, len(expected_slugs) - offset)
            assert set(page) <= expected_slugs
            assert all(button.get("web_app", {}).get("url") == APP_URL + f"&startapp={slug}"
                       and "url" not in button for slug, button in page.items())
            seen.extend(page)
            forward = [button["callback_data"] for button in buttons(payload)
                       if button.get("callback_data", "").startswith(f"bg:games:{category}:")
                       and int(button["callback_data"].rsplit(":", 1)[1]) > offset]
            if len(seen) == len(expected_slugs):
                assert not forward
                break
            assert forward == [f"bg:games:{category}:{offset + 6}"]
            query, _ = callback(h, forward[0])
            payload = callback_payload(query)
            offset += 6
        assert len(seen) == len(set(seen)) == len(expected_slugs)
        assert set(seen) == expected_slugs

    follow_pages(command(h, "games"), "all", expected)
    query, _ = callback(h, "bg:categories")
    category_payload = callback_payload(query)
    targets = {button["callback_data"] for button in buttons(category_payload)
               if button.get("callback_data", "").startswith("bg:games:")}
    categories = {game["category"] for game in catalog["games"]}
    assert targets == {"bg:games:all:0"} | {f"bg:games:{category}:0" for category in categories}
    for category in categories:
        query, _ = callback(h, f"bg:games:{category}:0")
        filtered = {game["slug"] for game in catalog["games"] if game["category"] == category}
        follow_pages(callback_payload(query), category, filtered)


@pytest.mark.parametrize("category,offset,size", [("arcade", 0, 6), ("arcade", 6, 2), ("board", 0, 2), ("puzzle", 0, 3)])
@pytest.mark.parametrize("photo", [True, False])
def test_category_filters_and_callbacks_edit_the_existing_media_or_text(monkeypatch, category, offset, size, photo):
    query, events = callback(harness(monkeypatch), f"bg:games:{category}:{offset}", photo=photo)
    assert events == ["answer", "media" if photo else "text"]
    payload = callback_payload(query, photo=photo)
    selected = game_buttons(payload)
    assert len(selected) == size
    assert all(BY_SLUG[slug]["category"] == category for slug in selected)
    assert "bg:categories" in {b.get("callback_data") for b in buttons(payload)}


def test_category_selector_has_exactly_the_available_categories_and_all(monkeypatch):
    query, events = callback(harness(monkeypatch), "bg:categories")
    assert events == ["answer", "media"]
    payload = callback_payload(query)
    assert not game_buttons(payload)
    callbacks = {b.get("callback_data") for b in buttons(payload)}
    category_targets = {value for value in callbacks if value and value.startswith("bg:games:")}
    assert category_targets == {"bg:games:all:0", "bg:games:arcade:0", "bg:games:board:0", "bg:games:puzzle:0"}
    assert "bg:home" in callbacks


@pytest.mark.parametrize("main,named", [(False, ""), (True, ""), (False, "arcade")])
@pytest.mark.parametrize("chat_type", ["group", "channel"])
def test_catalog_and_callback_destinations_remain_group_compatible(monkeypatch, main, named, chat_type):
    h = harness(monkeypatch, main=main, named=named)
    direct = command(h, "games", chat_type=chat_type)
    query, _ = callback(h, "bg:games:all:6", chat_type=chat_type)
    edited = callback_payload(query)
    for payload in [direct, edited]:
        for slug, button in game_buttons(payload).items():
            expected = (f"https://t.me/{USERNAME}/{named}?startapp={slug}" if named else
                        f"https://t.me/{USERNAME}?startapp={slug}" if main else
                        f"https://t.me/{USERNAME}?start=game_{slug}")
            assert button["url"] == expected and "web_app" not in button
        assert not any("web_app" in b for b in buttons(payload))
        if chat_type == "channel":
            assert not any("switch_inline_query_current_chat" in b for b in buttons(payload))


@pytest.mark.parametrize("data", [None, "", "bg:home:extra", "other:home", "bg:play:missing",
    "bg:games:all:1", "bg:games:all:01", "bg:games:all:-6", "bg:games:all:6.0",
    "bg:games:all:999999", "bg:games:board:6", "bg:games:missing:0",
    "bg:games:../:0", "bg:games:all:0:extra", "bg:games:all:" + "9" * 1000])
def test_invalid_callback_is_acknowledged_without_any_message_mutation(monkeypatch, data):
    query, events = callback(harness(monkeypatch), data)
    assert events == ["answer"]
    query.edit_message_media.assert_not_awaited()
    query.edit_message_text.assert_not_awaited()


def test_repeated_stateless_buttons_do_not_send_new_messages(monkeypatch):
    h = harness(monkeypatch)
    query, events = callback(h, "bg:games:arcade:0")
    assert events == ["answer", "media"]
    first = callback_payload(query)
    handler = next(handler for handler in h.handlers if isinstance(handler, CallbackQueryHandler))
    update = SimpleNamespace(callback_query=query, effective_message=query.message, effective_chat=query.message.chat)
    context = SimpleNamespace(args=[], user_data=MappingProxyType({}), chat_data=MappingProxyType({}))
    run(handler.callback(update, context))
    assert events == ["answer", "media", "answer", "media"]
    assert query.answer.await_count == query.edit_message_media.await_count == 2
    second = query.edit_message_media.await_args.kwargs
    assert wire(second["media"]) == {key: first[key] for key in wire(second["media"])}
    assert wire(second["reply_markup"]) == wire(first["reply_markup"])
    query.message.reply_photo.assert_not_awaited()
    query.message.reply_text.assert_not_awaited()
    query, events = callback(h, "bg:games:arcade:0", failure=BadRequest("Message is not modified"))
    assert events == ["answer", "media"]
    query.edit_message_media.assert_awaited_once()


@pytest.mark.parametrize("data", ["bg:home", "bg:play"])
def test_home_and_play_callbacks_have_distinct_meaning(monkeypatch, data):
    query, _ = callback(harness(monkeypatch), data)
    selected = game_buttons(callback_payload(query))
    assert len(selected) == (1 if data == "bg:play" else 0)


def test_another_game_callback_excludes_the_selected_game_without_session_data(monkeypatch):
    query, events = callback(harness(monkeypatch), "bg:play:arcade-3")
    assert events == ["answer", "media"]
    selected = game_buttons(callback_payload(query))
    assert len(selected) == 1 and "arcade-3" not in selected and set(selected) <= BY_SLUG.keys()


def test_long_catalog_text_is_escaped_and_fits_the_telegram_caption(monkeypatch):
    catalog = {"games": [{"slug": "safe-game", "name": '<b>Nome & estranho</b>' + 'x' * 5000,
                          "category": "arcade", "description": '<script>alert(1)</script>&' + 'y' * 5000}]}
    payload = command(harness(monkeypatch, catalog=catalog), "jogar", ("safe-game",))
    assert set(game_buttons(payload)) == {"safe-game"}
    text = payload.get("caption", payload.get("text", ""))
    assert "&lt;b&gt;Nome &amp; estranho&lt;/b&gt;" in text
    assert "<script>" not in text
    assert len(visible_text(text).encode('utf-16-le')) // 2 <= 1024


def test_inline_header_result_buttons_and_menu_all_use_requested_emojis(monkeypatch):
    h = harness(monkeypatch)
    menu = wire(h.app.bot.set_chat_menu_button.await_args.kwargs["menu_button"])
    assert EMOJI.search(menu["text"]) and menu["web_app"]["url"] == APP_URL
    handlers = [handler for handler in h.handlers if isinstance(handler, InlineQueryHandler)]
    assert len(handlers) == 1
    query = SimpleNamespace(query="arcade-3", offset="", answer=AsyncMock())
    run(handlers[0].callback(SimpleNamespace(inline_query=query), None))
    call = query.answer.await_args
    header = wire(call.kwargs["button"])
    assert EMOJI.search(header["text"]) and header["web_app"]["url"] == APP_URL
    assert len(call.args[0]) == 1
    photo = wire(call.args[0][0])
    assert photo["type"] == "photo" and "input_message_content" not in photo
    assert EMOJI.search(visible_text(photo["caption"]))
    for row in photo["reply_markup"]["inline_keyboard"]:
        for button in row:
            assert EMOJI.search(button["text"]) and "url" in button and "web_app" not in button
