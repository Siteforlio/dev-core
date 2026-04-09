from app.graph.connection import get_driver


async def get_questions_for_round(company_name: str, round_type: str) -> list[dict]:
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (c:Company {name: $name})-[:HAS_ROUND]->(r:RoundType {type: $round_type})
                  -[:HAS_QUESTION]->(q:Question)
            RETURN q.text AS text, q.difficulty AS difficulty
            """,
            name=company_name,
            round_type=round_type,
        )
        rows = []
        async for rec in result:
            rows.append({"text": rec["text"], "difficulty": rec["difficulty"]})
        return rows


async def get_round_context(company_name: str, round_type: str) -> dict:
    questions = await get_questions_for_round(company_name, round_type)
    return {
        "company": company_name,
        "round_type": round_type,
        "sample_questions": questions,
    }


async def seed_rounds(round_data: list[dict]):
    """round_data: [{company, type, questions: [{text, difficulty}]}]"""
    driver = await get_driver()
    async with driver.session() as session:
        for entry in round_data:
            await session.run(
                """
                MATCH (c:Company {name: $company})
                MERGE (r:RoundType {type: $type})<-[:HAS_ROUND]-(c)
                """,
                company=entry["company"],
                type=entry["type"],
            )
            for q in entry.get("questions", []):
                await session.run(
                    """
                    MATCH (c:Company {name: $company})-[:HAS_ROUND]->(r:RoundType {type: $type})
                    MERGE (q:Question {text: $text})
                    SET q.difficulty = $difficulty
                    MERGE (r)-[:HAS_QUESTION]->(q)
                    """,
                    company=entry["company"],
                    type=entry["type"],
                    text=q["text"],
                    difficulty=q.get("difficulty", "medium"),
                )
