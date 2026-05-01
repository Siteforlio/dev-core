import logging
from typing import AsyncGenerator

from app.core.exceptions import LLMRateLimitedError
from app.schemas.cluely import TranscriptEntry
from app.services.cluely.search_service import SearchService
from app.services.cluely.vertex_client import vertex_generate, vertex_stream

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
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

    def _build_context_block(self, facts: str, summary: str, recent: list[TranscriptEntry], rag_chunks: list[str]) -> str:
        """Build the three-layer context block injected into every prompt."""
        parts = []
        if facts:
            parts.append(f"KEY FACTS FROM THIS INTERVIEW:\n{facts}")
        if summary:
            parts.append(f"INTERVIEW SUMMARY SO FAR:\n{summary}")
        if recent:
            history = "\n".join(f"{e.speaker}: {e.text}" for e in recent)
            parts.append(f"RECENT CONVERSATION:\n{history}")
        if rag_chunks:
            parts.append(f"RELEVANT RESUME/JD CONTEXT:\n{chr(10).join(rag_chunks)}")
        return "\n\n".join(parts)

    async def stream_suggestion(
        self,
        transcript: list[TranscriptEntry],
        context: dict,
        rag_chunks: list[str],
        summary: str = "",
        facts: str = "",
    ) -> AsyncGenerator[str, None]:
        ctx_block = self._build_context_block(facts, summary, transcript, rag_chunks)
        system = self._build_system_prompt(context)
        prompt = ctx_block
        try:
            async for delta in vertex_stream(prompt, system=system):
                yield delta
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                raise LLMRateLimitedError() from e
            raise

    async def stream_manual_ask(
        self,
        text: str,
        mode: str,
        context: dict,
        rag_chunks: list[str] | None = None,
        summary: str = "",
        facts: str = "",
    ) -> AsyncGenerator[str, None]:
        """Stream a manual ask response token-by-token."""
        if rag_chunks is None:
            rag_chunks = []
        ctx_block = self._build_context_block(facts, summary, [], rag_chunks)
        system = self._build_system_prompt(context)

        if mode == "ultra":
            result = await self._ask_claude(system=system, user=text, ctx_block=ctx_block)
            yield result
            return

        if mode == "hints":
            prompt = f"{ctx_block}\n\nProvide hints and approach only (no full solution) for: {text}"
        else:  # solve
            prompt = f"{ctx_block}\n\nWrite a complete, clean solution for: {text}"

        try:
            async for delta in vertex_stream(prompt, system=system):
                yield delta
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                raise LLMRateLimitedError() from e
            raise

    async def manual_ask(self, text: str, mode: str, context: dict, rag_chunks: list[str] | None = None) -> str:
        """Non-streaming manual ask — kept for code_runner integration."""
        if rag_chunks is None:
            rag_chunks = []
        ctx_block = self._build_context_block("", "", [], rag_chunks)
        system = self._build_system_prompt(context)

        if mode == "ultra":
            return await self._ask_claude(system=system, user=text, ctx_block=ctx_block)

        if mode == "hints":
            prompt = f"{ctx_block}\n\nProvide hints and approach only (no full solution) for: {text}"
        else:
            prompt = f"{ctx_block}\n\nWrite a complete, clean solution for: {text}"

        return await vertex_generate(prompt, system=system)

    async def _ask_claude(self, system: str, user: str, rag_ctx: str = "", ctx_block: str = "") -> str:
        import anthropic
        from app.core.config import settings
        if self._claude is None:
            self._claude = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        search_results = []
        if any(kw in user.lower() for kw in ["latest", "current", "docs", "documentation", "api"]):
            search_results = await self._search.search(user[:200])

        full_user = user
        if ctx_block:
            full_user += f"\n\n{ctx_block}"
        elif rag_ctx:
            full_user += f"\n\nRelevant context:\n{rag_ctx}"
        if search_results:
            full_user += "\n\nWeb search results:\n" + "\n".join(search_results)

        msg = await self._claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": full_user}],
        )
        return msg.content[0].text
