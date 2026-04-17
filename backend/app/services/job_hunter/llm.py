"""
Shared LLM utility for job hunter services.

Uses Gemini 2.0 Flash (free tier) when a Gemini API key is configured,
falls back to Anthropic Haiku otherwise.

Free Gemini limits (as of 2025):
  - gemini-2.0-flash: 15 RPM, 1 500 RPD, 1 M TPM — no cost
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

# Semaphore: stay under 15 RPM free-tier limit
_gemini_sem = asyncio.Semaphore(12)


async def call_llm(prompt: str, max_tokens: int = 1000, *, json_mode: bool = False) -> str:
    """
    Send a prompt and return the text response.

    Preference order:
      1. Gemini 2.0 Flash  (free)
      2. Anthropic Haiku   (paid fallback)
    """
    from app.core.config import settings

    if settings.gemini_api_key:
        return await _call_gemini(prompt, max_tokens, json_mode=json_mode)
    return await _call_haiku(prompt, max_tokens)


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
