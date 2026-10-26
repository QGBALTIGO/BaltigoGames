from __future__ import annotations

import html
import os
import re
import unicodedata
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_PAGE_SIZE = 25
# The fallback /start payload includes the five-byte "game_" prefix (64-byte limit).
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z", re.ASCII)
_CATEGORIES = {
    "puzzle": "Quebra-cabeças", "arcade": "Fliperama", "shooter": "Tiro",
    "racing": "Corrida", "sports": "Esportes", "platformer": "Plataforma",
    "casual": "Casuais", "board": "Tabuleiro", "word-quiz": "Palavras e perguntas",
    "3d": "Jogos em 3D",
}
_DESCRIPTION = (
    "Seu fliperama no Telegram: jogos em português, tutoriais e controles para celular. "
    "Abra o catálogo, escolha seu próximo desafio e jogue sem instalar nada. "
    "Use a busca inline para compartilhar um jogo em qualquer conversa."
)
_SHORT_DESCRIPTION = "Jogos em português no Telegram. Escolha, compartilhe e jogue sem instalar nada."
_PHOTO_PERMISSION_ERRORS = {
    "chat_send_photos_forbidden", "chat_send_media_forbidden",
    "not enough rights to send photos to the chat",
    "not enough rights to send media messages to the chat",
}


def _plain(value: Any, limit: int) -> str:
    # Catalog text is plain text. Strip controls and pictographs before HTML escaping.
    text = "".join(char if not char.isspace() else " " for char in str(value or "")
                   if (char.isspace() or unicodedata.category(char) not in {"Cc", "Cf", "Cs", "So"})
                   and char not in {"\ufe0e", "\ufe0f", "\u20e3"}
                   and not 0x1F3FB <= ord(char) <= 0x1F3FF)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _normalize(value: Any) -> str:
    return " ".join("".join(char for char in unicodedata.normalize("NFKD", str(value or ""))
                            if not unicodedata.combining(char)).casefold().split())


