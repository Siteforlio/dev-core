# backend/app/services/knowledge_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.knowledge import KnowledgeProfile


class KnowledgeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, track: str, level: str, stage: str) -> dict | None:
        result = await self.db.execute(
            select(KnowledgeProfile).where(
                KnowledgeProfile.track == track,
                KnowledgeProfile.level == level,
                KnowledgeProfile.stage == stage,
            )
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile.profile

        # Fallback: same track + level, hr_interview stage
        fallback = await self.db.execute(
            select(KnowledgeProfile).where(
                KnowledgeProfile.track == track,
                KnowledgeProfile.level == level,
                KnowledgeProfile.stage == "hr_interview",
            )
        )
        fb = fallback.scalar_one_or_none()
        return fb.profile if fb else None
