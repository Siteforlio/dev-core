from unittest.mock import AsyncMock, MagicMock, patch
from app.services.debrief_service import DebriefService, _extract_dimension_scores


def _exec_scalars(rows):
    m = MagicMock()
    m.scalars.return_value.all.return_value = rows
    return m


def _exec_scalar_one(value):
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


async def test_generate_debrief_returns_structured_report():
    mock_db = AsyncMock()
    mock_session = MagicMock(id="s1", company="Google", role="SWE")
    mock_round = MagicMock(id="r1", type="behavioral", grade=7.5, passed=True)
    mock_moment = MagicMock(
        question="Tell me about yourself.",
        answer="I am a SWE.",
        emotion_state="confident",
        round_id="r1",
    )

    mock_db.execute = AsyncMock(side_effect=[
        _exec_scalar_one(mock_session),
        _exec_scalars([mock_round]),
    ])

    service = DebriefService(db=mock_db)
    with patch.object(service, '_get_moments', new=AsyncMock(return_value=[mock_moment])):
        with patch.object(service, '_call_llm', new=AsyncMock(return_value={
            "overall_score": 7.5,
            "strengths": ["Clear communication"],
            "improvements": ["More specifics"],
            "recommendation": "Strong candidate",
            "top_3_focus_areas": ["Communication", "Quantified impact", "Problem solving"],
            "recommended_next_session": "Practice Hiring Manager stage at Senior level",
        })):
            result = await service.generate(session_id="s1")

    assert "overall_score" in result
    assert "strengths" in result
    assert "rounds" in result
    assert "top_3_focus_areas" in result
    assert "recommended_next_session" in result
    assert result["top_3_focus_areas"] == ["Communication", "Quantified impact", "Problem solving"]
    assert result["recommended_next_session"] == "Practice Hiring Manager stage at Senior level"


async def test_generate_debrief_includes_emotion_summary():
    mock_db = AsyncMock()
    mock_session = MagicMock(id="s1", company="Meta", role="PM")

    mock_db.execute = AsyncMock(side_effect=[
        _exec_scalar_one(mock_session),
        _exec_scalars([]),
    ])

    service = DebriefService(db=mock_db)
    with patch.object(service, '_get_moments', new=AsyncMock(return_value=[])):
        with patch.object(service, '_call_llm', new=AsyncMock(return_value={
            "overall_score": 5.0, "strengths": [], "improvements": [], "recommendation": "Needs work",
            "top_3_focus_areas": [], "recommended_next_session": "",
        })):
            result = await service.generate(session_id="s1")
    assert "emotion_summary" in result
    assert "top_3_focus_areas" in result
    assert "recommended_next_session" in result


def test_extract_dimension_scores_returns_seven_dimensions():
    analysis = {
        "overall_score": 7.0,
        "strengths": ["Strong communication clarity"],
        "improvements": ["Needs more quantified impact"],
    }
    scores = _extract_dimension_scores(analysis, rounds=[])

    expected_dims = {
        "domain_knowledge",
        "communication_clarity",
        "quantified_impact",
        "leadership_narrative",
        "culture_alignment",
        "executive_presence",
        "problem_solving",
    }
    assert set(scores.keys()) == expected_dims
    for dim, val in scores.items():
        assert isinstance(val, float), f"{dim} should be float, got {type(val)}"
        assert 0.0 <= val <= 10.0, f"{dim} value {val} out of [0.0, 10.0] range"


def test_extract_dimension_scores_adjusts_for_strengths_and_improvements():
    analysis = {
        "overall_score": 6.0,
        "strengths": ["excellent communication clarity"],
        "improvements": ["poor problem solving skills"],
    }
    scores = _extract_dimension_scores(analysis, rounds=[])

    # communication_clarity should be boosted
    assert scores["communication_clarity"] > 6.0
    # problem_solving should be reduced
    assert scores["problem_solving"] < 6.0


def test_extract_dimension_scores_no_improvements_uses_higher_quantified_impact():
    analysis_no_improvements = {"overall_score": 8.0, "strengths": [], "improvements": []}
    analysis_with_improvements = {"overall_score": 8.0, "strengths": [], "improvements": ["some area"]}

    scores_no_imp = _extract_dimension_scores(analysis_no_improvements, rounds=[])
    scores_with_imp = _extract_dimension_scores(analysis_with_improvements, rounds=[])

    # With no improvements, quantified_impact = overall * 0.9 = 7.2
    # With improvements, quantified_impact = overall * 0.7 = 5.6
    assert scores_no_imp["quantified_impact"] > scores_with_imp["quantified_impact"]
