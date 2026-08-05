"""Manager graph queries — SQLAlchemy/SQLite implementation (replaces Neo4j Cypher)."""
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.pg.graph import Manager


async def get_managers_for_company(company_name: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Manager).where(Manager.company_name == company_name)
        )
        managers = result.scalars().all()
        return [
            {"name": m.name, "title": m.title, "traits": m.traits or []}
            for m in managers
        ]


async def get_manager_history(manager_name: str) -> list[dict]:
    """Return current company association for a manager.

    Note: PREVIOUSLY_AT relationships don't exist in the SQLite model (single-user
    desktop app). Returns current WORKS_AT only.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Manager).where(Manager.name == manager_name)
        )
        manager = result.scalar_one_or_none()
        if manager is None or manager.company_name is None:
            return []
        return [
            {
                "company": manager.company_name,
                "title": manager.title,
                "relationship": "WORKS_AT",
            }
        ]


async def record_manager_move(
    manager_name: str,
    from_company: str,
    to_company: str,
    new_title: str,
):
    """Update manager's company and title (no PREVIOUSLY_AT tracking in SQLite model)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Manager).where(Manager.name == manager_name)
        )
        manager = result.scalar_one_or_none()
        if manager:
            manager.company_name = to_company
            manager.title = new_title
            await db.commit()


async def seed_managers(managers: list[dict]):
    """managers: [{name, title, company, traits: [str]}]"""
    async with AsyncSessionLocal() as db:
        for m in managers:
            result = await db.execute(
                select(Manager).where(Manager.name == m["name"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                db.add(Manager(
                    name=m["name"],
                    title=m.get("title"),
                    company_name=m.get("company"),
                    traits=m.get("traits", []),
                ))
            else:
                existing.title = m.get("title")
                existing.company_name = m.get("company")
                existing.traits = m.get("traits", [])
        await db.commit()
