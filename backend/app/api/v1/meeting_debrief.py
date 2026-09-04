# backend/app/api/v1/meeting_debrief.py
"""
Meeting debrief routes — one debrief record per calendar event.
All business logic lives in MeetingDebriefService.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_api_key
from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.meeting_debrief import (
    MeetingDebriefCreateRequest,
    MeetingDebriefPatchRequest,
    MeetingDebriefResponse,
)
from app.services.meeting_debrief_service import MeetingDebriefService
from app.models.pg.meeting_debrief import MeetingDebrief

router = APIRouter(prefix="/meeting-debriefs", tags=["meeting-debriefs"])
bearer = HTTPBearer()


def get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


def _row_to_schema(row: MeetingDebrief) -> MeetingDebriefResponse:
    return MeetingDebriefResponse(
        id=row.id,
        calendar_event_uid=row.calendar_event_uid,
        cluely_session_id=row.cluely_session_id,
        date=str(row.date) if row.date else None,
        title=row.title,
        location=row.location,
        start_time=row.start_time,
        duration_minutes=int(row.duration_minutes) if row.duration_minutes else None,
        notes=row.notes,
        actions=row.actions or [],
        decisions=row.decisions or [],
        attendees=row.attendees or [],
        ai_summary=row.ai_summary,
        ai_summary_status=row.ai_summary_status,
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _to_response(row: MeetingDebrief) -> dict:
    return {"data": _row_to_schema(row).model_dump(), "error": None}


@router.get("", response_model=dict)
async def list_by_date(
    date: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """List all meeting debriefs for the given date (YYYY-MM-DD)."""
    svc = MeetingDebriefService(db)
    rows = await svc.list_by_date(user_id, date)
    return {"data": [_row_to_schema(r).model_dump() for r in rows], "error": None}


@router.post("", response_model=dict)
async def get_or_create(
    body: MeetingDebriefCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Get or create a debrief for a calendar event."""
    svc = MeetingDebriefService(db)
    row = await svc.get_or_create(
        user_id=user_id,
        calendar_event_uid=body.calendar_event_uid,
        date_str=body.date,
        title=body.title,
        location=body.location,
        start_time=body.start_time,
        duration_minutes=body.duration_minutes,
        attendees=[a.model_dump() for a in body.attendees],
    )
    return _to_response(row)


@router.patch("/{debrief_id}", response_model=dict)
async def patch_debrief(
    debrief_id: str,
    body: MeetingDebriefPatchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Partial update — notes, actions, decisions, attendees, or title."""
    svc = MeetingDebriefService(db)
    row = await svc.patch(
        debrief_id=debrief_id,
        user_id=user_id,
        notes=body.notes,
        actions=body.actions,
        decisions=body.decisions,
        attendees=body.attendees,
        title=body.title,
        cluely_session_id=body.cluely_session_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Debrief not found")
    return _to_response(row)


@router.get("/recent", response_model=dict)
async def list_recent(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Return the most recent debriefs across all dates (for meeting picker)."""
    svc = MeetingDebriefService(db)
    rows = await svc.list_recent(user_id, limit)
    return {"data": [_row_to_schema(r).model_dump() for r in rows], "error": None}


@router.get("/{debrief_id}", response_model=dict)
async def get_debrief(
    debrief_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    svc = MeetingDebriefService(db)
    row = await svc.get_by_id(debrief_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Debrief not found")
    return _to_response(row)


@router.post("/{debrief_id}/compose-email", response_model=dict)
async def compose_email(
    debrief_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Use DeepSeek to compose a contextual follow-up email for this meeting."""
    api_key = await get_api_key(user_id, "deepseek_api_key", db)
    svc = MeetingDebriefService(db, api_key=api_key)
    result = await svc.compose_followup_email(debrief_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Debrief not found")
    return {"data": result, "error": None}


@router.post("/{debrief_id}/summarize", response_model=dict)
async def summarize(
    debrief_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_user_id),
):
    """Trigger Claude AI summary generation. Returns immediately with status=pending."""
    api_key = await get_api_key(user_id, "deepseek_api_key", db)
    svc = MeetingDebriefService(db, api_key=api_key)
    row = await svc.generate_ai_summary(debrief_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Debrief not found")
    return _to_response(row)
