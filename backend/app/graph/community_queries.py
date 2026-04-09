from app.graph.connection import get_driver


async def write_community_round(
    company: str,
    role: str,
    round_type: str,
    grade: float | None,
    passed: bool | None,
    moments: list[dict],
):
    """Write an anonymized round outcome into the community knowledge graph."""
    driver = await get_driver()
    async with driver.session() as session:
        await session.run(
            """
            MATCH (c:Company {name: $company})
            MATCH (r:RoundType {type: $round_type})<-[:HAS_ROUND]-(c)
            MERGE (cr:CommunityRound {
                company: $company,
                role: $role,
                round_type: $round_type
            })
            SET cr.sample_count = coalesce(cr.sample_count, 0) + 1,
                cr.avg_grade    = (coalesce(cr.avg_grade, 0) * coalesce(cr.sample_count - 1, 0) + coalesce($grade, 0))
                                  / cr.sample_count
            """,
            company=company,
            role=role,
            round_type=round_type,
            grade=grade,
        )


async def get_community_stats(company: str, round_type: str) -> dict:
    """Return aggregated community performance data for a company+round."""
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (cr:CommunityRound {company: $company, round_type: $round_type})
            RETURN cr.avg_grade AS avg_grade, cr.sample_count AS sample_count
            """,
            company=company,
            round_type=round_type,
        )
        rows = [r async for r in result]
        if not rows:
            return {"avg_grade": None, "sample_count": 0}
        return {"avg_grade": rows[0]["avg_grade"], "sample_count": rows[0]["sample_count"]}
