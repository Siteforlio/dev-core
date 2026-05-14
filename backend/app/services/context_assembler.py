import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.knowledge_service import KnowledgeService
from app.services.jd_parser_service import JDParserService
from app.services.progress_service import ProgressService
from app.graph.round_queries import get_round_context


class ContextAssembler:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def assemble(
        self,
        user_id: str,
        company: str,
        role: str,
        career_track: str,
        level: str,
        interview_stage: str,
        jd_text: str | None = None,
        manager_name: str | None = None,
    ) -> dict:
        knowledge_svc = KnowledgeService(db=self.db)
        jd_svc = JDParserService()
        progress_svc = ProgressService(db=self.db)

        knowledge_profile, jd_analysis, graph_context, weak_dimensions = await asyncio.gather(
            knowledge_svc.get_profile(career_track, level, interview_stage),
            jd_svc.parse(jd_text) if jd_text else _empty(),
            get_round_context(company, interview_stage),
            progress_svc.get_weak_dimensions(user_id, career_track),
        )

        return {
            "company": company,
            "role": role,
            "career_track": career_track,
            "level": level,
            "interview_stage": interview_stage,
            "knowledge_profile": knowledge_profile or {},
            "jd_analysis": jd_analysis,
            "graph_context": graph_context,
            "user_weak_dimensions": weak_dimensions,
            "manager_name": manager_name,
        }


async def _empty() -> dict:
    return {}
