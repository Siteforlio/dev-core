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
_MODEL = "deepseek-chat"
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
