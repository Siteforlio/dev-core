import hashlib
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pg.session import InterviewSession, Round, RoundMoment
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.persona_engine import PersonaEngine
from app.services.context_assembler import ContextAssembler
from app.core.exceptions import SessionNotFoundError
from app.schemas.session import EvaluationResult, CheatSignal, SkillsTaskSchema

_log = logging.getLogger(__name__)


def _validate_evaluation(raw: dict) -> dict:
    """Validate and coerce a raw evaluation dict into the known schema."""
    try:
        return EvaluationResult.model_validate(raw).model_dump()
    except Exception as exc:
        _log.warning("[engine] evaluation validation failed: %s — storing as-is", exc)
        return raw


def _validate_task_brief(raw: dict) -> dict:
    """Validate a task_brief dict against SkillsTaskSchema."""
    try:
        return SkillsTaskSchema.model_validate(raw).model_dump()
    except Exception as exc:
        _log.warning("[engine] task_brief validation failed: %s — storing as-is", exc)
        return raw


def _validate_cheat_signal(raw: dict) -> dict | None:
    """Validate one cheat signal entry; returns None if invalid."""
    try:
        return CheatSignal.model_validate(raw).model_dump(exclude_none=True)
    except Exception as exc:
        _log.warning("[engine] cheat_signal validation failed: %s — skipping entry", exc)
        return None

PASS_THRESHOLD = 5.0   # score >= this → passed
FAIL_THRESHOLD = 3.0   # score <= this on last question → immediate fail

