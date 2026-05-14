import hashlib
import json
import re
import openai
from app.core.config import settings
from app.core.cache import cache_set, cache_get

_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


class JDParserService:
    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )

    async def _call_llm(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        return response.choices[0].message.content

    async def parse(self, jd_text: str) -> dict:
        if not jd_text or not jd_text.strip():
            return {}

        jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()
        cache_key = f"jd:{jd_hash}"

        cached = await cache_get(cache_key)
        if cached:
            return cached

        prompt = (
            "Extract structured information from this job description.\n\n"
            f"JD:\n{jd_text}\n\n"
            "Return JSON only:\n"
            '{"required_skills": [], "preferred_skills": [], "culture_signals": [], '
            '"red_flags_to_avoid": [], "implied_seniority": "", "key_responsibilities": []}'
        )
        raw = await self._call_llm(prompt)
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\{.*\}', str(raw), re.DOTALL)
            try:
                result = json.loads(match.group()) if match else {}
            except (json.JSONDecodeError, AttributeError):
                result = {}

        if result:
            await cache_set(cache_key, result, ttl=_CACHE_TTL)
        return result
