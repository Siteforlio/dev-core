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
        for company in companies:
            existing = await db.get(Company, company["name"])
            if existing is None:
                db.add(Company(name=company["name"], industry=company.get("industry")))
        await db.commit()
