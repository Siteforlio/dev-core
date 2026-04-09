from unittest.mock import AsyncMock, MagicMock, patch
from app.services.community_pipeline import CommunityPipeline


async def test_stage_anonymizes_pii():
    """Staged payload must not contain user_id or raw answers."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    pipeline = CommunityPipeline(db=mock_db)
    payload = await pipeline.stage(
        session_id="s1",
        user_id="user-secret-123",
        company="Google",
        role="SWE",
        rounds=[
            {
                "type": "behavioral",
                "grade": 7.5,
                "passed": True,
                "moments": [
                    {"question": "Tell me about yourself.", "answer": "I am John Smith.", "emotion": "confident"},
                ],
            }
        ],
    )

    assert "user_id" not in payload
    assert "user-secret-123" not in str(payload)
    assert payload["company"] == "Google"
    assert payload["role"] == "SWE"
    assert len(payload["rounds"]) == 1
    # answers should be stripped or hashed, not raw
    moment = payload["rounds"][0]["moments"][0]
    assert moment.get("answer") != "I am John Smith."


async def test_stage_writes_community_data_row():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    pipeline = CommunityPipeline(db=mock_db)
    await pipeline.stage(
        session_id="s1",
        user_id="u1",
        company="Meta",
        role="PM",
        rounds=[{"type": "behavioral", "grade": 6.0, "passed": True, "moments": []}],
    )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


async def test_flush_marks_rows_as_flushed():
    mock_db = AsyncMock()

    pending_row = MagicMock(
        id="cd1",
        flushed_to_graph=False,
        payload={"company": "Google", "role": "SWE", "rounds": [{"type": "behavioral", "grade": 7.0, "passed": True, "moments": []}]},
    )

    mock_db.execute = AsyncMock(
        return_value=MagicMock(**{"scalars.return_value.all.return_value": [pending_row]})
    )

    pipeline = CommunityPipeline(db=mock_db)
    with patch.object(pipeline, "_write_to_graph", new=AsyncMock()) as mock_write:
        flushed = await pipeline.flush_pending()

    assert flushed == 1
    assert pending_row.flushed_to_graph is True
    mock_write.assert_called_once()
    mock_db.commit.assert_called_once()


async def test_flush_skips_already_flushed():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(**{"scalars.return_value.all.return_value": []})
    )

    pipeline = CommunityPipeline(db=mock_db)
    flushed = await pipeline.flush_pending()

    assert flushed == 0
