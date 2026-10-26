"""Independent transport checks: no Telegram credentials, network or real messages."""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from telegram import InputFile, PhotoSize
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut

from app.bot import _BotUI, _photo_url


APP_URL = "https://games.example/?version=2"
GAME = {"slug": "snake", "name": "Cobrinha", "category": "arcade", "description": "Recolha as maçãs."}
OTHER_GAME = {"slug": "chess", "name": "Xadrez", "category": "board", "description": "Proteja o rei."}
CATALOG = {"games": [GAME, OTHER_GAME]}
BANNER_BYTES = b"\xff\xd8\xff-banner-fixture"
GAME_BYTES = b"\xff\xd8\xff-game-fixture"


def received(file_id="telegram-photo"):
    return SimpleNamespace(photo=(PhotoSize("small-" + file_id, "unique-small", 100, 100),
                                  PhotoSize(file_id, "unique-large", 1200, 630)),
                           chat_id=987654, message_id=321)


def make_message(file_id=None):
    return SimpleNamespace(
        photo=received(file_id).photo if file_id else (),
        reply_photo=AsyncMock(return_value=received()), reply_text=AsyncMock(),
        caption=None, text=None, chat_id=987654, message_id=321,
    )


def make_update(message=None, *, chat_type="private"):
    return SimpleNamespace(effective_message=message or make_message(),
                           effective_chat=SimpleNamespace(type=chat_type, id=987654))


def make_query(message=None, *, response="edited-photo"):
    return SimpleNamespace(
        message=message or make_message("old-photo"),
        edit_message_caption=AsyncMock(return_value=received(response)),
        edit_message_media=AsyncMock(return_value=received(response)),
        edit_message_text=AsyncMock(return_value=True),
    )


@pytest.fixture
def artwork(tmp_path):
    root = tmp_path / "telegram"
    (root / "games").mkdir(parents=True)
    (root / "baltigo-games.jpg").write_bytes(BANNER_BYTES)
    (root / "games" / "snake.jpg").write_bytes(GAME_BYTES)
    (root / "games" / "chess.jpg").write_bytes(b"\xff\xd8\xff-chess-fixture")
    return root


def make_ui(artwork=None):
    return _BotUI(APP_URL, lambda: CATALOG, "ExampleGamesBot", True, media_root=artwork)


def assert_upload(value, name, content):
    assert isinstance(value, InputFile)
    # Real PTB multipart tuple, including the MIME type inferred from the JPEG filename.
    assert value.field_tuple == (name, content, "image/jpeg")


@pytest.mark.asyncio
async def test_first_home_uploads_public_bytes_then_reuses_telegram_id(artwork):
    ui = make_ui(artwork)
    first = make_update()
    first.effective_message.reply_photo.return_value = received("banner-id")
    await ui.send_home(first, SimpleNamespace(args=[]))
    args = first.effective_message.reply_photo.await_args.kwargs
    assert_upload(args["photo"], "baltigo-games.jpg", BANNER_BYTES)
    assert args["parse_mode"] == "HTML"
    assert "🎮 Baltigo Games" in args["caption"]
    assert args["reply_markup"].inline_keyboard[0][0].web_app.url == APP_URL

    # Cached delivery must survive loss of the local file without fetching its public URL.
    (artwork / "baltigo-games.jpg").unlink()
    second = make_update()
    await ui.send_home(second, SimpleNamespace(args=[]))
    assert second.effective_message.reply_photo.await_args.kwargs["photo"] == "banner-id"
    assert second.effective_message.reply_photo.await_args.kwargs["caption"] == args["caption"]
    first.effective_message.reply_text.assert_not_awaited()
    second.effective_message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_banner_and_each_game_keep_independent_photo_ids(artwork):
    ui = make_ui(artwork)
    cases = [(ui._home_view("private"), "banner-id", BANNER_BYTES, "baltigo-games.jpg"),
             (ui._game_view(GAME, "private"), "snake-id", GAME_BYTES, "snake.jpg"),
             (ui._game_view(OTHER_GAME, "private"), "chess-id", b"\xff\xd8\xff-chess-fixture", "chess.jpg")]
    for view, result_id, content, name in cases:
        update = make_update()
        update.effective_message.reply_photo.return_value = received(result_id)
        await ui._deliver(update, view)
        assert_upload(update.effective_message.reply_photo.await_args.kwargs["photo"], name, content)
    for view, expected_id, _, _ in cases:
        update = make_update()
        await ui._deliver(update, view)
        assert update.effective_message.reply_photo.await_args.kwargs["photo"] == expected_id


