import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pg.session import InterviewSession, Round, RoundMoment
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.persona_engine import PersonaEngine
from app.core.exceptions import SessionNotFoundError

PASS_THRESHOLD = 6.0   # score >= this → passed
FAIL_THRESHOLD = 3.0   # score <= this on last question → immediate fail


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InterviewEngine:
    def __init__(self, db: AsyncSession, orchestrator: LLMOrchestrator):
        self.db = db
        self.orchestrator = orchestrator
        self._persona_engine = PersonaEngine()

    async def create_session(
        self,
        user_id: str,
        company: str,
        role: str,
        round_types: list[str],
    ) -> dict:
        session = InterviewSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            company=company,
            role=role,
        )
        self.db.add(session)

        first_round_type = round_types[0]
        round_ = Round(id=str(uuid.uuid4()), session_id=session.id, type=first_round_type)
        self.db.add(round_)
        await self.db.commit()

        graph_context = await self._persona_engine.get_graph_context(
            company=company, round_type=first_round_type
        )
        questions = await self.orchestrator.generate_questions(
            company=company, role=role, round_type=first_round_type, graph_context=graph_context
        )
        persona = await self._persona_engine.build(
            company=company, role=role, round_type=first_round_type
        )

        return {
            "session_id": session.id,
            "round_id": round_.id,
            "company": company,
            "role": role,
            "current_round": first_round_type,
            "remaining_rounds": round_types[1:],
            "questions": questions,
            "persona": persona,
        }

    async def submit_answer(
        self,
        session_id: str,
        round_id: str,
        question: str,
        answer: str,
        total_questions: int = 5,
        emotion_state: str | None = None,
    ) -> dict:
        result_q = await self.db.execute(select(Round).where(Round.id == round_id))
        round_ = result_q.scalar_one_or_none()
        if not round_:
            raise SessionNotFoundError()

        result_s = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = result_s.scalar_one_or_none()

        grade = await self.orchestrator.grade_answer(
            question=question,
            answer=answer,
            company=session.company,
            role=session.role,
            round_type=round_.type,
        )

        moment = RoundMoment(
            id=str(uuid.uuid4()),
            round_id=round_id,
            question=question,
            answer=answer,
            emotion_state=emotion_state,
        )
        self.db.add(moment)

        # Count answers already stored for this round
        count_result = await self.db.execute(
            select(func.count()).select_from(RoundMoment).where(RoundMoment.round_id == round_id)
        )
        answers_count = count_result.scalar()  # includes the one we just added (after flush)
        is_last = answers_count >= total_questions

        round_complete = False
        round_passed = None

        if is_last or grade["score"] <= FAIL_THRESHOLD:
            round_complete = True
            round_passed = grade["passed"] and grade["score"] > FAIL_THRESHOLD
            round_.grade = grade["score"]
            round_.passed = round_passed
            round_.completed_at = _utcnow()
        else:
            round_.grade = grade["score"]

        await self.db.commit()

        return {
            "score": grade["score"],
            "passed": grade["passed"],
            "what_worked": grade.get("what_worked", ""),
            "what_was_missing": grade.get("what_was_missing", ""),
            "stronger_version": grade.get("stronger_version", ""),
            "round_complete": round_complete,
            "round_passed": round_passed,
        }

    async def advance_to_next_round(self, session_id: str, next_round_type: str) -> dict:
        result_s = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = result_s.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError()

        round_ = Round(id=str(uuid.uuid4()), session_id=session_id, type=next_round_type)
        self.db.add(round_)
        await self.db.commit()

        graph_context = await self._persona_engine.get_graph_context(
            company=session.company, round_type=next_round_type
        )
        questions = await self.orchestrator.generate_questions(
            company=session.company,
            role=session.role,
            round_type=next_round_type,
            graph_context=graph_context,
        )
        persona = await self._persona_engine.build(
            company=session.company,
            role=session.role,
            round_type=next_round_type,
        )

        return {
            "round_id": round_.id,
            "current_round": next_round_type,
            "questions": questions,
            "persona": persona,
        }
