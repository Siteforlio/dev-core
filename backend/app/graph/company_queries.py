"""Company graph queries — SQLAlchemy/SQLite implementation (replaces Neo4j Cypher)."""
from sqlalchemy import select, distinct
from app.core.database import AsyncSessionLocal
from app.models.pg.graph import Company, InterviewRound


async def get_all_companies() -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Company).order_by(Company.name))
        companies = result.scalars().all()
        return [{"name": c.name, "industry": c.industry} for c in companies]


async def get_round_types(company_name: str) -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(distinct(InterviewRound.type)).where(
                InterviewRound.company_name == company_name
            )
        )
        return list(result.scalars().all())


async def seed_companies(companies: list[dict]):
    async with AsyncSessionLocal() as db:
        # Bulk pre-load all existing company names in one query — eliminates N+1
        names = [c["name"] for c in companies]
        existing_result = await db.execute(
            select(Company).where(Company.name.in_(names))
        )
        existing_names = {c.name for c in existing_result.scalars().all()}
        for company in companies:
            if company["name"] not in existing_names:
                db.add(Company(name=company["name"], industry=company.get("industry")))
        await db.commit()
