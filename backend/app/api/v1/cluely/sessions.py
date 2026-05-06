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
