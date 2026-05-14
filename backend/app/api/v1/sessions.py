from fastapi import APIRouter, Depends
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.session import CreateSessionRequest, AnswerRequest, AdvanceRoundRequest
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.interview_engine import InterviewEngine
from app.services.debrief_service import DebriefService

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