@pytest.mark.asyncio
async def test_matching_known_photo_edits_caption_without_accessing_artwork(artwork, monkeypatch):
    ui = make_ui(artwork)
    ui._remember_photo(None, received("banner-id"))
    ui._record_message_photo(received("banner-id"), "banner-id")
    monkeypatch.setattr(ui, "_photo_source", Mock(side_effect=AssertionError("unnecessary artwork access")))
    query = make_query(make_message("banner-id"), response="banner-id")
    view = ui._catalog_view(CATALOG["games"], "private")
    await ui._deliver(make_update(query.message), view, query)
    query.edit_message_caption.assert_awaited_once_with(
        caption=view[0], parse_mode="HTML", reply_markup=view[1])
    query.edit_message_media.assert_not_awaited()
    query.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("known,current", [(None, "banner-id"), ("banner-id", "game-id"),
                                           ("banner-id", "banner-id")])
async def test_unproven_photo_identity_requires_media_edit(artwork, known, current):
    ui = make_ui(artwork)
    if known:
        ui._remember_photo(None, received(known))
    query = make_query(make_message(current), response="new-banner-id")
    await ui._deliver(make_update(query.message), ui._home_view("private"), query)
    query.edit_message_media.assert_awaited_once()
    query.edit_message_caption.assert_not_awaited()
    media = query.edit_message_media.await_args.kwargs["media"]
    if known:
        assert media.media == known
    else:
        assert_upload(media.media, "baltigo-games.jpg", BANNER_BYTES)
    assert media.to_dict()["parse_mode"] == "HTML"
    assert "🏠 /home" in media.caption
    assert ui._photo_source(None) == ("new-banner-id", "cached")


@pytest.mark.asyncio
async def test_media_edit_learns_file_id_and_text_edits_never_upload(artwork):
    ui = make_ui(artwork)
    query = make_query(response="new-snake-id")
    await ui._deliver(make_update(query.message), ui._game_view(GAME, "private"), query)
    media = query.edit_message_media.await_args.kwargs["media"]
    assert_upload(media.media, "snake.jpg", GAME_BYTES)
    assert ui._photo_source("snake") == ("new-snake-id", "cached")

    text_query = make_query(make_message())
    view = ui._categories_view(CATALOG["games"], "private")
    await ui._deliver(make_update(text_query.message), view, text_query)
    text_query.edit_message_text.assert_awaited_once_with(view[0], parse_mode="HTML", reply_markup=view[1])
    text_query.edit_message_caption.assert_not_awaited()
    text_query.edit_message_media.assert_not_awaited()


def test_photo_cache_is_bounded_and_evicted_artwork_remains_available(artwork):
    ui = make_ui(artwork)
    ui._remember_photo(None, received("oldest-banner-id"))
    for number in range(256):
        ui._remember_photo(f"game-{number}", received(f"id-{number}"))
    assert len(ui._photo_ids) == 256
    assert None not in ui._photo_ids
    photo, source = ui._photo_source(None)
    assert source == "upload"
    assert_upload(photo, "baltigo-games.jpg", BANNER_BYTES)
    ui._remember_photo("game-255", received("replacement-id"))
    assert len(ui._photo_ids) == 256
    assert ui._photo_source("game-255") == ("replacement-id", "cached")


@pytest.mark.parametrize("response", [True, None, SimpleNamespace(photo=[]),
                                      SimpleNamespace(photo=(SimpleNamespace(file_id=None),)),
                                      SimpleNamespace(photo=(SimpleNamespace(file_id=""),))])
def test_non_photo_sdk_result_does_not_poison_cache(response):
    ui = make_ui()
    ui._remember_photo(None, response)
    assert ui._photo_ids == {}


def test_missing_artwork_and_unconfigured_directory_use_public_url(artwork):
    ui = make_ui(artwork)
    assert ui._photo_source("missing") == (_photo_url(APP_URL, "missing"), "url")
    assert make_ui()._photo_source(None) == (_photo_url(APP_URL), "url")


