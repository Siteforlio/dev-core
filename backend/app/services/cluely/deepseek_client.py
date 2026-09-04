"""
DeepSeek API client — OpenAI-compatible REST interface.

Uses httpx SSE streaming for token-by-token delivery.

Model selection:
  - STREAM model (real-time overlay): deepseek-v4-flash — no reasoning overhead,
    first token in ~300-600ms.  The overlay needs speed, not deep thinking.
  - GENERATE model (background tasks: titles, summaries, outcome inference):
    deepseek-v4-pro — higher quality, reasoning overhead is fine for async tasks.

A persistent httpx.AsyncClient is reused across requests to keep TCP/TLS
connections alive (HTTP/2 multiplexing where supported).  This eliminates
the ~200-500ms TLS handshake that occurred on every call when a fresh
client was created per request.
"""
import json
import logging
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.deepseek.com"
_MODEL_FAST = "deepseek-v4-flash"     # streaming / real-time — speed-critical
_MODEL_DEEP = "deepseek-v4-pro"       # background / non-streaming — quality-critical
_TIMEOUT = 60.0

# Persistent client — reused across all calls for connection pooling.
# Lazy-initialized on first use so module import doesn't trigger network.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        # Use HTTP/2 if h2 is installed, otherwise fall back to HTTP/1.1
        try:
            import h2  # noqa: F401
            use_h2 = True
        except ImportError:
            use_h2 = False
        _client = httpx.AsyncClient(
            timeout=_TIMEOUT,
            http2=use_h2,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=120,
            ),
        )
    return _client


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _build_body(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 512,
    stream: bool = True,
    model: str | None = None,
    reasoning: bool = False,
) -> dict:
    body: dict = {
        "model": model or (_MODEL_FAST if stream else _MODEL_DEEP),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if not reasoning:
        body["reasoning_effort"] = "none"
    return body


def _to_messages(prompt: str, system: str = "") -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


async def deepseek_stream(
    prompt: str,
    api_key: str,
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream token deltas from DeepSeek chat API."""
    import time as _time
    t_start = _time.monotonic()
    url = f"{_BASE}/chat/completions"
    body = _build_body(_to_messages(prompt, system), temperature=temperature, max_tokens=max_tokens)
    client = _get_client()
    logger.info("[deepseek] stream request starting — prompt=%d chars", len(prompt))
    async with client.stream("POST", url, json=body, headers=_headers(api_key)) as resp:
        logger.info("[deepseek] stream connected in %dms — status=%d",
                    round((_time.monotonic() - t_start) * 1000), resp.status_code)
        resp.raise_for_status()
        first_token = True
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                chunk = json.loads(raw)
                delta_obj = chunk["choices"][0]["delta"]
                # DeepSeek v4 models put the actual response in
                # "reasoning_content" (chain-of-thought output), while
                # "content" is often empty or null.  Yield whichever has text.
                delta = delta_obj.get("content") or delta_obj.get("reasoning_content") or ""
                if delta:
                    if first_token:
                        logger.info("[deepseek] first token in %dms",
                                    round((_time.monotonic() - t_start) * 1000))
                        first_token = False
                    yield delta
            except (KeyError, json.JSONDecodeError):
                continue


async def deepseek_generate(
    prompt: str,
    api_key: str,
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
    client = _get_client()
    resp = await client.post(url, json=body, headers=_headers(api_key))
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content") or ""


async def deepseek_with_tools(
    messages: list[dict],
    tools: list[dict],
    api_key: str,
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> dict:
    """
    Non-streaming call with tool schemas.
    Returns the raw choice dict — check choice["message"].get("tool_calls").
    """
    url = f"{_BASE}/chat/completions"
    body = {
        "model": _MODEL_DEEP,
        "messages": _sanitize_messages(messages),
        "tools": tools,
        "tool_choice": "auto",
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "reasoning_effort": "none",
    }
    client = _get_client()
    resp = await client.post(url, json=body, headers=_headers(api_key))
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
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> AsyncGenerator[str, None]:
    """Stream token deltas from a full messages list (for multi-turn tool conversations)."""
    url = f"{_BASE}/chat/completions"
    body = {
        "model": _MODEL_FAST,
        "messages": _sanitize_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "reasoning_effort": "none",
    }
    # Buffer to catch DSML tags that span chunk boundaries
    buf = ""
    client = _get_client()
    async with client.stream("POST", url, json=body, headers=_headers(api_key)) as resp:
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
                    delta_obj = chunk["choices"][0]["delta"]
                    delta = delta_obj.get("content") or delta_obj.get("reasoning_content") or ""
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
