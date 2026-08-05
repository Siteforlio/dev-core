"""
In-process event bus — replaces Redis pub/sub for single-user desktop app.
Publishers call publish(channel, message). Subscribers get an asyncio.Queue
via subscribe(channel) and read from it.
"""
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# channel → list of subscriber queues
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


def publish(channel: str, message: str) -> None:
    """Publish a message to all subscribers of a channel (sync-safe)."""
    for q in _subscribers.get(channel, []):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("[event_bus] queue full for channel %s, dropping message", channel)


def subscribe(channel: str) -> asyncio.Queue:
    """Return a new Queue that receives all future messages on this channel."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[channel].append(q)
    return q


def unsubscribe(channel: str, q: asyncio.Queue) -> None:
    """Remove a subscriber queue when a WebSocket disconnects."""
    try:
        _subscribers[channel].remove(q)
    except ValueError:
        pass
