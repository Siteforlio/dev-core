import json
from collections import Counter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic
from app.core.config import settings
from app.models.pg.session import InterviewSession, Round, RoundMoment
from app.core.exceptions import SessionNotFoundError
from app.services.community_pipeline import CommunityPipeline


class DebriefService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_claude(self, prompt: str) -> dict:
        msg = await self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            return json.loads(m.group()) if m else {
                "overall_score": 5.0, "strengths": [], "improvements": [], "recommendation": raw[:200]
            }

    async def _get_moments(self, round_id: str) -> list:
        result = await self.db.execute(
            select(RoundMoment).where(RoundMoment.round_id == round_id)
        )
        return result.scalars().all()

    async def generate(self, session_id: str) -> dict:
        sess_result = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = sess_result.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError()

        rounds_result = await self.db.execute(
            select(Round).where(Round.session_id == session_id)
        )
        rounds = rounds_result.scalars().all()

        all_moments = []
        for r in rounds:
            moments = await self._get_moments(r.id)
            all_moments.extend(moments)

        # Emotion summary
        emotions = [m.emotion_state for m in all_moments if m.emotion_state]
        emotion_summary = dict(Counter(emotions)) if emotions else {}

        # Build transcript for Claude
        transcript_lines = []
        for r in rounds:
            moments = [m for m in all_moments if m.round_id == r.id]
            for m in moments:
                transcript_lines.append(f"[{r.type}] Q: {m.question}\nA: {m.answer}")

        transcript = "\n\n".join(transcript_lines) or "No answers recorded."
        avg_score = sum(r.grade for r in rounds if r.grade) / max(len(rounds), 1)

        prompt = (
            f"You are reviewing an interview for {session.company}, role: {session.role}.\n\n"
            f"Transcript:\n{transcript}\n\n"
            f"Average score: {avg_score:.1f}/10\n\n"
            "Return a JSON debrief:\n"
            '{"overall_score": 7.5, "strengths": ["..."], "improvements": ["..."], "recommendation": "..."}'
        )
        analysis = await self._call_claude(prompt)

        # Stage anonymized data for community pipeline (fire-and-forget)
        try:
            pipeline = CommunityPipeline(db=self.db)
            rounds_for_pipeline = []
            for r in rounds:
                moments_for_round = [m for m in all_moments if m.round_id == r.id]
                rounds_for_pipeline.append({
                    "type": r.type,
                    "grade": r.grade,
                    "passed": r.passed,
                    "moments": [
                        {"question": m.question, "answer": m.answer, "emotion": m.emotion_state}
                        for m in moments_for_round
                    ],
                })
            await pipeline.stage(
                session_id=session_id,
                user_id=session.user_id,
                company=session.company,
                role=session.role,
                rounds=rounds_for_pipeline,
            )
        except Exception:
            pass  # community staging is best-effort; never break the debrief

        return {
            "session_id": session_id,
            "company": session.company,
            "role": session.role,
            "overall_score": analysis.get("overall_score", avg_score),
            "strengths": analysis.get("strengths", []),
            "improvements": analysis.get("improvements", []),
            "recommendation": analysis.get("recommendation", ""),
            "emotion_summary": emotion_summary,
            "rounds": [
                {
                    "type": r.type,
                    "grade": r.grade,
                    "passed": r.passed,
                }
                for r in rounds
            ],
        }