def test_unreadable_artwork_uses_public_url(artwork, monkeypatch):
    ui = make_ui(artwork)
    monkeypatch.setattr(Path, "read_bytes", Mock(side_effect=PermissionError("fixture")))
    assert ui._photo_source("snake") == (_photo_url(APP_URL, "snake"), "url")


def test_unresolvable_artwork_uses_public_url_without_reading(artwork, monkeypatch):
    ui = make_ui(artwork)
    monkeypatch.setattr(Path, "resolve", Mock(side_effect=PermissionError("directory resolution denied")))
    reader = Mock(side_effect=AssertionError("unresolvable artwork was read"))
    monkeypatch.setattr(Path, "read_bytes", reader)
    assert ui._photo_source("snake") == (_photo_url(APP_URL, "snake"), "url")
    reader.assert_not_called()


def test_resolved_artwork_outside_root_is_never_read(artwork, tmp_path, monkeypatch):
    ui = make_ui(artwork)
    outside = tmp_path / "private-photo.jpg"
    outside.write_bytes(b"private data must never be uploaded")
    original_resolve = Path.resolve
    def resolved(path, *args, **kwargs):
        return outside if path.name == "snake.jpg" else original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolved)
    reader = Mock(side_effect=AssertionError("outside-root file was read"))
    monkeypatch.setattr(Path, "read_bytes", reader)
    assert ui._photo_source("snake") == (_photo_url(APP_URL, "snake"), "url")
    reader.assert_not_called()


@pytest.mark.parametrize("slug", ["../private", "snake/../../private", "SNAKE", "snake?key=secret"])
def test_invalid_slug_is_rejected_before_any_filesystem_read(artwork, monkeypatch, slug):
    ui = make_ui(artwork)
    reader = Mock(side_effect=AssertionError("invalid path was read"))
    monkeypatch.setattr(Path, "read_bytes", reader)
    with pytest.raises(ValueError, match="invalid game slug"):
        ui._photo_source(slug)
    reader.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("editing", [False, True])
@pytest.mark.parametrize("description", [
    "Wrong file identifier/HTTP URL specified", "Wrong remote file identifier specified",
    "Invalid remote file identifier", "Wrong remote file identifier specified: can't unserialize it",
])
async def test_definitively_rejected_cached_photo_uploads_once(artwork, editing, description):
    ui = make_ui(artwork)
    ui._remember_photo("snake", received("expired-id"))
    update = make_update()
    query = make_query() if editing else None
    operation = query.edit_message_media if editing else update.effective_message.reply_photo
    operation.side_effect = [BadRequest(description), received("fresh-id")]
    await ui._deliver(update, ui._game_view(GAME, "private"), query)
    assert operation.await_count == 2
    first = operation.await_args_list[0].kwargs
    second = operation.await_args_list[1].kwargs
    assert (first["media"].media if editing else first["photo"]) == "expired-id"
    assert_upload(second["media"].media if editing else second["photo"], "snake.jpg", GAME_BYTES)
    assert ui._photo_source("snake") == ("fresh-id", "cached")
    update.effective_message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_photo_rejection_never_retries_a_third_time(artwork):
    ui = make_ui(artwork)
    ui._remember_photo("snake", received("expired-id"))
    update = make_update()
    operation = update.effective_message.reply_photo
    operation.side_effect = BadRequest("Wrong remote file identifier specified")
    with pytest.raises(BadRequest):
        await ui._deliver(update, ui._game_view(GAME, "private"))
    assert operation.await_count == 2
    update.effective_message.reply_text.assert_not_awaited()
    assert "snake" not in ui._photo_ids


@pytest.mark.asyncio
async def test_rejected_cached_id_does_not_discard_a_newer_concurrent_id(artwork):
    ui = make_ui(artwork)
    ui._remember_photo("snake", received("expired-id"))
    update = make_update()
    async def reject_old_then_accept(**kwargs):
        if kwargs["photo"] == "expired-id":
            ui._remember_photo("snake", received("newer-id"))
            raise BadRequest("Wrong remote file identifier specified")
        assert kwargs["photo"] == "newer-id"
        return received("newer-id")
    update.effective_message.reply_photo.side_effect = reject_old_then_accept
    await ui._deliver(update, ui._game_view(GAME, "private"))
    assert update.effective_message.reply_photo.await_count == 2
    assert ui._photo_source("snake") == ("newer-id", "cached")


