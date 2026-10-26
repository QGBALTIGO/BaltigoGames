"""Independent processor gate; no Telegram connection or real credentials."""
import asyncio
import inspect
from types import SimpleNamespace

import pytest
from telegram import Chat, Update
from telegram.ext import Application, BaseUpdateProcessor

from app.bot_transport import ChatUpdateProcessor


def update(chat_id=None):
    return SimpleNamespace(effective_chat=Chat(chat_id, "private") if chat_id is not None else None)


async def reached(event):
    await asyncio.wait_for(event.wait(), 2)


def test_real_sdk_accepts_processor_without_overriding_its_final_admission():
    processor = ChatUpdateProcessor()
    application = Application.builder().token("123456:synthetic-not-real").concurrent_updates(processor).build()
    assert application.update_processor is processor
    assert application.concurrent_updates == 64
    assert ChatUpdateProcessor.process_update is BaseUpdateProcessor.process_update


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_concurrency_limit_is_rejected(limit):
    with pytest.raises(ValueError):
        ChatUpdateProcessor(limit)


@pytest.mark.asyncio
async def test_slow_chat_does_not_delay_another_conversation():
    entered, release, other_done = asyncio.Event(), asyncio.Event(), asyncio.Event()
    processor = ChatUpdateProcessor(3)
    events = []

    async def first():
        events.append("first-start")
        entered.set()
        await release.wait()
        events.append("first-end")

    async def second():
        events.append("second")

    async def other():
        events.append("other")
        other_done.set()

    async with processor:
        one = asyncio.create_task(processor.process_update(update(1), first()))
        await reached(entered)
        two = asyncio.create_task(processor.process_update(update(1), second()))
        three = asyncio.create_task(processor.process_update(update(2), other()))
        try:
            await reached(other_done)
            assert events == ["first-start", "other"]
        finally:
            release.set()
            await asyncio.gather(one, two, three)
    assert events == ["first-start", "other", "first-end", "second"]
    assert processor.current_concurrent_updates == 0
    assert not processor._chat_locks


@pytest.mark.asyncio
async def test_same_chat_keeps_fifo_order_for_commands_and_callbacks():
    processor = ChatUpdateProcessor(16)
    release, first_entered = asyncio.Event(), asyncio.Event()
    events = []

    async def work(index):
        if index == 0:
            first_entered.set()
            await release.wait()
        events.append(index)

    async with processor:
        tasks = [asyncio.create_task(processor.process_update(update(-100), work(0)))]
        await reached(first_entered)
        tasks.extend(asyncio.create_task(processor.process_update(update(-100), work(i))) for i in range(1, 12))
        await asyncio.sleep(0)
        assert not events
        release.set()
        await asyncio.gather(*tasks)
    assert events == list(range(12))
    assert not processor._chat_locks


@pytest.mark.asyncio
async def test_chatless_updates_are_independent():
    processor = ChatUpdateProcessor(3)
    entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def slow():
        entered.set()
        await release.wait()

    async def quick():
        completed.set()

    async with processor:
        first = asyncio.create_task(processor.process_update(Update(1), slow()))
        await reached(entered)
        second = asyncio.create_task(processor.process_update(Update(2), quick()))
        try:
            await reached(completed)
        finally:
            release.set()
            await asyncio.gather(first, second)
    assert not processor._chat_locks


@pytest.mark.asyncio
async def test_handler_failure_releases_chat_and_global_capacity():
    processor = ChatUpdateProcessor(2)
    entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def fail():
        entered.set()
        await release.wait()
        raise RuntimeError("isolated synthetic failure")

    async def recover():
        completed.set()

    async with processor:
        failed = asyncio.create_task(processor.process_update(update(10), fail()))
        await reached(entered)
        recovered = asyncio.create_task(processor.process_update(update(10), recover()))
        release.set()
        with pytest.raises(RuntimeError, match="synthetic failure"):
            await failed
        await reached(completed)
        await recovered
    assert not processor._chat_locks
    assert processor.current_concurrent_updates == 0


@pytest.mark.asyncio
async def test_cancelling_active_handler_releases_same_chat_waiter():
    processor = ChatUpdateProcessor(2)
    entered, completed = asyncio.Event(), asyncio.Event()

    async def wait_forever():
        entered.set()
        await asyncio.Future()

    async def recover():
        completed.set()

    async with processor:
        first = asyncio.create_task(processor.process_update(update(10), wait_forever()))
        await reached(entered)
        second = asyncio.create_task(processor.process_update(update(10), recover()))
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        await reached(completed)
        await second
    assert not processor._chat_locks
    assert processor.current_concurrent_updates == 0


@pytest.mark.asyncio
async def test_cancelled_chat_waiter_closes_unstarted_handler_and_keeps_order():
    processor = ChatUpdateProcessor(3)
    entered, release = asyncio.Event(), asyncio.Event()
    events = []

    async def hold():
        entered.set()
        await release.wait()

    async def should_not_run():
        events.append("cancelled")

    async def last():
        events.append("last")

    async with processor:
        first = asyncio.create_task(processor.process_update(update(20), hold()))
        await reached(entered)
        unused = should_not_run()
        cancelled = asyncio.create_task(processor.process_update(update(20), unused))
        third = asyncio.create_task(processor.process_update(update(20), last()))
        await asyncio.sleep(0)
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        assert inspect.getcoroutinestate(unused) == inspect.CORO_CLOSED
        release.set()
        await asyncio.gather(first, third)
    assert events == ["last"]
    assert not processor._chat_locks
    assert processor.current_concurrent_updates == 0


@pytest.mark.asyncio
async def test_limit_bounds_active_work_across_distinct_chats():
    processor = ChatUpdateProcessor(4)
    full, release = asyncio.Event(), asyncio.Event()
    running = maximum = completed = 0

    async def work():
        nonlocal running, maximum, completed
        running += 1
        maximum = max(maximum, running)
        if running == 4:
            full.set()
        try:
            await release.wait()
        finally:
            running -= 1
            completed += 1

    async with processor:
        tasks = [asyncio.create_task(processor.process_update(update(i), work())) for i in range(20)]
        await reached(full)
        assert maximum == processor.current_concurrent_updates == 4
        release.set()
        await asyncio.gather(*tasks)
    assert maximum == 4 and completed == 20
    assert not processor._chat_locks


@pytest.mark.asyncio
async def test_same_chat_waiters_count_toward_sdk_limit_documented_saturation():
    """Keep the admission tradeoff explicit instead of claiming fair scheduling."""
    processor = ChatUpdateProcessor(2)
    entered, release, other_done = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def hold():
        entered.set()
        await release.wait()

    async def queued():
        pass

    async def other():
        other_done.set()

    async with processor:
        first = asyncio.create_task(processor.process_update(update(1), hold()))
        await reached(entered)
        same = asyncio.create_task(processor.process_update(update(1), queued()))
        await asyncio.sleep(0)
        assert processor.current_concurrent_updates == 2
        unrelated = asyncio.create_task(processor.process_update(update(2), other()))
        await asyncio.sleep(0)
        assert not other_done.is_set()
        release.set()
        await asyncio.gather(first, same, unrelated)
    assert other_done.is_set()
    assert not processor._chat_locks


@pytest.mark.asyncio
async def test_many_completed_conversations_leave_no_lock_registry_growth():
    processor = ChatUpdateProcessor(64)

    async def work():
        await asyncio.sleep(0)

    async with processor:
        for batch in range(4):
            await asyncio.gather(*(processor.process_update(update(batch * 300 + i), work()) for i in range(300)))
            assert not processor._chat_locks
    assert processor.current_concurrent_updates == 0
