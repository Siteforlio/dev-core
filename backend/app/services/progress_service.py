# backend/app/services/progress_service.py
import uuid
import inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.progress import UserProgress


async def _resolve(val):
    """Await the value if it is awaitable (supports both real SQLAlchemy and AsyncMock)."""
    if inspect.isawaitable(val):
        return await val
    return val


async def _scalars_all(result) -> list:
    scalars = await _resolve(result.scalars())
    rows = await _resolve(scalars.all())
    return rows


class ProgressService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_scores(
        self,
        user_id: str,
        session_id: str,
        career_track: str,
        level: str,
        stage: str,
        scores: dict[str, float],
    ) -> None:
        for dimension, score in scores.items():
            row = UserProgress(
                id=str(uuid.uuid4()),
                user_id=user_id,
                session_id=session_id,
                career_track=career_track,
                level=level,
                stage=stage,
                skill_dimension=dimension,
                score=max(0.0, min(10.0, score)),
            )
            self.db.add(row)
        await self.db.commit()

    async def get_weak_dimensions(
        self, user_id: str, career_track: str, n: int = 3
    ) -> list[str]:
        result = await self.db.execute(
            select(UserProgress)
            .where(UserProgress.user_id == user_id, UserProgress.career_track == career_track)
            .order_by(UserProgress.recorded_at.desc())
            .limit(50)
        )
        rows = await _scalars_all(result)
        if not rows:
            return []
        avgs: dict[str, list[float]] = {}
        for row in rows:
            avgs.setdefault(row.skill_dimension, []).append(row.score)
        avg_scores = {dim: sum(scores) / len(scores) for dim, scores in avgs.items()}
        return sorted(avg_scores, key=lambda d: avg_scores[d])[:n]

    async def get_summary(self, user_id: str) -> dict:
        result = await self.db.execute(
            select(UserProgress)
            .where(UserProgress.user_id == user_id)
            .order_by(UserProgress.recorded_at.desc())
            .limit(200)
        )
        rows = await _scalars_all(result)
        if not rows:
            return {"dimensions": {}, "total_sessions": 0, "average_score": 0.0}

        dim_scores: dict[str, list[float]] = {}
        session_ids = set()
        for row in rows:
            dim_scores.setdefault(row.skill_dimension, []).append(row.score)
            session_ids.add(row.session_id)

        dimensions = {
            dim: round(sum(scores) / len(scores), 2)
            for dim, scores in dim_scores.items()
        }
        all_scores = [s for scores in dim_scores.values() for s in scores]
        return {
            "dimensions": dimensions,
            "total_sessions": len(session_ids),
            "average_score": round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0,
        }
