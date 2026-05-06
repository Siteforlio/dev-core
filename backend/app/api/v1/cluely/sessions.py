from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.security import decode_token

router = APIRouter(prefix="/cluely", tags=["cluely"])

bearer = HTTPBearer()


def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    rows = (await db.execute(text("""
        SELECT s.id, s.title, s.company, s.role,
               s.started_at, s.ended_at, s.duration_seconds,
               COUNT(DISTINCT t.id) AS transcript_lines
        FROM cluely_sessions s
        LEFT JOIN cluely_transcript_lines t ON t.session_id = s.id
        WHERE s.user_id = :uid
        GROUP BY s.id
        ORDER BY s.started_at DESC
        LIMIT :limit
    """), {"uid": user_id, "limit": limit})).fetchall()

    return {
        "sessions": [
            {
                "id":               r.id,
                "title":            r.title or "Untitled Session",
                "company":          r.company or "",
                "role":             r.role or "",
                "started_at":       r.started_at.isoformat() if r.started_at else None,
                "ended_at":         r.ended_at.isoformat() if r.ended_at else None,
                "duration_seconds": r.duration_seconds,
                "transcript_lines": r.transcript_lines,
            }
            for r in rows
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    # Verify ownership
    session = (await db.execute(text("""
        SELECT id, title, company, role FROM cluely_sessions
        WHERE id = :sid AND user_id = :uid
    """), {"sid": session_id, "uid": user_id})).fetchone()

    if not session:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")

    transcript = (await db.execute(text("""
        SELECT speaker, text, seq FROM cluely_transcript_lines
        WHERE session_id = :sid ORDER BY seq ASC
    """), {"sid": session_id})).fetchall()

    interactions = (await db.execute(text("""
        SELECT trigger_type, question_text, ai_response, occurred_at
        FROM cluely_interactions
        WHERE session_id = :sid ORDER BY occurred_at ASC
    """), {"sid": session_id})).fetchall()

    return {
        "id":       session.id,
        "title":    session.title or "Untitled Session",
        "company":  session.company or "",
        "role":     session.role or "",
        "transcript": [
            {"speaker": t.speaker, "text": t.text, "seq": t.seq}
            for t in transcript
        ],
        "interactions": [
            {"question": i.question_text, "answer": i.ai_response, "trigger": i.trigger_type}
            for i in interactions
        ],
    }