ROUND_TIME_BUDGETS = {
    "behavioral": 1800,
    "hr_interview": 1800,
    "hr": 1800,
    "hiring_manager": 2400,
    "technical": 3600,       # deprecated alias — kept for backwards compat
    "skills_task": 5400,     # 90 min — hands-on task + follow-ups
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

        persona = await self._persona_engine.build(
            company=company, role=role, round_type=first_round_type
        )

        result = {
            "session_id": session.id,
            "round_id": round_.id,
            "company": company,
            "role": role,
            "career_track": career_track,
            "level": level,
            "current_round": first_round_type,
            "remaining_rounds": round_types[1:],
            "questions": [],
            "task": None,
            "persona": persona,
            "time_budget_seconds": budget,
        }

        if first_round_type in ("skills_task", "technical"):
            task = await self.orchestrator.generate_skills_task(
                company=company,
                role=role,
                career_track=career_track,
                level=level,
                jd_text=jd_text,
                graph_context=context["graph_context"],
                knowledge_context=context["knowledge_profile"],
            )
            # Persist task brief on the round so follow-up handler can access it
            round_.task_brief = _validate_task_brief(task)
            await self.db.commit()
            result["task"] = task
        else:
            questions = await self.orchestrator.generate_questions(
                company=company, role=role, round_type=first_round_type,
                graph_context=context["graph_context"],
                knowledge_context=context["knowledge_profile"],
            )
            result["questions"] = questions

        return result

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

        # Time budget enforcement
        time_elapsed = 0
        time_budget = round_.time_budget_seconds or DEFAULT_TIME_BUDGET
        if round_.started_at is not None:
            time_elapsed = (_utcnow() - round_.started_at).total_seconds()
        budget_expired = time_elapsed >= time_budget
        time_remaining_pct = max(0.0, 1.0 - (time_elapsed / time_budget))

        is_skills_task = round_.type in ("skills_task", "technical") and round_.task_brief is not None

        if is_skills_task:
            return await self._submit_skills_task_answer(
                session=session,
                round_=round_,
                question=question,
                answer=answer,
                emotion_state=emotion_state,
                time_taken_seconds=time_taken_seconds,
                rewrite_count=rewrite_count,
                is_followup=is_followup,
                time_elapsed=time_elapsed,
                time_budget=time_budget,
                budget_expired=budget_expired,
                time_remaining_pct=time_remaining_pct,
            )

        # ── Standard Q&A round ──────────────────────────────────────────────
        grade = await self.orchestrator.grade_answer(
            question=question,
            answer=answer,
            company=session.company,
            role=session.role,
            round_type=round_.type,
            time_taken_seconds=time_taken_seconds,
            rewrite_count=rewrite_count,
        )
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
        await self.db.flush()

        count_result = await self.db.execute(
            select(func.count()).select_from(RoundMoment).where(
                RoundMoment.round_id == round_id,
                RoundMoment.is_followup == False,  # noqa: E712
            )
        )
        prepared_count = count_result.scalar()
        is_last = budget_expired or prepared_count >= total_questions

        if grade["score"] <= FAIL_THRESHOLD:
            is_last = True

        round_complete = False
        round_passed = None
        evaluation = None

        if is_last:
            round_complete = True
            round_passed = grade["passed"]
            round_.grade = grade["score"]
            round_.passed = round_passed
            round_.completed_at = _utcnow()
            evaluation = await self._run_evaluation(session, round_, round_id, question, answer, grade, time_elapsed, time_budget)
            round_.evaluation = _validate_evaluation(evaluation)
        else:
            round_.grade = grade["score"]

        await self.db.commit()

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

    async def _submit_skills_task_answer(
        self,
        session: InterviewSession,
        round_: Round,
        question: str,
        answer: str,
        emotion_state: str | None,
        time_taken_seconds: int | None,
        rewrite_count: int,
        is_followup: bool,
        time_elapsed: float,
        time_budget: int,
        budget_expired: bool,
        time_remaining_pct: float,
    ) -> dict:
        """Handle Phase 1 (task submission) and Phase 2 (follow-up Q&A) for skills_task rounds."""
        task_brief = round_.task_brief

        # Count existing moments to detect phase
        count_result = await self.db.execute(
            select(func.count()).select_from(RoundMoment).where(RoundMoment.round_id == round_.id)
        )
        existing_moments = count_result.scalar()
        is_phase1 = existing_moments == 0 and not is_followup

        if is_phase1:
            # Phase 1: grade the hands-on submission
            grade = await self.orchestrator.grade_skills_task(
                task_brief=task_brief,
                submission=answer,
                career_track=session.career_track or "technology",
                role=session.role,
                level=session.level or "mid_level",
            )
            follow_up = grade.get("first_followup")
            # Suppress follow-up only if time almost gone
            if time_remaining_pct <= 0.10 or budget_expired:
                follow_up = None
        else:
            # Phase 2: dynamic follow-up grading via standard grade_answer
            grade = await self.orchestrator.grade_answer(
                question=question,
                answer=answer,
                company=session.company,
                role=session.role,
                round_type="skills_task",
                time_taken_seconds=time_taken_seconds,
                rewrite_count=rewrite_count,
            )
            grade["passed"] = grade["score"] >= PASS_THRESHOLD

            # Gather conversation so far for context
            moments_result = await self.db.execute(
                select(RoundMoment).where(RoundMoment.round_id == round_.id).order_by(RoundMoment.timestamp)
            )
            all_moments = moments_result.scalars().all()
            conversation = []
            for m in all_moments:
                conversation.append({"role": "interviewer", "content": m.question})
                conversation.append({"role": "candidate", "content": m.answer})
            conversation.append({"role": "interviewer", "content": question})
            conversation.append({"role": "candidate", "content": answer})

            # Decide next follow-up dynamically
            follow_up = await self.orchestrator.decide_followup(
                task_brief=task_brief,
                submission=all_moments[0].answer if all_moments else answer,
                conversation=conversation,
                time_remaining_pct=time_remaining_pct,
                career_track=session.career_track or "technology",
                evaluation_criteria=task_brief.get("evaluation_criteria", []),
            )

        moment = RoundMoment(
            id=str(uuid.uuid4()),
            round_id=round_.id,
            question=question,
            answer=answer,
            emotion_state=emotion_state,
            time_taken_seconds=time_taken_seconds,
            rewrite_count=rewrite_count,
            is_followup=is_followup,
        )
        self.db.add(moment)
        await self.db.flush()

        # Round ends when: budget expired, no more follow-ups, or low score after phase 2
        is_last = budget_expired or (not is_phase1 and follow_up is None)
        if not is_phase1 and grade["score"] <= FAIL_THRESHOLD:
            is_last = True

        round_complete = False
        round_passed = None
        evaluation = None

        if is_last:
            round_complete = True
            round_passed = grade.get("passed", grade["score"] >= PASS_THRESHOLD)
            round_.grade = grade["score"]
            round_.passed = round_passed
            round_.completed_at = _utcnow()
            evaluation = await self._run_evaluation(
                session, round_, round_.id, question, answer, grade, time_elapsed, time_budget
            )
            round_.evaluation = _validate_evaluation(evaluation)
        else:
            round_.grade = grade["score"]

        await self.db.commit()

        time_remaining = max(0, int(time_budget - time_elapsed))

        return {
            "score": grade["score"],
            "passed": grade.get("passed", grade["score"] >= PASS_THRESHOLD),
            "what_worked": grade.get("what_worked", ""),
            "what_was_missing": grade.get("what_was_missing", ""),
            "stronger_version": grade.get("stronger_version", ""),
            "follow_up": follow_up if not is_last else None,
            "confidence_signal": grade.get("confidence_signal", ""),
            "factual_errors": grade.get("factual_errors", []),
            "round_complete": round_complete,
            "round_passed": round_passed,
            "evaluation": evaluation,
            "time_remaining_seconds": time_remaining,
            "phase": "followup" if not is_phase1 else "task",
        }

    async def _run_evaluation(
        self,
        session: InterviewSession,
        round_: Round,
        round_id: str,
        question: str,
        answer: str,
        grade: dict,
        time_elapsed: float,
        time_budget: int,
    ) -> dict:
        try:
            all_moments_result = await self.db.execute(
                select(RoundMoment).where(RoundMoment.round_id == round_id)
            )
            all_moments = all_moments_result.scalars().all()
            moments_data = [
                {
                    "question": m.question,
                    "answer": m.answer,
                    "score": None,
                    "time_taken_seconds": m.time_taken_seconds,
                    "rewrite_count": m.rewrite_count,
                    "is_followup": m.is_followup,
                }
                for m in all_moments
            ]
            moments_data.append({
                "question": question,
                "answer": answer,
                "score": grade["score"],
                "time_taken_seconds": None,
                "rewrite_count": 0,
                "is_followup": False,
            })
            return await self.orchestrator.evaluate_candidate(
                company=session.company,
                role=session.role,
                round_type=round_.type,
                moments=moments_data,
                time_budget_seconds=time_budget,
                actual_duration_seconds=int(time_elapsed),
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("evaluate_candidate failed: %s", exc)
            return {
                "hire_recommendation": "borderline",
                "confidence_rating": "low",
                "overall_score": grade["score"],
                "summary": "Evaluation could not be completed.",
                "strengths": [],
                "concerns": [],
                "time_management": "adequate",
            }

    async def record_cheat_signal(
        self,
        round_id: str,
        signal_type: str,
        paste_chars: int | None = None,
        duration_seconds: float | None = None,
        chars_per_second: float | None = None,
    ) -> None:
        """Append a cheat signal to the round's cheating_signals JSONB array."""
        result_q = await self.db.execute(select(Round).where(Round.id == round_id))
        round_ = result_q.scalar_one_or_none()
        if not round_:
            return

        signals = list(round_.cheating_signals or [])
        signal = {
            "type": signal_type,
            "ts": _utcnow().isoformat(),
        }
        if paste_chars is not None:
            signal["paste_chars"] = paste_chars
        if duration_seconds is not None:
            signal["duration_seconds"] = duration_seconds
        if chars_per_second is not None:
            signal["chars_per_second"] = chars_per_second

        validated = _validate_cheat_signal(signal)
        if validated is not None:
            signals.append(validated)
        round_.cheating_signals = signals
        await self.db.commit()

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

        result: dict = {
            "round_id": round_.id,
            "current_round": next_round_type,
            "questions": [],
            "task": None,
            "persona": "",
            "time_budget_seconds": budget,
        }

        if next_round_type in ("skills_task", "technical"):
            task = await self.orchestrator.generate_skills_task(
                company=session.company,
                role=session.role,
                career_track=session.career_track or "technology",
                level=session.level or "mid_level",
            )
            round_.task_brief = _validate_task_brief(task)
            await self.db.commit()
            result["task"] = task
        else:
            graph_context = await self._persona_engine.get_graph_context(
                company=session.company, round_type=next_round_type
            )
            questions = await self.orchestrator.generate_questions(
                company=session.company,
                role=session.role,
                round_type=next_round_type,
                graph_context=graph_context,
            )
            result["questions"] = questions

        persona = await self._persona_engine.build(
            company=session.company,
            role=session.role,
            round_type=next_round_type,
        )
        result["persona"] = persona

        return result
