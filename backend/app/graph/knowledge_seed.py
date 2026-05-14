# backend/app/graph/knowledge_seed.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.knowledge import KnowledgeProfile

TRACKS = [
    "technology", "finance_fintech", "healthcare", "business_consulting",
    "sales_marketing", "design_creative", "legal_compliance",
    "hr_people", "education_training", "operations_supply_chain",
]

LEVELS = ["entry_junior", "mid_level", "senior", "lead_manager", "director_vp_csuite"]

LEVEL_LABELS = {
    "entry_junior": "entry-level",
    "mid_level": "mid-level",
    "senior": "senior",
    "lead_manager": "manager/lead",
    "director_vp_csuite": "executive/C-suite",
}

TRACK_DATA = {
    "technology": {
        "label": "technology",
        "competencies": {
            "entry_junior": ["coding fundamentals", "debugging", "version control", "basic algorithms", "teamwork"],
            "mid_level": ["system design basics", "code quality", "testing", "API design", "problem solving"],
            "senior": ["architecture decisions", "performance optimization", "mentoring", "cross-team collaboration", "technical strategy"],
            "lead_manager": ["engineering management", "roadmap planning", "hiring", "stakeholder communication", "delivery"],
            "director_vp_csuite": ["technology vision", "organizational design", "budget ownership", "board communication", "competitive strategy"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "problem_solving", "leadership_narrative", "quantified_impact"],
    },
    "finance_fintech": {
        "label": "finance/fintech",
        "competencies": {
            "entry_junior": ["financial modeling basics", "Excel/spreadsheets", "data analysis", "attention to detail", "regulatory awareness"],
            "mid_level": ["financial analysis", "valuation", "risk assessment", "client communication", "reporting"],
            "senior": ["deal structuring", "portfolio management", "team leadership", "regulatory compliance", "P&L ownership"],
            "lead_manager": ["team building", "client relationships", "budget management", "strategy execution", "risk governance"],
            "director_vp_csuite": ["capital allocation", "M&A strategy", "board reporting", "regulatory leadership", "organizational design"],
        },
        "frameworks": ["STAR", "SOAR", "MECE", "Pyramid Principle"],
        "dimensions": ["domain_knowledge", "quantified_impact", "executive_presence", "leadership_narrative", "culture_alignment"],
    },
    "healthcare": {
        "label": "healthcare",
        "competencies": {
            "entry_junior": ["patient care basics", "clinical protocols", "documentation", "teamwork", "empathy"],
            "mid_level": ["clinical expertise", "patient outcomes", "interdisciplinary collaboration", "quality improvement", "evidence-based practice"],
            "senior": ["clinical leadership", "mentoring", "process improvement", "compliance", "complex case management"],
            "lead_manager": ["department management", "staff development", "budget oversight", "regulatory compliance", "strategic planning"],
            "director_vp_csuite": ["healthcare strategy", "population health", "organizational leadership", "board relations", "policy development"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment", "quantified_impact"],
    },
    "business_consulting": {
        "label": "business/consulting",
        "competencies": {
            "entry_junior": ["structured thinking", "data analysis", "presentation skills", "client interaction", "research"],
            "mid_level": ["project management", "client management", "hypothesis-driven analysis", "team coordination", "deliverable quality"],
            "senior": ["engagement leadership", "business development", "complex problem solving", "senior client relationships", "team development"],
            "lead_manager": ["practice leadership", "P&L management", "talent development", "key account ownership", "thought leadership"],
            "director_vp_csuite": ["firm strategy", "market positioning", "C-suite advisory", "organizational leadership", "business development"],
        },
        "frameworks": ["MECE", "Pyramid Principle", "STAR", "Case framework"],
        "dimensions": ["domain_knowledge", "problem_solving", "communication_clarity", "executive_presence", "quantified_impact"],
    },
    "sales_marketing": {
        "label": "sales/marketing",
        "competencies": {
            "entry_junior": ["product knowledge", "prospecting basics", "CRM usage", "communication", "resilience"],
            "mid_level": ["pipeline management", "negotiation", "account management", "data-driven marketing", "customer success"],
            "senior": ["revenue ownership", "team enablement", "strategic accounts", "go-to-market strategy", "forecasting"],
            "lead_manager": ["sales team leadership", "quota management", "hiring", "marketing strategy", "budget ownership"],
            "director_vp_csuite": ["revenue strategy", "market expansion", "brand leadership", "board reporting", "competitive positioning"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["quantified_impact", "domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment"],
    },
    "design_creative": {
        "label": "design/creative",
        "competencies": {
            "entry_junior": ["design tools", "visual communication", "user empathy", "iteration", "feedback receptiveness"],
            "mid_level": ["UX research", "interaction design", "design systems", "stakeholder communication", "data-informed design"],
            "senior": ["design strategy", "cross-functional leadership", "design ops", "mentoring", "systems thinking"],
            "lead_manager": ["team leadership", "design culture", "roadmap influence", "exec communication", "hiring"],
            "director_vp_csuite": ["design vision", "brand strategy", "organizational influence", "C-suite partnership", "design ROI"],
        },
        "frameworks": ["STAR", "Portfolio review"],
        "dimensions": ["domain_knowledge", "communication_clarity", "problem_solving", "leadership_narrative", "culture_alignment"],
    },
    "legal_compliance": {
        "label": "legal/compliance",
        "competencies": {
            "entry_junior": ["legal research", "contract basics", "attention to detail", "writing", "regulatory awareness"],
            "mid_level": ["contract negotiation", "risk analysis", "regulatory compliance", "client advisory", "litigation support"],
            "senior": ["complex transactions", "regulatory strategy", "team leadership", "senior client relationships", "risk management"],
            "lead_manager": ["practice management", "business development", "team development", "client retention", "compliance program ownership"],
            "director_vp_csuite": ["legal strategy", "board advisory", "M&A oversight", "regulatory leadership", "organizational governance"],
        },
        "frameworks": ["STAR", "IRAC"],
        "dimensions": ["domain_knowledge", "communication_clarity", "problem_solving", "executive_presence", "culture_alignment"],
    },
    "hr_people": {
        "label": "HR/people",
        "competencies": {
            "entry_junior": ["recruiting basics", "HRIS tools", "employee onboarding", "communication", "confidentiality"],
            "mid_level": ["talent acquisition", "employee relations", "performance management", "HR analytics", "L&D programs"],
            "senior": ["HR strategy", "organizational development", "change management", "total rewards", "culture programs"],
            "lead_manager": ["HR business partnership", "team leadership", "workforce planning", "senior stakeholder management", "DEI programs"],
            "director_vp_csuite": ["people strategy", "C-suite partnership", "organizational design", "culture transformation", "board reporting"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment", "quantified_impact"],
    },
    "education_training": {
        "label": "education/training",
        "competencies": {
            "entry_junior": ["lesson planning", "classroom management", "communication", "student engagement", "assessment design"],
            "mid_level": ["curriculum development", "differentiated instruction", "student outcomes", "parent communication", "professional development"],
            "senior": ["instructional leadership", "curriculum design", "teacher mentoring", "program evaluation", "stakeholder engagement"],
            "lead_manager": ["school/program leadership", "staff development", "budget management", "community relations", "strategic planning"],
            "director_vp_csuite": ["educational strategy", "policy development", "organizational leadership", "board relations", "system-wide improvement"],
        },
        "frameworks": ["STAR", "SOAR"],
        "dimensions": ["domain_knowledge", "communication_clarity", "leadership_narrative", "culture_alignment", "quantified_impact"],
    },
    "operations_supply_chain": {
        "label": "operations/supply chain",
        "competencies": {
            "entry_junior": ["process documentation", "data entry", "coordination", "problem identification", "tool proficiency"],
            "mid_level": ["process optimization", "vendor management", "project coordination", "data analysis", "cross-functional collaboration"],
            "senior": ["operations strategy", "supply chain design", "team leadership", "cost optimization", "risk management"],
            "lead_manager": ["operations management", "team development", "P&L ownership", "vendor strategy", "capacity planning"],
            "director_vp_csuite": ["supply chain strategy", "global operations", "organizational leadership", "board reporting", "digital transformation"],
        },
        "frameworks": ["STAR", "SOAR", "DMAIC"],
        "dimensions": ["domain_knowledge", "quantified_impact", "problem_solving", "leadership_narrative", "communication_clarity"],
    },
}

RUBRICS = {
    "excellent": "Quantified impact, structured answer, clear ownership, level-appropriate framing",
    "good": "Structured answer, relevant experience, some specifics, demonstrates growth",
    "needs_work": "Vague, limited specifics, missing ownership or metrics",
    "poor": "No structure, irrelevant, bad-mouths past employer, no self-awareness",
}

COMMON_PITFALLS = [
    "Answering at a lower seniority level than expected",
    "Not quantifying outcomes or impact",
    "Forgetting to ask questions at the end",
    "Over-explaining without landing a clear point",
    "Bad-mouthing a previous employer or colleague",
]

RED_FLAGS = [
    "Cannot describe impact of their work in numbers",
    "Blames others exclusively for past failures",
    "No questions for the interviewer",
    "Inconsistent career narrative",
    "Dismissive of the company's challenges",
]


def _build_profile(track: str, level: str, stage: str = "hr_interview") -> dict:
    t = TRACK_DATA[track]
    label = t["label"]
    level_label = LEVEL_LABELS[level]
    competencies = t["competencies"][level]
    if stage == "skills_domain":
        archetype_type = "technical"
        example_prefix = f"Walk me through how you would approach {competencies[0]} at the {level_label} level"
        weight_main = 0.5
        weight_motivational = 0.2
        weight_situational = 0.3
    else:
        archetype_type = "behavioral"
        example_prefix = f"Tell me about a time you demonstrated {competencies[0]} in a {label} role"
        weight_main = 0.4
        weight_motivational = 0.3
        weight_situational = 0.3
    question_archetypes = [
        {
            "type": archetype_type,
            "framework": t["frameworks"][0],
            "weight": weight_main,
            "example": f"{example_prefix}.",
        },
        {
            "type": "motivational",
            "framework": "open",
            "weight": weight_motivational,
            "example": f"Why do you want to be a {level_label} in {label}?",
        },
        {
            "type": "situational",
            "framework": t["frameworks"][1] if len(t["frameworks"]) > 1 else t["frameworks"][0],
            "weight": weight_situational,
            "example": f"How would you approach a conflict on your team as a {level_label}?",
        },
    ]
    return {
        "track": track,
        "level": level,
        "stage": stage,
        "core_competencies": competencies,
        "question_archetypes": question_archetypes,
        "evaluation_rubrics": RUBRICS,
        "answer_frameworks": t["frameworks"],
        "common_pitfalls": COMMON_PITFALLS,
        "red_flags": RED_FLAGS,
        "skill_dimensions": t["dimensions"],
    }


async def _seed_stage(db: AsyncSession, stage: str) -> None:
    for track in TRACKS:
        for level in LEVELS:
            existing = await db.execute(
                select(KnowledgeProfile).where(
                    KnowledgeProfile.track == track,
                    KnowledgeProfile.level == level,
                    KnowledgeProfile.stage == stage,
                )
            )
            if existing.scalar_one_or_none():
                continue
            profile_data = _build_profile(track, level, stage)
            db.add(KnowledgeProfile(
                id=str(uuid.uuid4()),
                track=track, level=level, stage=stage, profile=profile_data,
            ))
    await db.commit()


async def seed_knowledge_profiles(db: AsyncSession) -> None:
    await _seed_stage(db, "hr_interview")   # 50 profiles
    await _seed_stage(db, "skills_domain")  # 50 profiles
