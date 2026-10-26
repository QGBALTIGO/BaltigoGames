"""Bounded Telegram concurrency, with ordered updates within each conversation."""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any

from telegram.ext import BaseUpdateProcessor


@dataclass
class _ChatLock:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


class ChatUpdateProcessor(BaseUpdateProcessor):
    """Let separate chats progress concurrently without reordering a single chat.

    The SDK's public processor API admits an update before calling this class.
    Consequently the configured limit includes updates waiting for their chat:
    64 pending updates from one chat can fill a 64-update limit. This is a bounded
    processor, not a fairness scheduler. We retain the SDK's task lifecycle and
    semaphore behavior rather than bypassing its final ``process_update`` method.
    """

    def __init__(self, max_concurrent_updates: int = 64):
        super().__init__(max_concurrent_updates=max_concurrent_updates)
        self._chat_locks: dict[int, _ChatLock] = {}

    async def initialize(self) -> None:
        """No independent worker or network resource needs initialization."""

    async def shutdown(self) -> None:
        """The application owns update tasks and drains them before shutdown."""

    async def do_process_update(self, update: object, coroutine: Awaitable[Any]) -> None:
        chat = getattr(update, "effective_chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is None:
            # Inline queries and other chatless updates must not share a global lock.
            await coroutine
            return

        entry = self._chat_locks.setdefault(chat_id, _ChatLock())
        entry.users += 1
        started = False
        try:
            async with entry.lock:
                started = True
                await coroutine
        finally:
            entry.users -= 1
            if entry.users == 0:
                del self._chat_locks[chat_id]
            if not started and inspect.iscoroutine(coroutine):
                # A cancelled waiter never reached the SDK handler coroutine.
                coroutine.close()
