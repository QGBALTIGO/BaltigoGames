from __future__ import annotations

import html
import logging
import os
import random
import re
import unicodedata
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_PAGE_SIZE = 25
_CATALOG_PAGE_SIZE = 6
# The fallback /start payload includes the five-byte "game_" prefix (64-byte limit).
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z", re.ASCII)
_CATEGORIES = {
    "puzzle": "Quebra-cabeças", "arcade": "Fliperama", "shooter": "Tiro",
    "racing": "Corrida", "sports": "Esportes", "platformer": "Plataforma",
    "casual": "Casuais", "board": "Tabuleiro", "word-quiz": "Palavras e perguntas",
    "3d": "Jogos em 3D",
}
_DESCRIPTION = (
    "🎮 Seu fliperama no Telegram, com jogos em português e sem instalação. "
    "Use /jogar para uma sugestão, /games para explorar o catálogo e /home para voltar ao início. "
    "🔎 Encontre e compartilhe jogos pela busca inline."
)
_SHORT_DESCRIPTION = "🎮 Jogos em português, sem instalar. Descubra seu próximo favorito e compartilhe no Telegram."
_CATEGORY_ICONS = {
    "puzzle": "🧩", "arcade": "🕹️", "shooter": "🎯", "racing": "🏎️", "sports": "⚽",
    "platformer": "🏃", "casual": "🎈", "board": "♟️", "word-quiz": "📝", "3d": "🌐",
}
_PHOTO_PERMISSION_ERRORS = {
    "chat_send_photos_forbidden", "chat_send_media_forbidden",
    "not enough rights to send photos to the chat",
    "not enough rights to send media messages to the chat",
}
_LOGGER = logging.getLogger("baltigogames.bot")


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
    return (f"<b>🎮 {name}</b>\n{_category(game)}\n\n<b>Objetivo</b>\n{objective}"
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

    def _open_button(self, chat_type: str, slug: str | None = None, label: str | None = None):
        from telegram import InlineKeyboardButton, WebAppInfo

        if chat_type == "private":
            return InlineKeyboardButton(label or ("🎮 Jogar agora" if slug else "📱 Abrir webapp"),
                                        web_app=WebAppInfo(url=_launch_url(self.app_url, slug)))
        default = ("🎮 Jogar agora" if slug else "📱 Abrir webapp") if self.direct_app_available else (
            "🔗 Abrir jogo no bot" if slug else "🔗 Abrir catálogo no bot")
        return InlineKeyboardButton(label or default, url=self._link(slug))

    @staticmethod
    def _search_button(chat_type: str):
        from telegram import InlineKeyboardButton

        return (InlineKeyboardButton("🔎 Buscar um jogo", switch_inline_query="") if chat_type == "channel"
                else InlineKeyboardButton("🔎 Buscar um jogo", switch_inline_query_current_chat=""))

    @staticmethod
    def _chat_type(update: Any) -> str:
        return str(getattr(getattr(update, "effective_chat", None), "type", "unknown"))

    def _home_view(self, chat_type: str):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        caption = (
            "<b>🎮 Baltigo Games</b>\nSeu próximo favorito está a um toque.\n\n"
            "<b>Escolha por onde começar</b>\n"
            "🎲 /jogar — receba uma sugestão ou procure, por exemplo, /jogar xadrez.\n"
            "🕹️ /games — explore os jogos por página e categoria.\n"
            "🏠 /home — volte para este início.\n\n"
            "Abra o webapp para jogar ou use a busca para compartilhar um jogo nesta conversa."
        )
        keyboard = InlineKeyboardMarkup([
            [self._open_button(chat_type)],
            [InlineKeyboardButton("🎲 Sugerir um jogo", callback_data="bg:play"),
             InlineKeyboardButton("🕹️ Ver catálogo", callback_data="bg:games:all:0")],
            [self._search_button(chat_type)],
        ])
        return caption, keyboard, None

    def _game_view(self, game: dict[str, Any], chat_type: str):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        slug = game["slug"]
        # All current slugs fit. Longer valid /start slugs use the visible caption to exclude the current game.
        swap = f"bg:play:{slug}" if len(f"bg:play:{slug}".encode()) <= 64 else "bg:play"
        keyboard = InlineKeyboardMarkup([
            [self._open_button(chat_type, slug)],
            [InlineKeyboardButton("🔀 Outra sugestão", callback_data=swap),
             InlineKeyboardButton("🕹️ Ver catálogo", callback_data="bg:games:all:0")],
            [InlineKeyboardButton("🏠 Início", callback_data="bg:home"), self._search_button(chat_type)],
        ])
        return _game_caption(game), keyboard, slug

    def _not_found_view(self, query: str, chat_type: str):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        searched = html.escape(_plain(query, 100))
        caption = (f"<b>🔎 Jogo não encontrado</b>\nNão encontrei <b>{searched}</b>.\n\n"
                   "Tente outro nome, use /jogar com o nome do jogo ou escolha no catálogo.\n\n"
                   "<b>Baltigo Games</b>")
        return caption, InlineKeyboardMarkup([
            [self._search_button(chat_type)],
            [InlineKeyboardButton("🕹️ Ver catálogo", callback_data="bg:games:all:0"),
             InlineKeyboardButton("🏠 Início", callback_data="bg:home")],
        ]), None

    @staticmethod
    def _ordered_games(games: list[dict[str, Any]], category: str = "all") -> list[dict[str, Any]]:
        return sorted((game for game in games if category == "all" or game.get("category") == category),
                      key=lambda game: (_normalize(game.get("name") or game["slug"]), game["slug"]))

    def _catalog_view(self, games: list[dict[str, Any]], chat_type: str, category: str = "all", offset: int = 0):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        filtered = self._ordered_games(games, category)
        page = filtered[offset:offset + _CATALOG_PAGE_SIZE]
        total = len(filtered)
        pages = max(1, (total + _CATALOG_PAGE_SIZE - 1) // _CATALOG_PAGE_SIZE)
        label = "Todos os jogos" if category == "all" else _CATEGORIES[category]
        caption = (f"<b>🕹️ Catálogo de jogos</b>\n{label} · {total} {'jogo' if total == 1 else 'jogos'}\n"
                   f"Página {offset // _CATALOG_PAGE_SIZE + 1} de {pages}\n\n"
                   + ("Escolha um dos jogos abaixo. Use as categorias para filtrar ou a busca para encontrar um nome."
                      if page else "Ainda não há jogos disponíveis aqui. Volte ao início ou tente novamente mais tarde."))
        buttons = [self._open_button(chat_type, game["slug"],
                    f"{_CATEGORY_ICONS.get(game.get('category'), '🎮')} {_plain(game.get('name'), 40) or game['slug']}")
                   for game in page]
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        navigation = []
        if offset:
            navigation.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"bg:games:{category}:{offset - _CATALOG_PAGE_SIZE}"))
        if offset + _CATALOG_PAGE_SIZE < total:
            navigation.append(InlineKeyboardButton("➡️ Próxima", callback_data=f"bg:games:{category}:{offset + _CATALOG_PAGE_SIZE}"))
        if navigation:
            rows.append(navigation)
        rows.extend([
            [InlineKeyboardButton("🏷️ Categorias", callback_data="bg:categories"), self._search_button(chat_type)],
            [InlineKeyboardButton("🏠 Início", callback_data="bg:home"),
             InlineKeyboardButton("🎲 Sugerir um jogo", callback_data="bg:play")],
        ])
        return caption, InlineKeyboardMarkup(rows), None

    def _categories_view(self, games: list[dict[str, Any]], chat_type: str):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        buttons = [InlineKeyboardButton(f"🕹️ Todos os jogos ({len(games)})", callback_data="bg:games:all:0")]
        for category, label in _CATEGORIES.items():
            count = sum(game.get("category") == category for game in games)
            if count:
                buttons.append(InlineKeyboardButton(f"{_CATEGORY_ICONS[category]} {label} ({count})",
                                                   callback_data=f"bg:games:{category}:0"))
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton("🏠 Início", callback_data="bg:home"), self._search_button(chat_type)])
        caption = "<b>🏷️ Escolha uma categoria</b>\nFiltre o catálogo pelo tipo de jogo que você quer jogar."
        if not games:
            caption += "\n\nAinda não há jogos disponíveis."
        return caption, InlineKeyboardMarkup(rows), None

    def _suggestion_view(self, games: list[dict[str, Any]], chat_type: str, excluded: str | None = None):
        if not games:
            return self._catalog_view(games, chat_type)
        candidates = [game for game in games if game["slug"] != excluded] or games
        return self._game_view(random.choice(candidates), chat_type)

    @staticmethod
    def _rejection(exc: Exception) -> str:
        return str(exc).strip().casefold().removeprefix("forbidden: ").removeprefix("bad request: ")

    async def _deliver(self, update: Any, view: tuple, query: Any = None) -> None:
        from telegram import InputMediaPhoto
        from telegram.error import BadRequest, Forbidden

        caption, keyboard, slug = view
        message = query.message if query is not None else update.effective_message
        if message is None:
            return
        has_photo = bool(getattr(message, "photo", None))
        try:
            if query is None:
                await message.reply_photo(photo=_photo_url(self.app_url, slug), caption=caption,
                                          parse_mode="HTML", reply_markup=keyboard)
            elif has_photo:
                await query.edit_message_media(media=InputMediaPhoto(_photo_url(self.app_url, slug),
                                               caption=caption, parse_mode="HTML"), reply_markup=keyboard)
            else:
                await query.edit_message_text(caption, parse_mode="HTML", reply_markup=keyboard)
        except (BadRequest, Forbidden) as exc:
            rejection = self._rejection(exc)
            if query is not None and isinstance(exc, BadRequest) and (
                    rejection == "message is not modified" or rejection.startswith("message is not modified:")):
                return
            if (query is not None and not has_photo) or rejection not in _PHOTO_PERMISSION_ERRORS:
                raise
            # Definitive media rejection only; never resend an uncertain network operation.
            await message.reply_text(caption, parse_mode="HTML", reply_markup=keyboard)

    async def send_home(self, update: Any, context: Any) -> None:
        if update.effective_message is not None:
            await self._deliver(update, self._home_view(self._chat_type(update)))

    async def send_start(self, update: Any, context: Any) -> None:
        if update.effective_message is None:
            return
        chat_type = self._chat_type(update)
        argument = str(context.args[0]) if context.args else ""
        # /start game_<slug> opens exactly that game, never a fuzzy or random substitute.
        if argument.startswith("game_"):
            slug = argument[5:]
            selected = next((game for game in _catalog_games(self.catalog_loader()) if game["slug"] == slug), None)
            view = self._game_view(selected, chat_type) if selected else self._not_found_view(slug, chat_type)
        elif argument == "games":
            view = self._catalog_view(_catalog_games(self.catalog_loader()), chat_type)
        else:
            view = self._home_view(chat_type)
        await self._deliver(update, view)

    async def send_games(self, update: Any, context: Any) -> None:
        if update.effective_message is not None:
            await self._deliver(update, self._catalog_view(_catalog_games(self.catalog_loader()), self._chat_type(update)))

    async def send_play(self, update: Any, context: Any) -> None:
        if update.effective_message is None:
            return
        games, chat_type = _catalog_games(self.catalog_loader()), self._chat_type(update)
        search = " ".join(str(arg) for arg in context.args).strip()
        if search:
            found = _search_games({"games": games}, search, limit=1)
            view = self._game_view(found[0], chat_type) if found else self._not_found_view(search, chat_type)
        else:
            view = self._suggestion_view(games, chat_type)
        await self._deliver(update, view)

    async def callback_query(self, update: Any, context: Any) -> None:
        query = update.callback_query
        if query is None:
            return
        await query.answer()
        data = query.data
        if not isinstance(data, str) or query.message is None:
            return
        try:
            if len(data.encode()) > 64:
                return
        except UnicodeEncodeError:
            return
        chat_type = self._chat_type(update)
        games = _catalog_games(self.catalog_loader())
        if data == "bg:home":
            view = self._home_view(chat_type)
        elif data == "bg:categories":
            view = self._categories_view(games, chat_type)
        elif data == "bg:play" or data.startswith("bg:play:"):
            excluded = data[len("bg:play:"):] if data.startswith("bg:play:") else None
            if excluded is not None and (not _valid_slug(excluded) or not any(game["slug"] == excluded for game in games)):
                return
            if excluded is None:
                previous = getattr(query.message, "caption", None) or getattr(query.message, "text", None)
                for game in games:
                    rendered = _game_caption(game)
                    if isinstance(previous, str) and previous in {rendered, html.unescape(re.sub(r"</?b>", "", rendered))}:
                        excluded = game["slug"]
                        break
            view = self._suggestion_view(games, chat_type, excluded)
        else:
            match = re.fullmatch(r"bg:games:([a-z0-9-]+):(0|[1-9][0-9]{0,5})", data)
            if match is None:
                return
            category, offset = match[1], int(match[2])
            if category != "all" and (category not in _CATEGORIES or not any(game.get("category") == category for game in games)):
                return
            total = len(self._ordered_games(games, category))
            if offset % _CATALOG_PAGE_SIZE or (offset >= total and offset != 0):
                return
            view = self._catalog_view(games, chat_type, category, offset)
        await self._deliver(update, view, query)

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
                    "🎮 Jogar agora" if self.direct_app_available else "🔗 Abrir jogo no bot", url=self._link(slug),
                )]]),
            ))
        next_offset = str(offset + len(page)) if offset + len(page) < len(games) else ""
        await query.answer(
            results, button=InlineQueryResultsButton(text="🕹️ Abrir catálogo de jogos",
                                                    web_app=WebAppInfo(url=self.app_url)),
            next_offset=next_offset, cache_time=20, is_personal=False,
        )


