"""
Shared LLM utility for job hunter services.

Priority order:
  1. Gemini 2.5 Flash Lite via aiplatform.googleapis.com (VERTEX_API_KEY)
     — no daily quota cap, on-demand billing, fastest
  2. Gemini 2.0 Flash via generativelanguage.googleapis.com (GEMINI_API_KEY)
     — free tier: 15 RPM, 1 500 RPD, 1 M TPM
  3. Anthropic Haiku (ANTHROPIC_API_KEY) — paid fallback

Vertex endpoint:
  POST https://aiplatform.googleapis.com/v1/publishers/google/models/
       gemini-2.5-flash-lite:generateContent?key={VERTEX_API_KEY}
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

_VERTEX_URL = (
    "https://aiplatform.googleapis.com/v1/publishers/google/models/"
    "gemini-2.5-flash-lite:generateContent"
)

# Semaphore: cap concurrent Vertex calls (generous — on-demand, no free-tier RPM cap)
_vertex_sem = asyncio.Semaphore(8)

# Semaphore: stay under 15 RPM free-tier limit for standard Gemini
_gemini_sem = asyncio.Semaphore(12)


async def call_llm(prompt: str, max_tokens: int = 1000, *, json_mode: bool = False) -> str:
    """
    Send a prompt and return the text response.

    Preference order:
      1. Vertex AI  (gemini-2.5-flash-lite, VERTEX_API_KEY)
      2. Gemini 2.0 Flash free tier (GEMINI_API_KEY)
      3. Anthropic Haiku (ANTHROPIC_API_KEY)
    """
    from app.core.config import settings

    if settings.vertex_api_key:
        return await _call_vertex(prompt, max_tokens)
    if settings.gemini_api_key:
        return await _call_gemini(prompt, max_tokens, json_mode=json_mode)
    return await _call_haiku(prompt, max_tokens)


async def _call_vertex(prompt: str, max_tokens: int) -> str:
    """
    Direct httpx call to aiplatform.googleapis.com — no SDK needed.
    """
    import httpx
    from app.core.config import settings

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }

    async with _vertex_sem:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                _VERTEX_URL,
                params={"key": settings.vertex_api_key},
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        logger.warning("_call_vertex: unexpected response shape: %s | %s", exc, data)
        return ""


async def _call_gemini(prompt: str, max_tokens: int, *, json_mode: bool = False) -> str:
    from google import genai
    from google.genai import types
    from app.core.config import settings

    async with _gemini_sem:
        client = genai.Client(api_key=settings.gemini_api_key)
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
            config=config,
        )
        return response.text or ""


async def _call_haiku(prompt: str, max_tokens: int) -> str:
    from anthropic import AsyncAnthropic
    from app.core.config import settings

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        timeout=30.0,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
