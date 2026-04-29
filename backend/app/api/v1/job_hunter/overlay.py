"""
GET /api/v1/job-hunter/applications

Returns applications the user can load as context into the DevCore overlay
Session Setup "Applied Job" tab (design spec §5).  The overlay needs a quick
list to display — resume/JD text is fetched separately once the user picks one.
"""
from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from app.models.pg.job_hunter import Application, JobListing

router = APIRouter(prefix="/job-hunter", tags=["job-hunter-overlay"])
bearer = HTTPBearer()


def _get_user_id(credentials=Depends(bearer)) -> str:
    return decode_token(credentials.credentials)


@router.get("/applications", response_model=dict)
async def list_applications_for_overlay(
    status: str = Query(default="interview,screening", description="Comma-separated statuses"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(_get_user_id),
):
    """List the user's applications in the given statuses for the overlay Session Setup picker."""
    statuses = [s.strip() for s in status.split(",") if s.strip()]

    result = await db.execute(
        select(Application, JobListing)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .where(
            Application.user_id == user_id,
            Application.status.in_(statuses),
        )
        .order_by(Application.status_updated_at.desc())
        .limit(limit)
    )
    rows = result.all()

    applications = [
        {
            "application_id": app.id,
            "campaign_id": app.campaign_id,
            "job_title": listing.title,
            "company": listing.company,
            "status": app.status,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "status_updated_at": app.status_updated_at.isoformat() if app.status_updated_at else None,
        }
        for app, listing in rows
    ]

    return {"data": applications, "error": None}


@router.get("/applications/{application_id}/context", response_model=dict)
async def get_application_context(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(_get_user_id),
):
    """Return JD text + resume context for a selected application (used by overlay Session Setup)."""
    from app.models.pg.job_hunter import CampaignProfile
    import json

    result = await db.execute(
        select(Application, JobListing)
        .join(JobListing, Application.job_listing_id == JobListing.id)
        .where(Application.id == application_id, Application.user_id == user_id)
    )
    row = result.first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Application not found")
    app, listing = row

    # Fetch campaign profile for resume context
    profile_result = await db.execute(
        select(CampaignProfile).where(
            CampaignProfile.campaign_id == app.campaign_id,
            CampaignProfile.user_id == user_id,
        )
    )
    profile = profile_result.scalar_one_or_none()

    # Build a plain-text resume summary from structured profile fields
    resume_text = ""
    if profile:
        parts: list[str] = []
        if profile.raw_context:
            parts.append(profile.raw_context)
        if profile.work_experience:
            parts.append("Work experience: " + json.dumps(profile.work_experience))
        if profile.skills:
            parts.append("Skills: " + ", ".join(
                (s.get("name") or s) if isinstance(s, dict) else str(s)
                for s in profile.skills
            ))
        if profile.projects:
            parts.append("Projects: " + json.dumps(profile.projects))
        resume_text = "\n\n".join(parts)

    return {
        "job_title": listing.title,
        "company": listing.company,
        "jd_text": listing.description or "",
        "resume_text": resume_text,
        "error": None,
    }
