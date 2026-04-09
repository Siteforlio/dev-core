from unittest.mock import AsyncMock, patch
from app.services.persona_engine import PersonaEngine


async def test_build_returns_persona_string():
    engine = PersonaEngine()
    with patch("app.services.persona_engine.get_managers_for_company", new=AsyncMock(return_value=[
        {"name": "Jeff Bezos", "title": "Former CEO", "traits": ["high-standards", "customer-obsessed"]},
    ])):
        with patch("app.services.persona_engine.get_round_context", new=AsyncMock(return_value={
            "company": "Amazon", "round_type": "behavioral",
            "sample_questions": [{"text": "Tell me about a time you failed.", "difficulty": "medium"}],
        })):
            with patch.object(engine._orchestrator, "build_persona", new=AsyncMock(
                return_value="Demanding, metrics-focused interviewer who values ownership."
            )):
                persona = await engine.build(company="Amazon", role="SWE", round_type="behavioral")

    assert isinstance(persona, str)
    assert len(persona) > 0


async def test_build_returns_fallback_when_no_graph_data():
    engine = PersonaEngine()
    with patch("app.services.persona_engine.get_managers_for_company", new=AsyncMock(return_value=[])):
        with patch("app.services.persona_engine.get_round_context", new=AsyncMock(return_value={
            "company": "Acme", "round_type": "behavioral", "sample_questions": [],
        })):
            with patch.object(engine._orchestrator, "build_persona", new=AsyncMock(
                return_value="Professional interviewer."
            )):
                persona = await engine.build(company="Acme", role="PM", round_type="behavioral")

    assert isinstance(persona, str)


async def test_get_graph_context_returns_dict():
    engine = PersonaEngine()
    with patch("app.services.persona_engine.get_round_context", new=AsyncMock(return_value={
        "company": "Google", "round_type": "technical",
        "sample_questions": [{"text": "LRU Cache implementation.", "difficulty": "hard"}],
    })):
        ctx = await engine.get_graph_context(company="Google", round_type="technical")

    assert ctx["company"] == "Google"
    assert len(ctx["sample_questions"]) == 1
