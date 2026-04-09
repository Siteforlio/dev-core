from unittest.mock import AsyncMock
from app.services.company_service import CompanyService


async def test_list_companies_returns_seeded_list():
    mock_graph = AsyncMock()
    mock_graph.get_all_companies.return_value = [
        {"name": "Google", "industry": "Tech"},
        {"name": "Meta", "industry": "Tech"},
    ]
    service = CompanyService(graph=mock_graph)
    companies = await service.list_companies()
    assert len(companies) == 2
    assert companies[0]["name"] == "Google"


async def test_get_round_types_for_company():
    mock_graph = AsyncMock()
    mock_graph.get_round_types.return_value = ["HR", "behavioral", "technical", "leetcode"]
    service = CompanyService(graph=mock_graph)
    rounds = await service.get_round_types("Google")
    assert "leetcode" in rounds


async def test_get_round_types_falls_back_when_empty():
    mock_graph = AsyncMock()
    mock_graph.get_round_types.return_value = []
    service = CompanyService(graph=mock_graph)
    rounds = await service.get_round_types("UnknownCorp")
    assert rounds == ["HR", "behavioral", "technical"]
