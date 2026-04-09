import hashlib
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.community import CommunityData
from app.graph.community_queries import write_community_round


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash(value: str) -> str:
    """One-way hash for PII — irreversible but consistent within a session."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _anonymize_moments(moments: list[dict]) -> list[dict]:
    return [
        {
            "question": m["question"],
            "answer_length": len(m.get("answer", "")),
            "answer_hash": _hash(m.get("answer", "")),
            "emotion": m.get("emotion"),
        }
        for m in moments
    ]


class CommunityPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def stage(
        self,
        session_id: str,
        user_id: str,
        company: str,
        role: str,
        rounds: list[dict],
    ) -> dict:
        """Anonymize session data and write a pending CommunityData row."""
        payload = {
            "company": company,
            "role": role,
            "session_hash": _hash(session_id),
            "rounds": [
                {
                    "type": r["type"],
                    "grade": r.get("grade"),
                    "passed": r.get("passed"),
                    "moments": _anonymize_moments(r.get("moments", [])),
                }
                for r in rounds
            ],
        }

        row = CommunityData(
            id=str(uuid.uuid4()),
            payload=payload,
            flushed_to_graph=False,
            created_at=_utcnow(),
        )
        self.db.add(row)
        await self.db.commit()
        return payload

    async def _write_to_graph(self, payload: dict):
        """Write anonymized round data to Neo4j community pool."""
        for round_data in payload.get("rounds", []):
            await write_community_round(
                company=payload["company"],
                role=payload["role"],
                round_type=round_data["type"],
                grade=round_data.get("grade"),
                passed=round_data.get("passed"),
                moments=round_data.get("moments", []),
            )

    async def flush_pending(self) -> int:
        """Flush all un-flushed CommunityData rows to Neo4j. Returns count flushed."""
        result = await self.db.execute(
            select(CommunityData).where(CommunityData.flushed_to_graph == False)  # noqa: E712
        )
        rows = result.scalars().all()

        for row in rows:
            await self._write_to_graph(row.payload)
            row.flushed_to_graph = True
            row.flushed_at = _utcnow()

        if rows:
            await self.db.commit()

        return len(rows)
