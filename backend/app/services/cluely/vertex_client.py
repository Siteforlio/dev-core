"""
Lightweight async Vertex AI REST client.

Replaces the google-generativeai SDK with direct httpx calls to
aiplatform.googleapis.com so we can use an API key instead of ADC.

Endpoint:
  https://aiplatform.googleapis.com/v1/publishers/google/models/
      gemini-2.5-flash-lite:generateContent?key=<KEY>
  https://aiplatform.googleapis.com/v1/publishers/google/models/
      gemini-2.5-flash-lite:streamGenerateContent?alt=sse&key=<KEY>
"""
import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash-lite"
_TIMEOUT = 60.0


def _build_body(prompt: str, system: str = "") -> dict:
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    return body


async def vertex_generate(prompt: str, system: str = "") -> str:
    """Non-streaming call — returns full text."""
    url = f"{_BASE}:generateContent?key={settings.vertex_api_key}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=_build_body(prompt, system))
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def vertex_stream(prompt: str, system: str = "") -> AsyncGenerator[str, None]:
    """Streaming call — yields text deltas via SSE."""
    url = f"{_BASE}:streamGenerateContent?alt=sse&key={settings.vertex_api_key}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream("POST", url, json=_build_body(prompt, system)) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    chunk = json.loads(raw)
                    text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                    if text:
                        yield text
                except (KeyError, json.JSONDecodeError):
                    continue
