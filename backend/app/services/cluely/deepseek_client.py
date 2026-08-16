"""
DeepSeek API client — OpenAI-compatible REST interface.

Uses httpx SSE streaming for token-by-token delivery.
Model: deepseek-chat (DeepSeek-V3) for all real-time paths.
"""
import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.deepseek.com"
_MODEL = "deepseek-v4-pro"
_TIMEOUT = 60.0


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }


def _build_body(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
    stream: bool = True,
) -> dict:
    return {
        "model": _MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }


def _to_messages(prompt: str, system: str = "") -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


async def deepseek_stream(
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream token deltas from DeepSeek chat API."""
    url = f"{_BASE}/chat/completions"
    body = _build_body(_to_messages(prompt, system), temperature=temperature, max_tokens=max_tokens)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream("POST", url, json=body, headers=_headers()) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    chunk = json.loads(raw)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (KeyError, json.JSONDecodeError):
                    continue


async def deepseek_generate(
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> str:
    """Non-streaming call — returns full response text."""
    url = f"{_BASE}/chat/completions"
    body = _build_body(
        _to_messages(prompt, system),
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=body, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def deepseek_with_tools(
    messages: list[dict],
    tools: list[dict],
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> dict:
    """
    Non-streaming call with tool schemas.
    Returns the raw choice dict — check choice["message"].get("tool_calls").
    """
    url = f"{_BASE}/chat/completions"
    body = {
        "model": _MODEL,
        "messages": _sanitize_messages(messages),
        "tools": tools,
        "tool_choice": "auto",
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=body, headers=_headers())
        if not resp.is_success:
            logger.error("[deepseek] 400 body: %s", resp.text[:1000])
            resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]


def _strip_dsml(text: str) -> str:
    """Remove DeepSeek V4 DSML tool-call markup that leaks into streamed content."""
    import re
    # Remove any <｜｜DSML｜｜...> tags and their content
    return re.sub(r'<｜｜DSML｜｜.*?(?:>|$)', '', text, flags=re.DOTALL)


def _sanitize_messages(messages: list[dict]) -> list[dict]:
    """
    Remove or fix messages that would cause DeepSeek to return 400:
    - assistant messages with tool_calls must have content=null (not "")
    - every tool_call_id in an assistant message must have a matching tool response
    - drop orphaned tool messages (no preceding assistant tool_calls)
    """
    out = []
    in_tool_response = False  # True while we still expect tool messages for current assistant

    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            if msg.get("tool_calls"):
                out.append({**msg, "content": msg.get("content") or None})
                in_tool_response = True
            else:
                in_tool_response = False
                out.append(msg)
        elif role == "tool":
            if in_tool_response:
                out.append(msg)
                # Check if all tool_calls are now satisfied
                last_assistant = next((m for m in reversed(out) if m.get("role") == "assistant" and m.get("tool_calls")), None)
                if last_assistant:
                    expected_ids = {tc["id"] for tc in last_assistant["tool_calls"]}
                    provided_ids = {m["tool_call_id"] for m in out if m.get("role") == "tool"}
                    if expected_ids.issubset(provided_ids):
                        in_tool_response = False
            # else: orphaned tool message — drop it
        else:
            in_tool_response = False
            out.append(msg)
    return out


async def deepseek_stream_messages(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream token deltas from a full messages list (for multi-turn tool conversations)."""
    url = f"{_BASE}/chat/completions"
    body = {
        "model": _MODEL,
        "messages": _sanitize_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    # Buffer to catch DSML tags that span chunk boundaries
    buf = ""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream("POST", url, json=body, headers=_headers()) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw or raw == "[DONE]":
                    if buf:
                        clean = _strip_dsml(buf)
                        if clean:
                            yield clean
                    continue
                try:
                    chunk = json.loads(raw)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if not delta:
                        continue
                    buf += delta
                    # Only flush if we're not in the middle of a DSML tag
                    if "<｜｜DSML｜｜" not in buf:
                        clean = _strip_dsml(buf)
                        if clean:
                            yield clean
                        buf = ""
                    elif buf.count("<｜｜DSML｜｜") <= buf.count(">"):
                        # Tag appears closed — flush
                        clean = _strip_dsml(buf)
                        if clean:
                            yield clean
                        buf = ""
                except (KeyError, json.JSONDecodeError):
                    continue
