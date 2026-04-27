import logging
from typing import AsyncGenerator, AsyncIterator
import google.generativeai as genai
import anthropic
from app.core.config import settings
from app.core.exceptions import LLMRateLimitedError
from app.schemas.cluely import TranscriptEntry
from app.services.cluely.search_service import SearchService

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self._gemini = genai.GenerativeModel("gemini-2.0-flash")
        self._claude = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._search = SearchService()

    def _build_system_prompt(self, context: dict) -> str:
        return (
            f"You are a real-time interview assistant. The user is interviewing for "
            f"{context.get('job_title', 'a role')} at {context.get('company', 'a company')}. "
            f"Resume highlights: {context.get('resume_text', '')[:500]}. "
            f"Job description: {context.get('jd_text', '')[:500]}. "
            "Respond with a single, concise talking point (1-2 sentences). "
            "No lists. No preamble. Speak directly as a coaching whisper."
        )

    async def stream_suggestion(
        self,
        transcript: list[TranscriptEntry],
        context: dict,
        rag_chunks: list[str],
    ) -> AsyncGenerator[str, None]:
        history = "\n".join(f"{e.speaker}: {e.text}" for e in transcript[-10:])
        rag_ctx = "\n".join(rag_chunks) if rag_chunks else ""
        prompt = f"{self._build_system_prompt(context)}\n\nConversation:\n{history}\n\nRelevant context:\n{rag_ctx}"
        try:
            async for delta in self._stream_gemini(prompt):
                yield delta
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                raise LLMRateLimitedError() from e
            raise

    async def _stream_gemini(self, prompt: str) -> AsyncGenerator[str, None]:
        response = await self._gemini.generate_content_async(prompt, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def manual_ask(self, text: str, mode: str, context: dict, rag_chunks: list[str] | None = None) -> str:
        if rag_chunks is None:
            rag_chunks = []
        rag_ctx = "\n".join(rag_chunks)
        system = self._build_system_prompt(context)
        if mode == "hints":
            prompt = f"Provide hints and approach (no full solution) for: {text}\n\nContext: {rag_ctx}"
        else:
            prompt = f"Write a complete, clean solution for: {text}\n\nContext: {rag_ctx}"
        return await self._ask_claude(system=system, user=prompt)

    async def _ask_claude(self, system: str, user: str) -> str:
        # Check if web search is needed
        search_results = []
        if any(kw in user.lower() for kw in ["latest", "current", "docs", "documentation", "api"]):
            search_results = await self._search.search(user[:200])
        if search_results:
            user += f"\n\nWeb search results:\n" + "\n".join(search_results)
        msg = await self._claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text
