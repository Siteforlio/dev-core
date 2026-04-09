from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.session import CreateSessionRequest, AnswerRequest
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.interview_engine import InterviewEngine

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
    )
    return {"data": result, "error": None}