@pytest.mark.asyncio
@pytest.mark.parametrize("editing", [False, True])
@pytest.mark.parametrize("error", [TimedOut("uncertain send"), NetworkError("uncertain network"),
                                   RetryAfter(9), Forbidden("bot blocked"),
                                   BadRequest("Failed to get HTTP URL content"),
                                   BadRequest("caption is too long")])
async def test_uncertain_or_unrelated_failure_never_resends(artwork, editing, error):
    ui = make_ui(artwork)
    ui._remember_photo("snake", received("cached-id"))
    update = make_update()
    query = make_query() if editing else None
    operation = query.edit_message_media if editing else update.effective_message.reply_photo
    operation.side_effect = error
    with pytest.raises(type(error)):
        await ui._deliver(update, ui._game_view(GAME, "private"), query)
    operation.assert_awaited_once()
    update.effective_message.reply_text.assert_not_awaited()
    if query:
        query.message.reply_text.assert_not_awaited()
    assert ui._photo_source("snake") == ("cached-id", "cached")


@pytest.mark.asyncio
@pytest.mark.parametrize("editing", [False, True])
async def test_invalid_id_error_on_fresh_upload_does_not_retry(artwork, editing):
    ui = make_ui(artwork)
    update = make_update()
    query = make_query() if editing else None
    operation = query.edit_message_media if editing else update.effective_message.reply_photo
    operation.side_effect = BadRequest("Wrong remote file identifier specified")
    with pytest.raises(BadRequest):
        await ui._deliver(update, ui._game_view(GAME, "private"), query)
    operation.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("editing", [False, True])
@pytest.mark.parametrize("error", [Forbidden("CHAT_SEND_PHOTOS_FORBIDDEN"),
                                   BadRequest("Not enough rights to send media messages to the chat")])
async def test_definite_media_permission_rejection_preserves_text_and_buttons(artwork, editing, error):
    ui = make_ui(artwork)
    update = make_update()
    query = make_query() if editing else None
    message = query.message if query else update.effective_message
    operation = query.edit_message_media if editing else message.reply_photo
    operation.side_effect = error
    view = ui._game_view(GAME, "private")
    await ui._deliver(update, view, query)
    operation.assert_awaited_once()
    message.reply_text.assert_awaited_once_with(view[0], parse_mode="HTML", reply_markup=view[1])


@pytest.mark.asyncio
@pytest.mark.parametrize("caption_only", [False, True])
async def test_repeated_edit_noop_does_not_send_a_replacement(artwork, caption_only):
    ui = make_ui(artwork)
    if caption_only:
        ui._remember_photo(None, received("banner-id"))
        ui._record_message_photo(received("banner-id"), "banner-id")
    query = make_query(make_message("banner-id"))
    operation = query.edit_message_caption if caption_only else query.edit_message_media
    operation.side_effect = BadRequest("Message is not modified: specified new message content is the same")
    await ui._deliver(make_update(query.message), ui._home_view("private"), query)
    operation.assert_awaited_once()
    query.message.reply_photo.assert_not_awaited()
    query.message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_latency_log_contains_only_operation_transport_time_and_outcome(artwork, caplog, failure):
    ui = make_ui(artwork)
    update = make_update()
    secret_text = "sensitive command argument 123456:EXAMPLE_TOKEN"
    if failure:
        update.effective_message.reply_photo.side_effect = NetworkError(secret_text)
    with caplog.at_level(logging.INFO, logger="baltigogames.bot"):
        if failure:
            with pytest.raises(NetworkError):
                await ui._deliver(update, (secret_text, ui._home_view("private")[1], None))
        else:
            await ui._deliver(update, (secret_text, ui._home_view("private")[1], None))
    entries = [record.getMessage() for record in caplog.records if record.name == "baltigogames.bot"]
    assert len(entries) == 1
    assert "operation=send_photo transport=upload elapsed_ms=" in entries[0]
    assert f"outcome={'error' if failure else 'ok'}" in entries[0]
    for private in [secret_text, "123456", "EXAMPLE_TOKEN", str(artwork), "987654", APP_URL]:
        assert private not in entries[0]


