import pytest
from unittest.mock import AsyncMock, patch
from app.services.context_assembler import ContextAssembler


@pytest.mark.asyncio
async def test_assemble_returns_merged_context():
    mock_db = AsyncMock()

    with patch("app.services.context_assembler.KnowledgeService") as MockKS, \
         patch("app.services.context_assembler.JDParserService") as MockJD, \
         patch("app.services.context_assembler.get_round_context", new=AsyncMock(return_value={})), \
         patch("app.services.context_assembler.ProgressService") as MockPS:

        MockKS.return_value.get_profile = AsyncMock(return_value={
            "core_competencies": ["Python", "system design"],
            "skill_dimensions": ["domain_knowledge"],
        })
        MockJD.return_value.parse = AsyncMock(return_value={
            "required_skills": ["Python"],
            "culture_signals": ["fast-paced"],
        })
        MockPS.return_value.get_weak_dimensions = AsyncMock(return_value=["communication_clarity"])

        assembler = ContextAssembler(db=mock_db)
        ctx = await assembler.assemble(
            user_id="u1", company="Stripe", role="SWE",
            career_track="technology", level="senior",
            interview_stage="hr_interview", jd_text="Python engineer role",
        )

    assert ctx["knowledge_profile"]["core_competencies"] == ["Python", "system design"]
    assert ctx["jd_analysis"]["required_skills"] == ["Python"]
    assert "communication_clarity" in ctx["user_weak_dimensions"]


@pytest.mark.asyncio
async def test_assemble_works_without_jd():
    mock_db = AsyncMock()
    with patch("app.services.context_assembler.KnowledgeService") as MockKS, \
         patch("app.services.context_assembler.JDParserService") as MockJD, \
         patch("app.services.context_assembler.get_round_context", new=AsyncMock(return_value={})), \
         patch("app.services.context_assembler.ProgressService") as MockPS:

        MockKS.return_value.get_profile = AsyncMock(return_value={"core_competencies": []})
        MockJD.return_value.parse = AsyncMock(return_value={})
        MockPS.return_value.get_weak_dimensions = AsyncMock(return_value=[])

        assembler = ContextAssembler(db=mock_db)
        ctx = await assembler.assemble(
            user_id="u1", company="Google", role="PM",
            career_track="technology", level="mid_level",
            interview_stage="hr_interview", jd_text=None,
        )

    assert ctx["jd_analysis"] == {}


@pytest.mark.asyncio
async def test_assemble_context_keys():
    mock_db = AsyncMock()
    with patch("app.services.context_assembler.KnowledgeService") as MockKS, \
         patch("app.services.context_assembler.JDParserService") as MockJD, \
         patch("app.services.context_assembler.get_round_context", new=AsyncMock(return_value={"rounds": []})), \
         patch("app.services.context_assembler.ProgressService") as MockPS:

        MockKS.return_value.get_profile = AsyncMock(return_value={})
        MockJD.return_value.parse = AsyncMock(return_value={})
        MockPS.return_value.get_weak_dimensions = AsyncMock(return_value=[])

        assembler = ContextAssembler(db=mock_db)
        ctx = await assembler.assemble(
            user_id="u1", company="Meta", role="PM",
            career_track="business_consulting", level="senior",
            interview_stage="panel_interview", jd_text=None,
            manager_name="John Doe",
        )

    required_keys = {"company", "role", "career_track", "level", "interview_stage",
                     "knowledge_profile", "jd_analysis", "graph_context",
                     "user_weak_dimensions", "manager_name"}
    assert required_keys.issubset(ctx.keys())
    assert ctx["manager_name"] == "John Doe"
