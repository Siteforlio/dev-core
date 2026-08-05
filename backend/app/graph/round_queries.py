"""Interview round graph queries — SQLAlchemy/SQLite implementation (replaces Neo4j Cypher)."""
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.pg.graph import InterviewRound, InterviewQuestion


async def get_questions_for_round(company_name: str, round_type: str) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(InterviewQuestion)
            .join(InterviewRound, InterviewRound.id == InterviewQuestion.round_id)
            .where(
                InterviewRound.company_name == company_name,
                InterviewRound.type == round_type,
            )
        )
        questions = result.scalars().all()
        return [{"text": q.text, "difficulty": q.difficulty} for q in questions]


async def get_round_context(company_name: str, round_type: str) -> dict:
    questions = await get_questions_for_round(company_name, round_type)
    return {
        "company": company_name,
        "round_type": round_type,
        "sample_questions": questions,
    }


async def seed_rounds(round_data: list[dict]):
    """round_data: [{company, type, questions: [{text, difficulty}]}]"""
    async with AsyncSessionLocal() as db:
        for entry in round_data:
            # Upsert the round
            round_result = await db.execute(
                select(InterviewRound).where(
                    InterviewRound.company_name == entry["company"],
                    InterviewRound.type == entry["type"],
                )
            )
            round_obj = round_result.scalar_one_or_none()
            if round_obj is None:
                round_obj = InterviewRound(
                    company_name=entry["company"],
                    type=entry["type"],
                )
                db.add(round_obj)
                await db.flush()  # get round_obj.id before inserting questions

            # Upsert questions: load existing texts to avoid duplicates
            existing_q_result = await db.execute(
                select(InterviewQuestion.text).where(
                    InterviewQuestion.round_id == round_obj.id
                )
            )
            existing_texts = set(existing_q_result.scalars().all())

            for q in entry.get("questions", []):
                if q["text"] not in existing_texts:
                    db.add(InterviewQuestion(
                        round_id=round_obj.id,
                        text=q["text"],
                        difficulty=q.get("difficulty", "medium"),
                    ))

        await db.commit()
