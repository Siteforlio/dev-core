"""
terminal_service.py — Invisible local process execution for the assessment agent.

Runs commands in a hidden subprocess with real-time stdout/stderr streaming.
The caller receives an async generator that yields structured event dicts so
the overlay WebSocket can forward them as terminal card events.

Design notes
------------
- Never opens a visible window (CREATE_NO_WINDOW on Windows).
- Caller-supplied working_dir is validated to exist before execution.
- Commands are passed as list[str] (no shell=True) to prevent injection.
- Execution is capped at MAX_RUNTIME_S seconds; process is killed on timeout.
- All output lines are tagged with stream ("stdout"/"stderr"/"system") and timestamp_ms.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from asyncio.subprocess import PIPE, Process
from typing import AsyncGenerator, Literal

logger = logging.getLogger(__name__)

MAX_RUNTIME_S = 30      # hard cap — keeps agent loops from hanging
StreamTag = Literal["stdout", "stderr", "system"]
TerminalEvent = dict    # {stream, text, timestamp_ms, cwd}


def _no_window_kwargs() -> dict:
    """Suppress a visible console window on Windows."""
    if sys.platform == "win32":
        import subprocess
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _wrap_for_shell(command: list[str]) -> tuple[list[str], bool]:
    """
    On Windows, wrap the command in 'cmd /c' so the shell handles quoting,
    PATH resolution, and built-ins (echo, where, etc.) correctly.
    Returns (wrapped_command, use_shell=False).
    """
    if sys.platform == "win32":
        return ["cmd", "/c", " ".join(command)], False
    return command, False


def _resolve_cwd(working_dir: str | None) -> str:
    """Return an absolute existing directory, or raise ValueError."""
    path = working_dir or "~"
    expanded = os.path.abspath(os.path.expanduser(os.path.expandvars(path)))
    if not os.path.isdir(expanded):
        raise ValueError(f"Working directory does not exist: {expanded!r}")
    return expanded


class TerminalService:
    """
    Execute commands invisibly and stream output line-by-line.

    Example
    -------
    async for event in svc.run(["python", "sol.py"], cwd="/tmp/project"):
        await ws.send_json({"type": "tool:terminal", **event})
    """

    async def run(
        self,
        command: list[str],
        working_dir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> AsyncGenerator[TerminalEvent, None]:
        """
        Stream terminal events for every output line until exit or timeout.

        Parameters
        ----------
        command     : argv list — never a shell string (prevents injection)
        working_dir : directory to run in; defaults to HOME
        env         : extra env vars merged over os.environ
        """
        try:
            cwd = _resolve_cwd(working_dir)
        except ValueError as exc:
            yield _ev("system", str(exc), "?")
            return

        yield _ev("system", f"$ {' '.join(command)}", cwd)

        wrapped, _ = _wrap_for_shell(command)
        merged_env = {**os.environ, **(env or {})}
        proc: Process | None = None

        try:
            proc = await asyncio.create_subprocess_exec(
                *wrapped,
                stdout=PIPE,
                stderr=PIPE,
                cwd=cwd,
                env=merged_env,
                **_no_window_kwargs(),
            )
        except FileNotFoundError:
            yield _ev("system", f"Command not found: {command[0]!r}", cwd)
            return
        except Exception as exc:
            yield _ev("system", f"Failed to start process: {exc}", cwd)
            return

        queue: asyncio.Queue[TerminalEvent | None] = asyncio.Queue()

        async def _drain(stream: asyncio.StreamReader, tag: StreamTag) -> None:
            deadline = time.monotonic() + MAX_RUNTIME_S
            while True:
                remaining = max(0.1, deadline - time.monotonic())
                try:
                    raw = await asyncio.wait_for(stream.readline(), timeout=remaining)
                except asyncio.TimeoutError:
                    await queue.put(_ev("system", "[timeout — process killed]", cwd))
                    if proc and proc.returncode is None:
                        proc.kill()
                    break
                if not raw:
                    break
                await queue.put(_ev(tag, raw.decode(errors="replace").rstrip("\n"), cwd))
            await queue.put(None)  # sentinel

        asyncio.create_task(_drain(proc.stdout, "stdout"))
        asyncio.create_task(_drain(proc.stderr, "stderr"))

        pending = 2
        deadline = time.monotonic() + MAX_RUNTIME_S

        while pending > 0:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                if proc and proc.returncode is None:
                    proc.kill()
                yield _ev("system", "[timeout — process killed]", cwd)
                break
            if item is None:
                pending -= 1
            else:
                yield item

        # Wait for clean exit
        if proc and proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                proc.kill()

        yield _ev("system", f"[exit {proc.returncode if proc else -1}]", cwd)


def _ev(stream: StreamTag, text: str, cwd: str) -> TerminalEvent:
    return {"stream": stream, "text": text, "timestamp_ms": int(time.time() * 1000), "cwd": cwd}
