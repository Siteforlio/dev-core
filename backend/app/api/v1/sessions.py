from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.session import CreateSessionRequest, AnswerRequest, AdvanceRoundRequest, BehavioralSignalRequest, CheatSignalRequest, CoachRequest
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.interview_engine import InterviewEngine
from app.services.debrief_service import DebriefService
from app.models.pg.session import InterviewSession, Round

router = APIRouter(prefix="/interview-sessions", tags=["sessions"])
bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.post("")
async def create_session(
    body: CreateSessionRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = LLMOrchestrator()
    engine = InterviewEngine(db=db, orchestrator=orchestrator)
    session = await engine.create_session(
        user_id=user_id,
        company=body.company,
        role=body.role,
        round_types=body.round_types,
        career_track=body.career_track,
        level=body.level,
        interview_stage=body.interview_stage,
        jd_text=body.jd_text,
        manager_name=body.manager_name,
    )
    return {"data": session, "error": None}


@router.post("/{session_id}/answer")
async def submit_answer(
    session_id: str,
    body: AnswerRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = LLMOrchestrator()
    engine = InterviewEngine(db=db, orchestrator=orchestrator)
    result = await engine.submit_answer(
        session_id=session_id,
        round_id=body.round_id,
        question=body.question,
        answer=body.answer,
        total_questions=body.total_questions,
        emotion_state=body.emotion_state,
        time_taken_seconds=body.time_taken_seconds,
        rewrite_count=body.rewrite_count,
        is_followup=body.is_followup,
    )
    return {"data": result, "error": None}


@router.post("/{session_id}/advance")
async def advance_round(
    session_id: str,
    body: AdvanceRoundRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = LLMOrchestrator()
    engine = InterviewEngine(db=db, orchestrator=orchestrator)
    result = await engine.advance_to_next_round(
        session_id=session_id,
        next_round_type=body.next_round_type,
    )
    return {"data": result, "error": None}


@router.post("/{session_id}/behavioral-signal")
async def behavioral_signal(
    session_id: str,
    body: BehavioralSignalRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"data": {"reaction": ""}, "error": None}
    orchestrator = LLMOrchestrator()
    reaction = await orchestrator.react_to_rewrite(
        company=session.company,
        role=session.role,
        rewrite_count=body.rewrite_count,
    )
    return {"data": {"reaction": reaction}, "error": None}


@router.post("/{session_id}/cheat-signal")
async def record_cheat_signal(
    session_id: str,
    body: CheatSignalRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify round belongs to this session/user
    result = await db.execute(
        select(Round).join(
            InterviewSession, Round.session_id == InterviewSession.id
        ).where(
            Round.id == body.round_id,
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        return {"data": None, "error": "round not found"}

    orchestrator = LLMOrchestrator()
    engine = InterviewEngine(db=db, orchestrator=orchestrator)
    await engine.record_cheat_signal(
        round_id=body.round_id,
        signal_type=body.signal_type,
        paste_chars=body.paste_chars,
        duration_seconds=body.duration_seconds,
        chars_per_second=body.chars_per_second,
    )
    return {"data": {"recorded": True}, "error": None}


@router.post("/{session_id}/coach")
async def coach(
    session_id: str,
    body: CoachRequest,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream coaching tokens as SSE.

    Route handler is thin (§4.2) — delegates entirely to LLMOrchestrator.
    The frontend appends the user's message to conversation_history before
    calling this, so the handler only needs to add it once more when
    conversation_history is non-empty.
    """
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return {"data": None, "error": {"code": "SESSION_NOT_FOUND", "message": "Session not found"}}

    # Build conversation history including the new user message (if any)
    history = [{"role": m.role, "content": m.content} for m in body.conversation_history]
    if body.message:
        history.append({"role": "user", "content": body.message})

    orchestrator = LLMOrchestrator()

    async def _sse_stream():
        try:
            async for token in orchestrator.coach_candidate(
                question=body.question,
                company=session.company,
                role=session.role,
                round_type=body.round_type,
                career_track=body.career_track,
                level=body.level,
                conversation_history=history,
            ):
                # SSE format: each token as a data event
                yield f"data: {token}\n\n"
        except Exception:
            pass
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{session_id}/debrief")
async def get_debrief(
    session_id: str,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = DebriefService(db=db)
    result = await service.generate(session_id=session_id)
    return {"data": result, "error": None}


@router.get("/{session_id}/report")
async def get_report(
    session_id: str,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    service = DebriefService(db=db)
    pdf_bytes = await service.generate_pdf(session_id=session_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{session_id}.pdf"'},
    )
