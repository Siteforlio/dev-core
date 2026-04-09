from app.graph.connection import get_driver


async def get_managers_for_company(company_name: str) -> list[dict]:
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:HiringManager)-[:WORKS_AT]->(c:Company {name: $name})
            OPTIONAL MATCH (m)-[:HAS_TRAIT]->(t:Trait)
            WITH m, collect(t.name) AS traits
            RETURN m.name AS name, m.title AS title, traits
            """,
            name=company_name,
        )
        rows = []
        async for r in result:
            rows.append({"name": r["name"], "title": r["title"], "traits": r["traits"]})
        return rows


async def get_manager_history(manager_name: str) -> list[dict]:
    """Return all companies a manager has been associated with (current + previous)."""
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (m:HiringManager {name: $name})-[rel:WORKS_AT|PREVIOUSLY_AT]->(c:Company)
            RETURN c.name AS company, m.title AS title, type(rel) AS relationship
            """,
            name=manager_name,
        )
        rows = []
        async for r in result:
            rows.append({
                "company": r["company"],
                "title": r["title"],
                "relationship": r["relationship"],
            })
        return rows


async def record_manager_move(
    manager_name: str,
    from_company: str,
    to_company: str,
    new_title: str,
):
    """Demote current WORKS_AT to PREVIOUSLY_AT and create new WORKS_AT."""
    driver = await get_driver()
    async with driver.session() as session:
        await session.run(
            """
            MATCH (m:HiringManager {name: $name})-[old:WORKS_AT]->(old_co:Company {name: $from_company})
            MATCH (new_co:Company {name: $to_company})
            DELETE old
            MERGE (m)-[:PREVIOUSLY_AT]->(old_co)
            MERGE (m)-[:WORKS_AT]->(new_co)
            SET m.title = $new_title
            """,
            name=manager_name,
            from_company=from_company,
            to_company=to_company,
            new_title=new_title,
        )


async def seed_managers(managers: list[dict]):
    """managers: [{name, title, company, traits: [str]}]"""
    driver = await get_driver()
    async with driver.session() as session:
        for m in managers:
            await session.run(
                """
                MERGE (mgr:HiringManager {name: $name})
                SET mgr.title = $title
                WITH mgr
                MATCH (c:Company {name: $company})
                MERGE (mgr)-[:WORKS_AT]->(c)
                """,
                name=m["name"], title=m["title"], company=m["company"],
            )
            for trait in m.get("traits", []):
                await session.run(
                    """
                    MATCH (mgr:HiringManager {name: $name})
                    MERGE (t:Trait {name: $trait})
                    MERGE (mgr)-[:HAS_TRAIT]->(t)
                    """,
                    name=m["name"], trait=trait,
                )
