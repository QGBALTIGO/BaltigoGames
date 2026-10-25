from __future__ import annotations

from collections.abc import Callable
from typing import Any


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
    me = await application.bot.get_me()
    username = me.username

    def game_link(slug: str) -> str:
        return f"https://t.me/{username}?startapp={slug}"

    async def send_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = (
            "🎮 *Baltigo Games*\n\n"
            "Seu fliperama dentro do Telegram. Abra o catálogo, escolha um jogo e jogue sem instalar nada."
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🎮 Abrir Baltigo Games", web_app=WebAppInfo(url=app_url))],
                [InlineKeyboardButton("🔎 Buscar um jogo aqui", switch_inline_query_current_chat="")],
            ]
        )
        if update.effective_message:
            await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

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
                    title=f"🎮 {name}",
                    description=description,
                    input_message_content=InputTextMessageContent(
                        f"🎮 *{name}*\nAbra e jogue agora no Baltigo Games.",
                        parse_mode="Markdown",
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("▶️ Jogar", url=game_link(str(slug)))]]
                    ),
                )
            )

        button = InlineQueryResultsButton(
            text="🎮 Abrir catálogo completo",
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

    await application.initialize()
    await application.bot.set_my_commands(
        [
            BotCommand("jogar", "Abrir o catálogo de jogos"),
            BotCommand("games", "Ver o Baltigo Games"),
        ]
    )
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="🎮 Jogos", web_app=WebAppInfo(url=app_url))
    )
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    return application
