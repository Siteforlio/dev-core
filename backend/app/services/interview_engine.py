import hashlib
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pg.session import InterviewSession, Round, RoundMoment
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.persona_engine import PersonaEngine
from app.services.context_assembler import ContextAssembler
from app.core.exceptions import SessionNotFoundError

PASS_THRESHOLD = 5.0   # score >= this → passed (lowered from 6.0 — follow-ups compensate)
FAIL_THRESHOLD = 3.0   # score <= this on last question → immediate fail

ROUND_TIME_BUDGETS = {
    "behavioral": 1800,
    "hr_interview": 1800,
    "hr": 1800,
    "hiring_manager": 2400,
    "technical": 3600,
    "skills_domain": 3600,
    "panel_interview": 3600,
    "case_presentation": 3600,
    "final_executive": 2400,
    "offer_negotiation": 1800,
    "leetcode": 5400,
}
DEFAULT_TIME_BUDGET = 1800


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
        career_track: str = "technology",
        level: str = "mid_level",
        interview_stage: str = "hr_interview",
        jd_text: str | None = None,
        manager_name: str | None = None,
    ) -> dict:
        session = InterviewSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            company=company,
            role=role,
            career_track=career_track,
            level=level,
            interview_stage=interview_stage,
            jd_hash=hashlib.sha256(jd_text.encode()).hexdigest() if jd_text else None,
        )
        self.db.add(session)

        first_round_type = round_types[0]
        budget = ROUND_TIME_BUDGETS.get(first_round_type, DEFAULT_TIME_BUDGET)
        round_ = Round(id=str(uuid.uuid4()), session_id=session.id, type=first_round_type, time_budget_seconds=budget)
        self.db.add(round_)
        await self.db.commit()

        assembler = ContextAssembler(db=self.db)
        context = await assembler.assemble(
            user_id=user_id, company=company, role=role,
            career_track=career_track, level=level,
            interview_stage=interview_stage, jd_text=jd_text,
            manager_name=manager_name,
        )

        questions = await self.orchestrator.generate_questions(
            company=company, role=role, round_type=first_round_type,
            graph_context=context["graph_context"],
            knowledge_context=context["knowledge_profile"],
        )
        persona = await self._persona_engine.build(
            company=company, role=role, round_type=first_round_type
        )

        return {
            "session_id": session.id,
            "round_id": round_.id,
            "company": company,
            "role": role,
            "career_track": career_track,
            "level": level,
            "current_round": first_round_type,
            "remaining_rounds": round_types[1:],
            "questions": questions,
            "persona": persona,
            "time_budget_seconds": budget,
        }

    async def submit_answer(
        self,
        session_id: str,
        round_id: str,
        question: str,
        answer: str,
        total_questions: int = 5,
        emotion_state: str | None = None,
        time_taken_seconds: int | None = None,
        rewrite_count: int = 0,
        is_followup: bool = False,
    ) -> dict:
        result_q = await self.db.execute(select(Round).where(Round.id == round_id))
        round_ = result_q.scalar_one_or_none()
        if not round_:
            raise SessionNotFoundError()

        result_s = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = result_s.scalar_one_or_none()

        # Time budget enforcement — use naive datetime helper to match stored naive datetimes
        time_elapsed = 0
        time_budget = round_.time_budget_seconds or DEFAULT_TIME_BUDGET
        if round_.started_at is not None:
            time_elapsed = (_utcnow() - round_.started_at).total_seconds()
        budget_expired = time_elapsed >= time_budget

        grade = await self.orchestrator.grade_answer(
            question=question,
            answer=answer,
            company=session.company,
            role=session.role,
            round_type=round_.type,
            time_taken_seconds=time_taken_seconds,
            rewrite_count=rewrite_count,
        )
        # Engine derives passed — do not trust LLM for this
        grade["passed"] = grade["score"] >= PASS_THRESHOLD

        moment = RoundMoment(
            id=str(uuid.uuid4()),
            round_id=round_id,
            question=question,
            answer=answer,
            emotion_state=emotion_state,
            time_taken_seconds=time_taken_seconds,
            rewrite_count=rewrite_count,
            is_followup=is_followup,
        )
        self.db.add(moment)

        # Count only non-followup answers toward prepared question total
        count_result = await self.db.execute(
            select(func.count()).select_from(RoundMoment).where(
                RoundMoment.round_id == round_id,
                RoundMoment.is_followup == False,  # noqa: E712
            )
        )
        prepared_count = count_result.scalar()
        is_last = budget_expired or prepared_count >= total_questions

        # Immediate fail on very low score
        if grade["score"] <= FAIL_THRESHOLD:
            is_last = True

        round_complete = False
        round_passed = None
        evaluation = None

        if is_last:
            round_complete = True
            round_passed = grade["passed"] and grade["score"] > FAIL_THRESHOLD
            round_.grade = grade["score"]
            round_.passed = round_passed
            round_.completed_at = _utcnow()

            # Holistic evaluation
            try:
                all_moments_result = await self.db.execute(
                    select(RoundMoment).where(RoundMoment.round_id == round_id)
                )
                all_moments = all_moments_result.scalars().all()
                moments_data = [
                    {
                        "question": m.question,
                        "answer": m.answer,
                        "score": None,  # individual scores not stored on moment
                        "time_taken_seconds": m.time_taken_seconds,
                        "rewrite_count": m.rewrite_count,
                        "is_followup": m.is_followup,
                    }
                    for m in all_moments
                ]
                # Current moment not yet committed — append explicitly with its grade
                moments_data.append({
                    "question": question,
                    "answer": answer,
                    "score": grade["score"],
                    "time_taken_seconds": time_taken_seconds,
                    "rewrite_count": rewrite_count,
                    "is_followup": is_followup,
                })

                actual_duration = int(time_elapsed)
                evaluation = await self.orchestrator.evaluate_candidate(
                    company=session.company,
                    role=session.role,
                    round_type=round_.type,
                    moments=moments_data,
                    time_budget_seconds=time_budget,
                    actual_duration_seconds=actual_duration,
                )
                round_.evaluation = evaluation
            except Exception:
                evaluation = {
                    "hire_recommendation": "borderline",
                    "confidence_rating": "low",
                    "overall_score": grade["score"],
                    "summary": "Evaluation could not be completed.",
                    "strengths": [],
                    "concerns": [],
                    "time_management": "adequate",
                }
                round_.evaluation = evaluation
        else:
            round_.grade = grade["score"]

        await self.db.commit()

        # Suppress follow-up if > 80% of time budget used
        follow_up = grade.get("follow_up")
        if time_elapsed >= 0.8 * time_budget:
            follow_up = None

        time_remaining = max(0, int(time_budget - time_elapsed))

        return {
            "score": grade["score"],
            "passed": grade["passed"],
            "what_worked": grade.get("what_worked", ""),
            "what_was_missing": grade.get("what_was_missing", ""),
            "stronger_version": grade.get("stronger_version", ""),
            "follow_up": follow_up,
            "confidence_signal": grade.get("confidence_signal", ""),
            "factual_errors": grade.get("factual_errors", []),
            "round_complete": round_complete,
            "round_passed": round_passed,
            "evaluation": evaluation,
            "time_remaining_seconds": time_remaining,
        }

    async def advance_to_next_round(self, session_id: str, next_round_type: str) -> dict:
        result_s = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session = result_s.scalar_one_or_none()
        if not session:
            raise SessionNotFoundError()

        budget = ROUND_TIME_BUDGETS.get(next_round_type, DEFAULT_TIME_BUDGET)
        round_ = Round(id=str(uuid.uuid4()), session_id=session_id, type=next_round_type, time_budget_seconds=budget)
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
            "time_budget_seconds": budget,
        }
