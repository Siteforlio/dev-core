class CompanyService:
    def __init__(self, graph):
        self.graph = graph

    async def list_companies(self) -> list[dict]:
        return await self.graph.get_all_companies()

    async def get_round_types(self, company_name: str) -> list[str]:
        types = await self.graph.get_round_types(company_name)
        if not types:
            return ["HR", "behavioral", "technical"]
        return types