def _valid_slug(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= 59 and _SLUG.fullmatch(value) is not None


def _catalog_games(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    games, seen = [], set()
    for game in catalog.get("games", []):
        if not isinstance(game, dict) or not _valid_slug(game.get("slug")):
            continue
        if game["slug"] not in seen:
            games.append(game)
            seen.add(game["slug"])
    return games


def _launch_url(app_url: str, slug: str | None = None) -> str:
    if not slug:
        return app_url
    if not _valid_slug(slug):
        raise ValueError("invalid game slug")
    parts = urlsplit(app_url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params["startapp"] = slug
    return urlunsplit(parts._replace(query=urlencode(params)))


def _game_link(username: str, slug: str | None = None, has_main_web_app: bool = False,
               named_app_short_name: str = "") -> str:
    username = username.removeprefix("@")
    if re.fullmatch(r"[A-Za-z0-9_]{1,64}", username) is None:
        raise ValueError("invalid bot username")
    if slug is not None and not _valid_slug(slug):
        raise ValueError("invalid game slug")
    if named_app_short_name and re.fullmatch(r"[A-Za-z0-9_]{1,64}", named_app_short_name) is None:
        raise ValueError("invalid Mini App short name")
    base = f"https://t.me/{username}"
    if named_app_short_name:
        base += f"/{named_app_short_name}"
    if has_main_web_app or named_app_short_name:
        return base + (f"?startapp={slug}" if slug else "?startapp")
    return base + (f"?start=game_{slug}" if slug else "?start=games")


def _category(game: dict[str, Any]) -> str:
    return _CATEGORIES.get(str(game.get("category", "")), "Jogos")


def _search_games(catalog: dict[str, Any], query: str, limit: int = 25) -> list[dict[str, Any]]:
    games = _catalog_games(catalog)
    q = _normalize(query)
    if q.startswith("game:"):
        q = q[5:].strip()
    if not q:
        preferred = ["snake", "2048", "tetris", "pacman", "flappy", "car-race"]
        by_slug = {game["slug"]: game for game in games}
        ordered = [by_slug[slug] for slug in preferred if slug in by_slug]
        ordered.extend(game for game in games if game["slug"] not in preferred)
        return ordered[:max(0, limit)]

    def score(game: dict[str, Any]) -> tuple[int, str, str]:
        name, slug = _normalize(game.get("name", "")), game["slug"]
        tags = " ".join(str(tag) for tag in game.get("tags", []) if isinstance(tag, str))
        hay = _normalize(f"{name} {slug} {tags} {game.get('category', '')} {_category(game)} "
                         f"{game.get('description', '')} {game.get('tutorial', '')}")
        rank = (0 if q in {slug, name} else 1 if name.startswith(q) or slug.startswith(q)
                else 2 if all(word in hay for word in q.split()) else 99)
        return rank, name, slug

    return sorted((game for game in games if score(game)[0] < 99), key=score)[:max(0, limit)]


def _photo_url(app_url: str, slug: str | None = None, *, thumbnail: bool = False) -> str:
    if slug is not None and not _valid_slug(slug):
        raise ValueError("invalid game slug")
    filename = f"{'thumbs' if thumbnail else 'games'}/{slug}.jpg" if slug else "baltigo-games.jpg"
    parts = urlsplit(app_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/static/telegram/{filename}", "", ""))


def _game_caption(game: dict[str, Any]) -> str:
    name = html.escape(_plain(game.get("name"), 80) or game["slug"])
    objective = html.escape(_plain(game.get("description") or game.get("tutorial")
                                  or "Escolha seu desafio e acompanhe o tutorial para começar.", 280))
    return (f"<b>{name}</b>\n{_category(game)}\n\n<b>Objetivo</b>\n{objective}"
            "\n\n<b>Baltigo Games</b> · Jogue sem instalar.")


class _BotUI:
    """Pure presentation/handlers; tests never initialize a real Telegram client."""

    def __init__(self, app_url: str, catalog_loader: Callable[[], dict[str, Any]],
                 username: str, has_main_web_app: bool = False, named_app_short_name: str = ""):
        _game_link(username, has_main_web_app=has_main_web_app, named_app_short_name=named_app_short_name)
        self.app_url, self.catalog_loader = app_url, catalog_loader
        self.username, self.has_main_web_app = username, has_main_web_app
        self.named_app_short_name = named_app_short_name

    def _link(self, slug: str | None = None) -> str:
        return _game_link(self.username, slug, self.has_main_web_app, self.named_app_short_name)

    @property
    def direct_app_available(self) -> bool:
        return bool(self.has_main_web_app or self.named_app_short_name)

    async def send_home(self, update: Any, context: Any) -> None:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        from telegram.error import BadRequest, Forbidden

        if update.effective_message is None:
            return
        games = _catalog_games(self.catalog_loader())
        argument = str(context.args[0]) if context.args else ""
        slug = argument.removeprefix("game_")
        selected = next((game for game in games if game["slug"] == slug), None)
        slug = selected["slug"] if selected else None
        private = update.effective_chat is not None and update.effective_chat.type == "private"
        if private:
            open_button = InlineKeyboardButton("Jogar agora" if selected else "Abrir catálogo",
                                              web_app=WebAppInfo(url=_launch_url(self.app_url, slug)))
        else:
            label = ("Jogar agora" if selected else "Abrir catálogo") if self.direct_app_available else (
                "Abrir jogo no bot" if selected else "Abrir catálogo no bot")
            open_button = InlineKeyboardButton(label, url=self._link(slug))
        choose_button = (InlineKeyboardButton("Escolher um jogo para compartilhar", switch_inline_query="")
                         if update.effective_chat is not None and update.effective_chat.type == "channel"
                         else InlineKeyboardButton("Escolher um jogo nesta conversa", switch_inline_query_current_chat=""))
        keyboard = InlineKeyboardMarkup([
            [open_button],
            [choose_button],
        ])
        caption = _game_caption(selected) if selected else (
            "<b>Baltigo Games</b>\nSeu próximo jogo começa aqui.\n\n"
            "Jogos em português, tutoriais e desafios para jogar no celular. "
            "Abra o catálogo ou escolha um jogo para compartilhar nesta conversa.\n\n"
            "<b>Escolha. Jogue. Supere seu recorde.</b>"
        )
        if argument and argument != "games" and selected is None:
            caption += "\n\nEsse jogo não está disponível. Escolha outro no catálogo."
        try:
            await update.effective_message.reply_photo(
                photo=_photo_url(self.app_url, slug), caption=caption, parse_mode="HTML", reply_markup=keyboard,
            )
        except (BadRequest, Forbidden) as exc:
            rejection = str(exc).strip().casefold().removeprefix("forbidden: ").removeprefix("bad request: ")
            if rejection not in _PHOTO_PERMISSION_ERRORS:
                raise
            # A definitive media rejection is safe to replace; uncertain network failures are not.
            await update.effective_message.reply_text(caption, parse_mode="HTML", reply_markup=keyboard)

    async def inline_query(self, update: Any, context: Any) -> None:
        from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultPhoto,
                              InlineQueryResultsButton, WebAppInfo)

        query = update.inline_query
        if query is None:
            return
        games = _search_games(self.catalog_loader(), query.query, limit=1_000_000)
        raw_offset = str(query.offset or "")
        offset = int(raw_offset) if re.fullmatch(r"0|[1-9][0-9]{0,5}", raw_offset) else 0
        page = games[offset:offset + _PAGE_SIZE]
        results = []
        for game in page:
            slug = game["slug"]
            results.append(InlineQueryResultPhoto(
                id=slug, photo_url=_photo_url(self.app_url, slug),
                thumbnail_url=_photo_url(self.app_url, slug, thumbnail=True),
                title=_plain(game.get("name"), 80) or slug,
                description=_plain(f"{_category(game)} · {game.get('description', '')}", 160),
                caption=_game_caption(game), parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                    "Jogar agora" if self.direct_app_available else "Abrir jogo no bot", url=self._link(slug),
                )]]),
            ))
        next_offset = str(offset + len(page)) if offset + len(page) < len(games) else ""
        await query.answer(
            results, button=InlineQueryResultsButton(text="Abrir catálogo de jogos",
                                                    web_app=WebAppInfo(url=self.app_url)),
            next_offset=next_offset, cache_time=20, is_personal=False,
        )


async def start_bot(token: str, app_url: str, catalog_loader: Callable[[], dict[str, Any]]):
    from telegram import BotCommand, MenuButtonWebApp, Update, WebAppInfo
    from telegram.ext import Application, CommandHandler, InlineQueryHandler

    application = Application.builder().token(token).build()
    await application.initialize()
    me = await application.bot.get_me()
    ui = _BotUI(app_url, catalog_loader, me.username, bool(getattr(me, "has_main_web_app", False)),
                os.getenv("TELEGRAM_MINI_APP_SHORT_NAME", "").strip())
    await application.bot.set_my_name(name="Baltigo Games")
    await application.bot.set_my_description(description=_DESCRIPTION)
    await application.bot.set_my_short_description(short_description=_SHORT_DESCRIPTION)
    application.add_handler(CommandHandler(["start", "jogar", "games", "home"], ui.send_home))
    application.add_handler(InlineQueryHandler(ui.inline_query))
    await application.bot.set_my_commands([
        BotCommand("jogar", "Escolher e jogar"), BotCommand("games", "Explorar o catálogo"),
        BotCommand("home", "Voltar ao início"),
    ])
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Jogos", web_app=WebAppInfo(url=app_url)),
    )
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await application.start()
    return application
