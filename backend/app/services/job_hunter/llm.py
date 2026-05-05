"""
Shared LLM utility for job hunter services.

All calls go to DeepSeek (deepseek-chat) by default.
Claude Sonnet is reserved for explicit ultra-quality requests only.
"""
import logging

logger = logging.getLogger(__name__)

_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_MODEL = "deepseek-chat"


async def call_llm(prompt: str, max_tokens: int = 1000, *, json_mode: bool = False) -> str:
    """Send a prompt to DeepSeek and return the text response."""
    import httpx
    from app.core.config import settings

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(_DEEPSEEK_URL, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.warning("call_llm: unexpected response shape: %s | %s", exc, data)
        return ""
