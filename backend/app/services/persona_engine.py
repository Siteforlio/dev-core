from app.graph.manager_queries import get_managers_for_company
from app.graph.round_queries import get_round_context
from app.services.llm_orchestrator import LLMOrchestrator


class PersonaEngine:
    def __init__(self):
        self._orchestrator = LLMOrchestrator()

    async def get_graph_context(self, company: str, round_type: str) -> dict:
        return await get_round_context(company, round_type)

    async def build(self, company: str, role: str, round_type: str) -> str:
        managers = await get_managers_for_company(company)
        round_ctx = await get_round_context(company, round_type)

        if managers:
            manager_context = {
                "managers": managers,
                "round_patterns": round_ctx,
            }
        else:
            manager_context = {
                "managers": [],
                "round_patterns": round_ctx,
            }

        return await self._orchestrator.build_persona(
            company=company,
            role=role,
            manager_context=manager_context,
        )
