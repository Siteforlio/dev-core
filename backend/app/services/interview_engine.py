import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.session import InterviewSession, Round, RoundMoment
from app.services.llm_orchestrator import LLMOrchestrator
from app.core.exceptions import SessionNotFoundError


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class InterviewEngine:
    def __init__(self, db: AsyncSession, orchestrator: LLMOrchestrator):
        self.db = db
        self.orchestrator = orchestrator

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
        round_ = Round(
            id=str(uuid.uuid4()),
            session_id=session.id,
            type=first_round_type,
        )
        self.db.add(round_)
        await self.db.commit()

        questions = await self.orchestrator.generate_questions(
            company=company,
            role=role,
            round_type=first_round_type,
            graph_context=None,
        )
        persona = await self.orchestrator.build_persona(
            company=company,
            role=role,
            manager_context=None,
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
        )
        self.db.add(moment)

        round_.grade = grade["score"]
        round_.passed = grade["passed"]
        round_.completed_at = _utcnow()
        await self.db.commit()

        return {
            "score": grade["score"],
            "passed": grade["passed"],
            "feedback": grade["feedback"],
        }
