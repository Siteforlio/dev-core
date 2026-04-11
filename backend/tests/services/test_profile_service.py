import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.job_hunter.profile_service import ProfileService


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db


async def test_check_completeness_incomplete_returns_missing_fields(mock_db):
    service = ProfileService(mock_db)
    profile_data = {"work_experience": [], "education": [], "skills": [], "projects": [], "languages_spoken": []}
    result = service.check_completeness(profile_data)
    assert result["is_complete"] is False
    assert "work_experience" in result["missing"]


async def test_check_completeness_complete_returns_true(mock_db):
    service = ProfileService(mock_db)
    profile_data = {
        "full_name": "Jane Doe", "email": "jane@example.com", "phone": "+1234567890",
        "city": "London", "country": "GB", "linkedin_url": "https://linkedin.com/in/jane",
        "github_url": "https://github.com/jane",
        "work_experience": [{"company": "Acme", "title": "Engineer", "start_date": "2022-01", "end_date": "Present", "responsibilities": "Built stuff"}],
        "education": [{"degree": "BSc", "institution": "MIT", "field": "CS", "graduation_year": 2021}],
        "skills": ["Python", "Django", "PostgreSQL"],
        "projects": [{"name": "MyApp", "description": "A cool app", "tech_stack": ["Python"], "link": "https://github.com/jane/myapp"}],
        "languages_spoken": [{"language": "English", "proficiency": "Native"}],
    }
    result = service.check_completeness(profile_data)
    assert result["is_complete"] is True
    assert result["missing"] == []


async def test_parse_resume_text_extracts_skills(mock_db):
    service = ProfileService(mock_db)
    resume_text = "Skills: Python, Django, React\nExperience: Software Engineer at Google"

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"skills": ["Python", "Django", "React"], "full_name": null, "email": null, "phone": null, "city": null, "country": null, "linkedin_url": null, "github_url": null, "work_experience": [], "education": [], "projects": [], "languages_spoken": []}')]

    service._client = MagicMock()
    service._client.messages.create = AsyncMock(return_value=mock_message)

    result = await service.parse_resume_text(resume_text)
    assert isinstance(result, dict)
    assert "skills" in result
