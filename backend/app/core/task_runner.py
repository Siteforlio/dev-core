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

    def schedule_periodic(self, coro_fn, interval_seconds: float, run_immediately: bool = False) -> None:
        """Run coro_fn() repeatedly every interval_seconds.
        run_immediately=False (default): waits one full interval before first run.
        """
        async def _loop():
            if not run_immediately:
                # Wait first interval before first execution — avoids firing on every restart
                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    return
            while self._running:
                try:
                    await coro_fn()
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.error("[task_runner] periodic task error: %s", e)
                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    return
        task = asyncio.ensure_future(_loop())
        self._periodic.append(task)

    async def shutdown(self, timeout: float = 5.0) -> None:
        global _runner
        self._running = False
        # Cancel everything — both periodic loops and any active fire-and-forget tasks
        all_tasks = list(self._tasks) + self._periodic
        for t in all_tasks:
            t.cancel()
        if all_tasks:
            # Wait at most `timeout` seconds for tasks to acknowledge cancellation
            try:
                await asyncio.wait_for(
                    asyncio.gather(*all_tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[task_runner] %d task(s) did not stop within %.1fs — forcing exit",
                    len(all_tasks), timeout,
                )
        _runner = None
