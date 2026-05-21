"""
Global WebSocket connection registry for graceful shutdown.

Usage:
  1. In each WS handler: `ws_registry.register(asyncio.current_task())`
  2. In lifespan shutdown: `await ws_registry.close_all()`

When close_all() cancels a task, any CancelledError propagates through the
WS handler's event loop, causing WebSocketDisconnect-like behaviour and
triggering the handler's finally block for proper cleanup.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_active: set[asyncio.Task] = set()


def register(task: asyncio.Task | None) -> None:
    """Register a WS handler task. Automatically deregisters when done."""
    if task is None:
        return
    _active.add(task)
    task.add_done_callback(_active.discard)


def count() -> int:
    return len(_active)


async def close_all(timeout: float = 10.0) -> None:
    """
    Cancel all active WS handler tasks and wait up to `timeout` seconds
    for them to finish their cleanup (finally blocks).
    """
    tasks = list(_active)
    if not tasks:
        return
    logger.info("[ws_registry] graceful shutdown: closing %d active connection(s)", len(tasks))
    for task in tasks:
        task.cancel()
    _, pending = await asyncio.wait(tasks, timeout=timeout)
    if pending:
        logger.warning("[ws_registry] %d connection(s) did not finish within %ss", len(pending), timeout)
    else:
        logger.info("[ws_registry] all WebSocket connections closed cleanly")
