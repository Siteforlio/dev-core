"""Community round queries — SQLAlchemy/SQLite implementation (replaces Neo4j Cypher)."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.database import AsyncSessionLocal
from app.models.pg.graph import CommunityRound


async def write_community_round(
    company: str,
    role: str,
    round_type: str,
    grade: float | None,
    passed: bool | None,
    moments: list[dict],
):
    """Upsert a CommunityRound, incrementing sample_count and updating rolling avg_grade."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CommunityRound).where(
                CommunityRound.company_name == company,
                CommunityRound.role == role,
                CommunityRound.round_type == round_type,
            )
        )
        cr = result.scalar_one_or_none()

        if cr is None:
            cr = CommunityRound(
                company_name=company,
                role=role,
                round_type=round_type,
                sample_count=1,
                avg_grade=grade,
            )
            try:
                db.add(cr)
                await db.commit()
            except IntegrityError:
                # Concurrent call inserted the row between our SELECT and INSERT — re-fetch and update
                await db.rollback()
                result = await db.execute(
                    select(CommunityRound).where(
                        CommunityRound.company_name == company,
                        CommunityRound.role == role,
                        CommunityRound.round_type == round_type,
                    )
                )
                cr = result.scalar_one()
                new_count = cr.sample_count + 1
                if grade is not None:
                    if cr.avg_grade is None:
                        cr.avg_grade = grade
                    else:
                        cr.avg_grade = (cr.avg_grade * cr.sample_count + grade) / new_count
                cr.sample_count = new_count
                await db.commit()
        else:
            new_count = cr.sample_count + 1
            if grade is not None:
                if cr.avg_grade is None:
                    cr.avg_grade = grade  # first graded sample — don't dilute with ungraded entries
                else:
                    cr.avg_grade = (cr.avg_grade * cr.sample_count + grade) / new_count
            cr.sample_count = new_count
            await db.commit()


async def get_community_stats(company: str, round_type: str) -> dict:
    """Return aggregated community performance data for a company+round."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CommunityRound).where(
                CommunityRound.company_name == company,
                CommunityRound.round_type == round_type,
            )
        )
        rows = result.scalars().all()
        if not rows:
            return {"avg_grade": None, "sample_count": 0}

        # Aggregate across all roles for the given company+round_type
        total_samples = sum(r.sample_count for r in rows)
        weighted_sum = sum(
            (r.avg_grade or 0.0) * r.sample_count for r in rows if r.avg_grade is not None
        )
        graded_samples = sum(r.sample_count for r in rows if r.avg_grade is not None)
        avg = weighted_sum / graded_samples if graded_samples > 0 else None
        return {"avg_grade": avg, "sample_count": total_samples}
