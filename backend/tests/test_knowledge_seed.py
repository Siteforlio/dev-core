from app.graph.knowledge_seed import NEGOTIATION_PROFILES, TRACKS, RUBRICS

def test_negotiation_profiles_covers_all_tracks():
    assert set(NEGOTIATION_PROFILES.keys()) == set(TRACKS)

def test_negotiation_profile_structure():
    for track, profile in NEGOTIATION_PROFILES.items():
        assert "core_competencies" in profile
        assert len(profile["core_competencies"]) == 5
        assert "question_archetypes" in profile
        assert len(profile["question_archetypes"]) == 3
        assert "evaluation_rubrics" in profile
        assert profile["evaluation_rubrics"] is RUBRICS
        assert "skill_dimensions" in profile
        for dim in ["communication_clarity", "quantified_impact", "executive_presence"]:
            assert dim in profile["skill_dimensions"], f"Missing {dim} in track {track}"

def test_negotiation_profile_question_weights_sum_to_one():
    for track, profile in NEGOTIATION_PROFILES.items():
        total = sum(a["weight"] for a in profile["question_archetypes"])
        assert abs(total - 1.0) < 0.01, f"weights don't sum to 1 for track {track}"
