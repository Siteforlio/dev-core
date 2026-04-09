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
