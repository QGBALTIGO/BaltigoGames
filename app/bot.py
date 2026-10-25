from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _launch_url(app_url: str, slug: str | None = None) -> str:
    if not slug:
        return app_url
    parts = urlsplit(app_url)
    params = dict(parse_qsl(parts.query))
    params["startapp"] = slug
    return urlunsplit(parts._replace(query=urlencode(params)))


def _game_link(username: str, slug: str, has_main_web_app: bool = False) -> str:
    if has_main_web_app:
        return f"https://t.me/{username}?startapp={slug}"
    return f"https://t.me/{username}?start=game_{slug}"


def _search_games(catalog: dict[str, Any], query: str, limit: int = 25) -> list[dict[str, Any]]:
    games = catalog.get("games", [])
    q = query.casefold().strip()
    if q.startswith("game:"):
        q = q[5:].strip()
    if not q:
        preferred = ["snake", "2048", "tetris", "pacman", "flappy", "car-race"]
        by_slug = {game.get("slug"): game for game in games}
        ordered = [by_slug[s] for s in preferred if s in by_slug]
        ordered.extend(game for game in games if game not in ordered)
        return ordered[:limit]

    def score(game: dict[str, Any]) -> tuple[int, str]:
        name = str(game.get("name", ""))
        slug = str(game.get("slug", ""))
        tags = " ".join(game.get("tags", []))
        category = str(game.get("category", ""))
        hay = f"{name} {slug} {tags} {category}".casefold()
        if slug.casefold() == q or name.casefold() == q:
            rank = 0
        elif name.casefold().startswith(q) or slug.casefold().startswith(q):
            rank = 1
        elif q in hay:
            rank = 2
        else:
            rank = 99
        return rank, name.casefold()

    found = [game for game in games if score(game)[0] < 99]
    return sorted(found, key=score)[:limit]


async def start_bot(token: str, app_url: str, catalog_loader: Callable[[], dict[str, Any]]):
    from telegram import (
        BotCommand,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        InlineQueryResultArticle,
        InlineQueryResultsButton,
        InputTextMessageContent,
        MenuButtonWebApp,
        Update,
        WebAppInfo,
    )
    from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler

    application = Application.builder().token(token).build()
    await application.initialize()
    me = await application.bot.get_me()
    await application.bot.set_my_name(name="Baltigo Games")
    username = me.username

    def game_link(slug: str) -> str:
        return _game_link(username, slug, bool(getattr(me, "has_main_web_app", False)))

    async def send_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        argument = context.args[0] if context.args else ""
        slug = argument[5:] if argument.startswith("game_") else None
        selected = next((game for game in catalog_loader().get("games", [])
                         if game.get("slug") == slug), None)
        launch_url = _launch_url(app_url, selected["slug"] if selected else None)
        text = (
            "*Baltigo Games*\n\n"
            "Seu fliperama dentro do Telegram. Abra o catálogo, escolha um jogo e jogue sem instalar nada."
        )
        if selected:
            text = f"{selected['name']}\n\nToque abaixo para abrir o jogo no Baltigo Games."
        private_chat = update.effective_chat and update.effective_chat.type == "private"
        open_button = (
            InlineKeyboardButton("Abrir Baltigo Games", web_app=WebAppInfo(url=launch_url))
            if private_chat else InlineKeyboardButton(
                "Abrir Baltigo Games", url=f"https://t.me/{username}?start={argument if selected else 'games'}")
        )
        keyboard = InlineKeyboardMarkup(
            [
                [open_button],
                [InlineKeyboardButton("Buscar um jogo aqui", switch_inline_query_current_chat="")],
            ]
        )
        if update.effective_message:
            await update.effective_message.reply_text(text.replace("*Baltigo Games*", "Baltigo Games"), reply_markup=keyboard)

    async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.inline_query is None:
            return
        games = _search_games(catalog_loader(), update.inline_query.query)
        results = []
        for game in games:
            slug = game.get("slug", "game")
            name = game.get("name", slug)
            description = game.get("description") or "Jogue agora no Baltigo Games"
            results.append(
                InlineQueryResultArticle(
                    id=str(slug),
                    title=name,
                    description=description,
                    input_message_content=InputTextMessageContent(
                        f"{name}\nAbra e jogue agora no Baltigo Games.",
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("Jogar", url=game_link(str(slug)))]]
                    ),
                )
            )

        button = InlineQueryResultsButton(
            text="Abrir catálogo completo",
            web_app=WebAppInfo(url=app_url),
        )
        await update.inline_query.answer(
            results,
            button=button,
            cache_time=20,
            is_personal=False,
        )

    application.add_handler(CommandHandler(["start", "jogar", "games"], send_home))
    application.add_handler(InlineQueryHandler(inline_query))

    await application.bot.set_my_commands(
        [
            BotCommand("jogar", "Abrir o catálogo de jogos"),
            BotCommand("games", "Ver o Baltigo Games"),
        ]
    )
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="Jogos", web_app=WebAppInfo(url=app_url))
    )
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await application.start()
    return application
