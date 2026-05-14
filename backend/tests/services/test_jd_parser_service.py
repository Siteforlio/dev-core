import pytest
import json
from unittest.mock import AsyncMock, patch
from app.services.jd_parser_service import JDParserService

SAMPLE_JD = """
We are looking for a Senior Software Engineer to join our platform team.
Required: 5+ years Python, distributed systems experience, strong communication skills.
Nice to have: Kubernetes, Rust. Fast-paced environment, high ownership expected.
"""

@pytest.mark.asyncio
async def test_parse_returns_structured_output():
    svc = JDParserService()
    mock_response = {
        "required_skills": ["Python", "distributed systems"],
        "preferred_skills": ["Kubernetes", "Rust"],
        "culture_signals": ["fast-paced", "high ownership"],
        "red_flags_to_avoid": [],
        "implied_seniority": "senior",
        "key_responsibilities": ["platform engineering"],
    }
    # Patch at the service module level (service imported cache_get directly)
    with patch("app.services.jd_parser_service.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.services.jd_parser_service.cache_set", new=AsyncMock()), \
         patch.object(svc, '_call_llm', new=AsyncMock(return_value=json.dumps(mock_response))):
        result = await svc.parse(SAMPLE_JD)
    assert "required_skills" in result
    assert result["required_skills"] == ["Python", "distributed systems"]
    assert "culture_signals" in result


@pytest.mark.asyncio
async def test_parse_returns_empty_dict_for_blank_jd():
    svc = JDParserService()
    result = await svc.parse("")
    assert result == {}


@pytest.mark.asyncio
async def test_parse_returns_empty_dict_for_whitespace_jd():
    svc = JDParserService()
    result = await svc.parse("   ")
    assert result == {}


@pytest.mark.asyncio
async def test_parse_uses_cache_on_second_call():
    svc = JDParserService()
    cached_data = {"required_skills": ["Python"], "culture_signals": ["remote-first"]}
    with patch("app.services.jd_parser_service.cache_get", new=AsyncMock(return_value=cached_data)):
        result = await svc.parse(SAMPLE_JD)
    assert result == cached_data
