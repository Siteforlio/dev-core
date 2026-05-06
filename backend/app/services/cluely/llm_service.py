import logging
from typing import AsyncGenerator

from app.core.exceptions import LLMRateLimitedError
from app.schemas.cluely import TranscriptEntry
from app.services.cluely.deepseek_client import deepseek_stream, deepseek_generate
from app.services.cluely.search_service import SearchService

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self._search = SearchService()
        self._claude = None  # lazy — only for ultra mode

    def _build_system_prompt(self, context: dict) -> str:
        """
        First-person candidate voice. The AI speaks AS the user, not at them.
        Resume and JD are injected so every response is grounded in the user's
        actual background.
        """
        job_title   = context.get("job_title", "this role")
        company     = context.get("company", "this company")
        resume_text = context.get("resume_text", "")[:600]
        jd_text     = context.get("jd_text", "")[:400]

        return (
            f"You are speaking AS the candidate in a live job interview for {job_title} at {company}. "
            "Answer every question in the first person, naturally and confidently, as if you are the candidate speaking aloud. "
            "Draw directly from the resume and job description provided — use specific experiences, projects, and skills. "
            "Sound human: conversational, not textbook. No bullet points, no preamble, no meta-commentary. "
            "One flowing answer, 2-4 sentences unless the question demands more. "
            f"Resume: {resume_text}. "
            f"Job description: {jd_text}."
        )

    def _build_context_block(
        self,
        facts: str,
        summary: str,
        recent: list[TranscriptEntry],
        rag_chunks: list[str],
    ) -> str:
        """
        Three-layer context model — kept exactly as designed.
        Covers 2+ hour interviews within ~900 tokens:
          [key facts]        ~75 tokens  (always current)
          [rolling summary]  ~300 tokens (2-min lag, 400-word budget)
          [last 15 verbatim] ~400 tokens (real-time)
          [rag chunks]       ~125 tokens (relevant resume/JD excerpts)
        """
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
        inferred_outcome: str = "",
    ) -> AsyncGenerator[str, None]:
        ctx_block = self._build_context_block(facts, summary, transcript, rag_chunks)
        system = self._build_system_prompt(context)

        # Anchor the response toward the inferred outcome when available
        outcome_line = (
            f"\nIMPORTANT: Your answer must land on this point: {inferred_outcome}\n"
            if inferred_outcome else ""
        )
        prompt = f"{outcome_line}{ctx_block}"

        try:
            async for delta in deepseek_stream(prompt, system=system, temperature=0.7, max_tokens=200):
                yield delta
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                raise LLMRateLimitedError() from e
            raise

    async def _detect_intent(self, text: str, has_transcript: bool) -> str:
        """
        Quickly classify user input as 'contextual' (about the ongoing interview
        conversation) or 'standalone' (a fresh question needing a direct answer).
        Returns 'contextual' or 'standalone'.
        """
        if not has_transcript:
            return "standalone"

        classification_prompt = (
            "Classify this user message as CONTEXTUAL or STANDALONE.\n"
            "CONTEXTUAL = the user is commenting on, clarifying, or asking about the ongoing interview conversation.\n"
            "STANDALONE = the user is asking a fresh, self-contained question unrelated to the conversation flow.\n"
            f"Message: \"{text}\"\n"
            "Reply with exactly one word: CONTEXTUAL or STANDALONE."
        )
        try:
            result = await deepseek_generate(
                classification_prompt,
                system="You are a message intent classifier. Reply with exactly one word.",
                temperature=0.0,
                max_tokens=5,
            )
            return "contextual" if "CONTEXTUAL" in result.upper() else "standalone"
        except Exception:
            return "contextual"  # safe default

    async def stream_manual_ask(
        self,
        text: str,
        mode: str,
        context: dict,
        rag_chunks: list[str] | None = None,
        summary: str = "",
        facts: str = "",
        recent: list[TranscriptEntry] | None = None,
    ) -> AsyncGenerator[str, None]:
        if rag_chunks is None:
            rag_chunks = []
        if recent is None:
            recent = []

        intent = await self._detect_intent(text, has_transcript=bool(recent or summary))
        ctx_block = self._build_context_block(facts, summary, recent, rag_chunks)
        system = self._build_system_prompt(context)

        if mode == "ultra":
            result = await self._ask_claude(system=system, user=text, ctx_block=ctx_block)
            yield result
            return

        if mode == "solve":
            prompt = f"{ctx_block}\n\nThe candidate (you) types: \"{text}\"\nWrite a complete, clean solution in their voice."
        elif intent == "contextual":
            # User is engaging with the interview flow — respond as the candidate continuing the conversation
            prompt = (
                f"{ctx_block}\n\n"
                f"The candidate adds: \"{text}\"\n"
                "Continue speaking as the candidate, building naturally on the conversation above. "
                "Stay in first person, conversational, 1-3 sentences."
            )
        else:
            # Standalone question — answer it directly as the candidate
            prompt = (
                f"{ctx_block}\n\n"
                f"The candidate wants to answer this specific question: \"{text}\"\n"
                "Respond directly and specifically to this question in first person, as the candidate speaking aloud. "
                "Do not reference the conversation above unless directly relevant. 2-4 sentences."
            )

        logger.info("[llm] manual_ask intent=%s mode=%s text=%r", intent, mode, text[:60])

        try:
            async for delta in deepseek_stream(prompt, system=system, temperature=0.7, max_tokens=300):
                yield delta
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                raise LLMRateLimitedError() from e
            raise

    async def manual_ask(
        self,
        text: str,
        mode: str,
        context: dict,
        rag_chunks: list[str] | None = None,
    ) -> str:
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

        return await deepseek_generate(prompt, system=system, temperature=0.5, max_tokens=800)

    async def stream_outcome_answer(
        self,
        outcome: str,
        context: dict,
        rag_chunks: list[str],
        summary: str = "",
        facts: str = "",
        recent: list[TranscriptEntry] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Outcome pill tap — generate a full first-person answer targeting the
        inferred outcome. Used when the user explicitly requests the full answer.
        """
        ctx_block = self._build_context_block(facts, summary, recent or [], rag_chunks)
        system = self._build_system_prompt(context)
        prompt = (
            f"The interviewer expects you to: {outcome}\n\n"
            f"{ctx_block}\n\n"
            "Speak your complete answer now, in first person, naturally."
        )
        try:
            async for delta in deepseek_stream(prompt, system=system, temperature=0.7, max_tokens=300):
                yield delta
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                raise LLMRateLimitedError() from e
            raise

    async def _ask_claude(self, system: str, user: str, ctx_block: str = "") -> str:
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
        if search_results:
            full_user += "\n\nWeb search results:\n" + "\n".join(search_results)

        msg = await self._claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": full_user}],
        )
        return msg.content[0].text