@pytest.mark.asyncio
async def test_queued_old_callback_snapshot_never_keeps_the_previous_game_picture(artwork):
    ui = make_ui(artwork)
    initial = make_update()
    initial.effective_message.reply_photo.return_value = received("banner-id")
    await ui.send_home(initial, SimpleNamespace(args=[]))

    # Both callback updates arrived before the first edit and describe the same old banner.
    original_snapshot = make_message("banner-id")
    play = make_query(original_snapshot, response="snake-id")
    home = make_query(original_snapshot, response="banner-id")
    await ui._deliver(make_update(original_snapshot), ui._game_view(GAME, "private"), play)
    await ui._deliver(make_update(original_snapshot), ui._home_view("private"), home)
    play.edit_message_media.assert_awaited_once()
    home.edit_message_media.assert_awaited_once()
    assert home.edit_message_media.await_args.kwargs["media"].media == "banner-id"
    home.edit_message_caption.assert_not_awaited()

    # The returned message now proves that the banner is current, even if a snapshot lags behind.
    catalog = make_query(make_message("snake-id"), response="banner-id")
    await ui._deliver(make_update(original_snapshot), ui._catalog_view(CATALOG["games"], "private"), catalog)
    catalog.edit_message_caption.assert_awaited_once()
    catalog.edit_message_media.assert_not_awaited()


@pytest.mark.asyncio
async def test_uncertain_media_edit_forgets_previous_picture_proof(artwork):
    ui = make_ui(artwork)
    ui._remember_photo(None, received("banner-id"))
    ui._record_message_photo(received("banner-id"), "banner-id")
    snapshot = make_message("banner-id")
    first = make_query(snapshot)
    first.edit_message_media.side_effect = TimedOut("remote photo may have changed")
    with pytest.raises(TimedOut):
        await ui._deliver(make_update(snapshot), ui._game_view(GAME, "private"), first)
    second = make_query(snapshot, response="banner-id")
    await ui._deliver(make_update(snapshot), ui._home_view("private"), second)
    second.edit_message_media.assert_awaited_once()
    second.edit_message_caption.assert_not_awaited()


@pytest.mark.asyncio
async def test_boolean_upload_acknowledgment_does_not_prove_current_photo_identity(artwork):
    ui = make_ui(artwork)
    snapshot = make_message("some-game-id")
    first = make_query(snapshot)
    first.edit_message_media.return_value = True
    await ui._deliver(make_update(snapshot), ui._home_view("private"), first)
    assert not ui._same_photo(None, snapshot)
    second = make_query(make_message("banner-id"), response="banner-id")
    await ui._deliver(make_update(snapshot), ui._catalog_view(CATALOG["games"], "private"), second)
    second.edit_message_media.assert_awaited_once()
    second.edit_message_caption.assert_not_awaited()


def test_current_message_proof_is_bounded_and_not_shared_between_chats(artwork):
    ui = make_ui(artwork)
    ui._remember_photo(None, received("banner-id"))
    ui._record_message_photo(received("banner-id"), "banner-id")
    other_chat = SimpleNamespace(chat_id=123, message_id=321, photo=received("banner-id").photo)
    assert not ui._same_photo(None, other_chat)
    for number in range(2048):
        ui._record_message_photo(SimpleNamespace(chat_id=123, message_id=number), "banner-id")
    assert len(ui._message_photo_ids) == 2048
    assert not ui._same_photo(None, received("banner-id"))


@pytest.mark.parametrize("message", [SimpleNamespace(chat_id=True, message_id=321),
                                     SimpleNamespace(chat_id=123, message_id=False),
                                     SimpleNamespace(chat_id="123", message_id=321),
                                     SimpleNamespace(chat_id=123), True, None])
def test_non_message_acknowledgment_never_becomes_picture_proof(message):
    ui = make_ui()
    ui._remember_photo(None, received("banner-id"))
    ui._record_message_photo(message, "banner-id")
    assert ui._message_photo_ids == {}
    assert not ui._same_photo(None, message)
