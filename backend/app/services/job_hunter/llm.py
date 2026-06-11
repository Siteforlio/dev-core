"""
Shared LLM utility for job hunter services.

Routing:
  deepseek-v4-flash  — default: fast and cheap, used for scoring/classification/extraction
  deepseek-v4-pro    — quality tier: used for bullet rewriting and cover letters
"""
import logging

logger = logging.getLogger(__name__)

_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_MODEL_FLASH = "deepseek-v4-flash"
_MODEL_PRO   = "deepseek-v4-pro"
_MODEL       = _MODEL_FLASH  # default


async def call_llm(
    prompt: str,
    max_tokens: int = 1000,
    *,
    json_mode: bool = False,
    quality: bool = False,   # True → deepseek-v4-pro (bullet rewriting, cover letters)
    thinking: bool = False,  # False → disable chain-of-thought reasoning (direct output, no empty content bug)
) -> str:
    """Send a prompt to DeepSeek and return the text response.

    quality=False (default) → deepseek-v4-flash  ($0.14/M in, $0.28/M out)
    quality=True            → deepseek-v4-pro     ($0.44/M in, $0.87/M out)
    thinking=False          → disables internal reasoning, output starts immediately
    """
    import httpx
    from app.core.config import settings

    model = _MODEL_PRO if quality else _MODEL_FLASH

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": False,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if not thinking:
        body["thinking"] = {"type": "disabled"}

    logger.debug("call_llm → model=%s max_tokens=%d json_mode=%s\n--- PROMPT ---\n%s\n--- END PROMPT ---", model, max_tokens, json_mode, prompt)

    timeout = httpx.Timeout(10.0, read=120.0)  # 10s connect, 120s read (Pro model with large outputs)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(_DEEPSEEK_URL, json=body, headers=headers)
        if not resp.is_success:
            logger.error("call_llm: HTTP %s — body: %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        data = resp.json()

    logger.debug("call_llm ← raw response: %s", data)

    try:
        content = data["choices"][0]["message"]["content"]
        if content is None:
            logger.warning("call_llm: content is None — finish_reason=%s", data["choices"][0].get("finish_reason"))
            return ""
        return content
    except (KeyError, IndexError) as exc:
        logger.error("call_llm: unexpected response shape %s — full response: %s", exc, data)
        return ""
