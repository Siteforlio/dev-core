from app.graph.connection import get_driver


async def get_all_companies() -> list[dict]:
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (c:Company) RETURN c.name AS name, c.industry AS industry ORDER BY c.name"
        )
        return [{"name": r["name"], "industry": r["industry"]} async for r in result]


async def get_round_types(company_name: str) -> list[str]:
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (c:Company {name: $name})-[:HAS_ROUND]->(r:RoundType) RETURN DISTINCT r.type AS type",
            name=company_name,
        )
        return [r["type"] async for r in result]


async def seed_companies(companies: list[dict]):
    driver = await get_driver()
    async with driver.session() as session:
        for company in companies:
            await session.run(
                "MERGE (c:Company {name: $name}) SET c.industry = $industry",
                name=company["name"],
                industry=company["industry"],
            )