async def _configure_profile(bot: Any, app_url: str) -> None:
    """Reconcile optional presentation once; a Telegram rate limit must not stop polling."""
    from telegram import BotCommand, MenuButtonWebApp, WebAppInfo
    from telegram.error import RetryAfter

    commands = [
        BotCommand("jogar", "🎲 Receber uma sugestão ou buscar um jogo"),
        BotCommand("games", "🕹️ Navegar pelo catálogo e categorias"),
        BotCommand("home", "🏠 Voltar ao início"),
    ]
    menu = MenuButtonWebApp(text="🎮 Jogos", web_app=WebAppInfo(url=app_url))
    settings = [
        ("get_my_name", "set_my_name", {"name": "Baltigo Games"},
         lambda value: value.name, "Baltigo Games"),
        ("get_my_description", "set_my_description", {"description": _DESCRIPTION},
         lambda value: value.description, _DESCRIPTION),
        ("get_my_short_description", "set_my_short_description", {"short_description": _SHORT_DESCRIPTION},
         lambda value: value.short_description, _SHORT_DESCRIPTION),
        ("get_my_commands", "set_my_commands", {"commands": commands},
         lambda value: tuple((command.command, command.description) for command in value),
         tuple((command.command, command.description) for command in commands)),
        ("get_chat_menu_button", "set_chat_menu_button", {"menu_button": menu},
         lambda value: (value.type, getattr(value, "text", None),
                        getattr(getattr(value, "web_app", None), "url", None)),
         ("web_app", menu.text, app_url)),
    ]
    for getter, setter, arguments, project, desired in settings:
        operation = getter
        try:
            current = await getattr(bot, getter)()
            if project(current) != desired:
                operation = setter
                await getattr(bot, setter)(**arguments)
        except RetryAfter as exc:
            delay = exc.retry_after
            seconds = delay.total_seconds() if hasattr(delay, "total_seconds") else float(delay)
            _LOGGER.warning("Telegram optional profile deferred operation=%s retry_after_seconds=%s", operation, seconds)
            # Stop this optional batch: no retries, sleeps or further profile requests during the limit.
            break


async def start_bot(token: str, app_url: str, catalog_loader: Callable[[], dict[str, Any]]):
    from telegram import Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, InlineQueryHandler

    application = Application.builder().token(token).build()
    await application.initialize()
    me = await application.bot.get_me()
    ui = _BotUI(app_url, catalog_loader, me.username, bool(getattr(me, "has_main_web_app", False)),
                os.getenv("TELEGRAM_MINI_APP_SHORT_NAME", "").strip())
    application.add_handler(CommandHandler("start", ui.send_start))
    application.add_handler(CommandHandler("home", ui.send_home))
    application.add_handler(CommandHandler("games", ui.send_games))
    application.add_handler(CommandHandler("jogar", ui.send_play))
    application.add_handler(CallbackQueryHandler(ui.callback_query, pattern=r"^bg:"))
    application.add_handler(InlineQueryHandler(ui.inline_query))
    await _configure_profile(application.bot, app_url)
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await application.start()
    return application
