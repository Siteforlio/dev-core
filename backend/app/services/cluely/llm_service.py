import logging
from typing import AsyncGenerator
import google.generativeai as genai
from app.core.config import settings
from app.core.exceptions import LLMRateLimitedError
from app.schemas.cluely import TranscriptEntry
from app.services.cluely.search_service import SearchService

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self._gemini = genai.GenerativeModel("gemini-2.0-flash")
        self._search = SearchService()
        self._claude = None  # lazy — only created when ultra mode is used

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

        if mode == "ultra":
            # Ultra mode: Claude Sonnet with web search enrichment
            return await self._ask_claude(system=system, user=text, rag_ctx=rag_ctx)

        # Default (hints / solve): Gemini with RAG context
        if mode == "hints":
            prompt = f"{system}\n\nProvide hints and approach only (no full solution) for: {text}\n\nRelevant context:\n{rag_ctx}"
        else:
            prompt = f"{system}\n\nWrite a complete, clean solution for: {text}\n\nRelevant context:\n{rag_ctx}"
        response = await self._gemini.generate_content_async(prompt)
        return response.text

    async def _ask_claude(self, system: str, user: str, rag_ctx: str = "") -> str:
        import anthropic
        if self._claude is None:
            self._claude = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Enrich with web search when query looks like it needs current info
        search_results = []
        if any(kw in user.lower() for kw in ["latest", "current", "docs", "documentation", "api"]):
            search_results = await self._search.search(user[:200])

        full_user = user
        if rag_ctx:
            full_user += f"\n\nRelevant context:\n{rag_ctx}"
        if search_results:
            full_user += f"\n\nWeb search results:\n" + "\n".join(search_results)

        msg = await self._claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": full_user}],
        )
        return msg.content[0].text
