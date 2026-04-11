from app.graph.manager_queries import get_managers_for_company, get_manager_history
from app.graph.round_queries import get_round_context
from app.services.llm_orchestrator import LLMOrchestrator


class PersonaEngine:
    def __init__(self):
        self._orchestrator = LLMOrchestrator()

    async def get_graph_context(self, company: str, round_type: str) -> dict:
        return await get_round_context(company, round_type)

    async def _assemble_context(self, company: str, role: str, round_type: str) -> dict:
        """Shared helper: fetch graph data and return structured context dict."""
        managers = await get_managers_for_company(company)
        round_ctx = await get_round_context(company, round_type)
        enriched_managers = []
        for m in managers:
            history = await get_manager_history(m["name"])
            previous = [h for h in history if h["relationship"] == "PREVIOUSLY_AT"]
            enriched_managers.append({**m, "previous_companies": [h["company"] for h in previous]})
        return {"managers": enriched_managers, "round_patterns": round_ctx}

    async def build(self, company: str, role: str, round_type: str) -> str:
        """Build persona string — return type unchanged."""
        manager_context = await self._assemble_context(company, role, round_type)
        return await self._orchestrator.build_persona(
            company=company, role=role, manager_context=manager_context,
        )

    async def get_context(self, company: str, role: str, round_type: str = "HR") -> dict:
        """Return structured context dict + persona string for the Interview Prep bridge."""
        manager_context = await self._assemble_context(company, role, round_type)
        persona_string = await self._orchestrator.build_persona(
            company=company, role=role, manager_context=manager_context,
        )
        return {**manager_context, "persona_string": persona_string}
