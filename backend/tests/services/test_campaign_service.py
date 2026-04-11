import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.campaign_service import CampaignService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
    return db

async def test_infer_sub_categories_returns_list(mock_db):
    service = CampaignService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='["Mobile Development", "Flutter Development"]')):
        result = await service.infer_sub_categories(
            skills=["Flutter", "Dart", "Firebase"],
            broad_category="Software Engineering"
        )
    assert isinstance(result, list)
    assert "Mobile Development" in result

async def test_create_campaign_blocks_incomplete_profile(mock_db):
    service = CampaignService(mock_db)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=MagicMock(is_complete=False))
    mock_db.execute = AsyncMock(return_value=mock_result)
    with pytest.raises(ValueError, match="Profile incomplete"):
        await service.create_campaign(user_id="u1", name="Test", broad_category="Engineering", user_country="GB")

async def test_create_campaign_stores_sub_categories(mock_db):
    service = CampaignService(mock_db)
    mock_profile = MagicMock(is_complete=True, skills=["Flutter", "Dart"])
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_profile)
    mock_db.execute = AsyncMock(return_value=mock_result)
    with patch.object(service, "infer_sub_categories", new=AsyncMock(return_value=["Mobile Development"])):
        campaign = await service.create_campaign(user_id="u1", name="Mobile 2026", broad_category="Software Engineering", user_country="GB")
    assert campaign.sub_categories == ["Mobile Development"]
