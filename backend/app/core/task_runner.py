"""
Lightweight asyncio-based background task runner.
Replaces Celery + Redis for single-user desktop mode.
"""
import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_runner: "TaskRunner | None" = None


def get_runner() -> "TaskRunner":
    global _runner
    if _runner is None:
        _runner = TaskRunner()
    return _runner


class TaskRunner:
    def __init__(self):
        self._tasks: set[asyncio.Task] = set()
        self._periodic: list[asyncio.Task] = []
        self._running = True

    def submit(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        """Fire-and-forget a coroutine."""
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._on_done)
        return task

    def _on_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error("[task_runner] task failed: %s", task.exception())

    def schedule_periodic(self, coro_fn, interval_seconds: float) -> None:
        """Run coro_fn() repeatedly every interval_seconds."""
        async def _loop():
            while self._running:
                try:
                    await coro_fn()
                except Exception as e:
                    logger.error("[task_runner] periodic task error: %s", e)
                await asyncio.sleep(interval_seconds)
        task = asyncio.ensure_future(_loop())
        self._periodic.append(task)

    async def shutdown(self) -> None:
        global _runner
        self._running = False
        for t in self._periodic:
            t.cancel()
        all_tasks = list(self._tasks) + self._periodic
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
        _runner = None
