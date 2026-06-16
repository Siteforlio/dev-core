# backend/app/services/simulation_engine.py
import re
import json
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.pg.simulation import SimulationSession, SimulationTurn, SimulationDebrief
from app.models.pg.progress import UserProgress
from app.services.sim_llm_orchestrator import SimLLMOrchestrator
from app.core.cache import get_redis, SESSION_TTL
import logging

logger = logging.getLogger(__name__)

SCENARIO_TYPE_MAP = [
    (re.compile(r"pitch|elevator|verbal pitch", re.I),         "pitch"),
    (re.compile(r"mr review|merge request|code review", re.I), "mr_review"),
    (re.compile(r"system design|architecture", re.I),          "system_design"),
    (re.compile(r"teach|lesson|class|student", re.I),          "teaching"),
    (re.compile(r"behavioral|star|panel", re.I),               "behavioral"),
    (re.compile(r"pair[\s.]program|live cod", re.I),            "mr_review"),
    (re.compile(r"negotiat|sales", re.I),                      "negotiation"),
]

CAREER_TRACK_MAP = {
    "pitch": "sales_marketing",
    "mr_review": "technology",
    "system_design": "technology",
    "teaching": "education_training",
    "behavioral": "technology",
    "negotiation": "sales_marketing",
    "custom": "technology",
}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_time_budget(time_str: str) -> int | None:
    if not time_str:
        return None
    low = time_str.lower()
    if "open" in low or "no limit" in low or "unlimited" in low:
        return None
    m = re.search(r'(\d+)\s*(hour|hr)', low)
    if m:
        return int(m.group(1)) * 3600
    m = re.search(r'(\d+)\s*min', low)
    if m:
        return int(m.group(1)) * 60
    m = re.search(r'(\d+)\s*sec', low)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)', low)
    if m:
        return int(m.group(1)) * 60  # bare number → minutes
    return None


def _detect_scenario_type(brief: dict) -> str:
    format_val = _get_field(brief, "Format")
    for pattern, stype in SCENARIO_TYPE_MAP:
        if pattern.search(format_val):
            return stype
    return "custom"


def _get_field(brief: dict, name: str) -> str:
    """Read a field from brief.fields — supports both {label,value} and {k,v} shapes."""
    for f in brief.get("fields", []):
        if not isinstance(f, dict):
            continue
        key = f.get("label") or f.get("k") or ""
        if key.lower() == name.lower():
            return f.get("value") or f.get("v") or ""
    return ""


def _detect_level(brief: dict) -> str:
    plays = _get_field(brief, "I'll play").lower()
    if any(w in plays for w in ["junior", "entry", "intern", "graduate"]):
        return "entry_level"
    if any(w in plays for w in ["senior", "staff", "principal", "lead"]):
        return "senior"
    return "mid_level"


class SimulationEngine:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._orchestrator = SimLLMOrchestrator()

    async def create_session(self, user_id: str, brief: dict, attachments: list) -> dict:
        """Create session, pre-load attachments, build persona. Returns session dict."""
        time_field = _get_field(brief, "Time")
        time_budget = _parse_time_budget(time_field)
        scenario_type = _detect_scenario_type(brief)

        # Pre-analyze attachments
        attachment_analysis = self._preload_attachments(attachments)

        # Build AI persona
        persona = await self._orchestrator.build_sim_persona(brief)
        brief["_persona"] = persona  # embed for later prompts

        session = SimulationSession(
            id=str(uuid4()),
            user_id=user_id,
            scenario_type=scenario_type,
            brief=brief,
            attachments=attachments,
            time_budget_seconds=time_budget,
            persona=persona,
        )
        self._db.add(session)
        await self._db.commit()

        # Cache attachments under sim namespace
        r = await get_redis()
        try:
            await r.setex(f"sim:{session.id}:attachments", SESSION_TTL, json.dumps(attachment_analysis))
        except Exception as e:
            logger.warning("[sim_engine] Redis cache write failed for %s: %s", session.id, e)

        return {
            "session_id": session.id,
            "persona": persona,
            "time_budget_seconds": time_budget,
            "scenario_type": scenario_type,
            "started_at": session.started_at.isoformat(),
        }

    def _preload_attachments(self, attachments: list) -> str:
        """Read attachment content. Returns a string context block for the LLM."""
        if not attachments:
            return ""
        lines = []
        for att in attachments:
            name = att.get("name", "unnamed")
            kind = att.get("kind", "file")
            content = att.get("content_preview", "")
            lines.append(f"[{kind.upper()}] {name}:\n{content}\n")
        return "\n".join(lines)

    async def submit_turn(
        self,
        session_id: str,
        content: str,
        modality: str,
        time_offset_seconds: int,
        cached_turns: list[dict] | None = None,
    ) -> dict:
        """Process one user turn. Returns AI response dict.

        cached_turns: if provided, used directly as conversation history instead
        of querying the DB — avoids O(n) DB reads as the session grows.
        """
        result = await self._db.execute(
            select(SimulationSession).where(SimulationSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return {"error": "Session not found"}

        # Hard cutoff check
        elapsed = (utcnow() - session.started_at).total_seconds()
        if session.time_budget_seconds and elapsed >= session.time_budget_seconds:
            await self._db.execute(
                update(SimulationSession)
                .where(SimulationSession.id == session_id)
                .values(hard_cutoff_fired=True, ended_at=utcnow())
            )
            await self._db.commit()
            return {"cutoff": True, "response": "[HARD STOP]", "session_complete": True}

        if cached_turns is not None:
            turns = cached_turns
            seq = len(turns)
        else:
            # Fallback: query DB (e.g. after WS reconnect)
            turns_result = await self._db.execute(
                select(SimulationTurn)
                .where(SimulationTurn.session_id == session_id)
                .order_by(SimulationTurn.seq)
            )
            turns = [
                {"speaker": t.speaker, "content": t.content, "time_offset_seconds": t.time_offset_seconds}
                for t in turns_result.scalars().all()
            ]
            seq = len(turns)

        # Save user turn
        user_turn = SimulationTurn(
            session_id=session_id,
            seq=seq,
            speaker="user",
            modality=modality,
            content=content,
            time_offset_seconds=time_offset_seconds,
        )
        self._db.add(user_turn)
        await self._db.flush()

        # Get attachment context from Redis
        r = await get_redis()
        try:
            raw_att = await r.get(f"sim:{session_id}:attachments")
        except Exception as e:
            logger.warning("[sim_engine] Redis cache read failed for %s: %s", session_id, e)
            raw_att = None
        attachment_context = raw_att or ""

        # Compute time remaining
        time_remaining = None
        time_remaining_pct = 1.0
        if session.time_budget_seconds:
            remaining = session.time_budget_seconds - elapsed
            time_remaining = max(0, int(remaining))
            time_remaining_pct = max(0.0, remaining / session.time_budget_seconds)

        brief = session.brief or {}

        # Call LLM — catch RuntimeError from orchestrator's API error handling
        try:
            sim_response = await self._orchestrator.respond(
                brief=brief,
                turns=turns,
                user_content=content,
                attachment_context=attachment_context,
                time_remaining_pct=time_remaining_pct,
            )
        except RuntimeError as e:
            logger.error("[sim_engine] LLM error in submit_turn: %s", e)
            sim_response_text = "I'm having trouble responding right now. Please try again."
            from app.services.sim_llm_orchestrator import SimResponse
            sim_response = SimResponse(text=sim_response_text)

        tool_events = []
        if sim_response.tool_calls:
            for tc in sim_response.tool_calls:
                event = await self._execute_tool(tc)
                tool_events.append(event)
            tool_summary = "\n".join(
                f"[Tool {e['tool']}] {e.get('output', '')[:500]}" for e in tool_events
            )
            sim_response.text = f"{sim_response.text}\n\n{tool_summary}".strip()

        # Save AI turn
        ai_turn = SimulationTurn(
            session_id=session_id,
            seq=seq + 1,
            speaker="ai",
            modality="text",
            content=sim_response.text,
            time_offset_seconds=int(elapsed),
            tool_calls=[
                {"tool": tc.tool, "command": tc.command, "output": tc.output}
                for tc in (sim_response.tool_calls or [])
            ],
        )
        self._db.add(ai_turn)
        await self._db.commit()

        session_complete = sim_response.end_signal or (time_remaining == 0)

        return {
            "response": sim_response.text,
            "tool_events": tool_events,
            "time_remaining_seconds": time_remaining,
            "session_complete": session_complete,
            "cutoff": False,
        }

    async def _execute_tool(self, tc) -> dict:
        """Execute a tool call. Catches all exceptions — tool failure must not crash session."""
        try:
            if tc.tool == "terminal":
                from app.services.terminal_service import TerminalService
                svc = TerminalService()
                output = await asyncio.wait_for(svc.run(tc.command), timeout=15.0)
                return {"tool": "terminal", "command": tc.command, "output": str(output), "status": "done"}
            elif tc.tool == "code":
                from app.services.terminal_service import TerminalService
                svc = TerminalService()
                output = await asyncio.wait_for(svc.run(f'python -c "{tc.command}"'), timeout=10.0)
                return {"tool": "code", "command": tc.command, "output": str(output), "status": "done"}
            elif tc.tool == "file":
                try:
                    with open(tc.command, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read(4096)
                    return {"tool": "file", "command": tc.command, "output": content, "status": "done"}
                except OSError as e:
                    return {"tool": "file", "command": tc.command, "output": str(e), "status": "error"}
        except asyncio.TimeoutError:
            return {"tool": tc.tool, "command": tc.command, "output": "Timed out", "status": "error"}
        except Exception as e:
            return {"tool": tc.tool, "command": tc.command, "output": str(e), "status": "error"}
        return {"tool": tc.tool, "command": tc.command, "output": "unknown tool", "status": "error"}

    async def generate_debrief(self, session_id: str) -> dict:
        """Generate and persist debrief. Idempotent — returns cached if already done."""
        existing = await self._db.execute(
            select(SimulationDebrief).where(SimulationDebrief.session_id == session_id)
        )
        debrief = existing.scalar_one_or_none()
        if debrief:
            return self._debrief_to_dict(debrief)

        result = await self._db.execute(
            select(SimulationSession).where(SimulationSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return {"error": "Session not found"}

        turns_result = await self._db.execute(
            select(SimulationTurn)
            .where(SimulationTurn.session_id == session_id)
            .order_by(SimulationTurn.seq)
        )
        turns = [
            {"speaker": t.speaker, "content": t.content, "time_offset_seconds": t.time_offset_seconds}
            for t in turns_result.scalars().all()
        ]

        brief = session.brief or {}
        try:
            result_data = await self._orchestrator.debrief(brief, turns, think=True)
        except RuntimeError as e:
            logger.error("[sim_engine] LLM error in generate_debrief: %s", e)
            from app.services.sim_llm_orchestrator import DebriefResult
            result_data = DebriefResult(
                overall_score=5.0, hire_signal="borderline",
                core_scores={"communication": 5.0, "time_management": 5.0,
                             "pressure_handling": 5.0, "structure": 5.0, "depth": 5.0},
                scenario_scores={}, summary="Debrief generation failed.",
                strengths=[], improvements=[], focus_areas=[],
            )

        debrief = SimulationDebrief(
            id=str(uuid4()),
            session_id=session_id,
            scenario_type=session.scenario_type,
            overall_score=result_data.overall_score,
            hire_signal=result_data.hire_signal,
            core_scores=result_data.core_scores,
            scenario_scores=result_data.scenario_scores,
            summary=result_data.summary,
            strengths=result_data.strengths,
            improvements=result_data.improvements,
            focus_areas=result_data.focus_areas,
        )
        self._db.add(debrief)

        # Write UserProgress for core dimensions
        career_track = CAREER_TRACK_MAP.get(session.scenario_type or "custom", "technology")
        level = _detect_level(brief)
        for dimension, score in (result_data.core_scores or {}).items():
            progress = UserProgress(
                id=str(uuid4()),
                user_id=session.user_id,
                session_id=session_id,  # plain string — FK dropped in migration
                career_track=career_track,
                level=level,
                stage=session.scenario_type or "custom",
                skill_dimension=dimension,
                score=float(score),
            )
            self._db.add(progress)

        await self._db.commit()
        return self._debrief_to_dict(debrief)

    def _debrief_to_dict(self, d: SimulationDebrief) -> dict:
        return {
            "id": d.id,
            "session_id": d.session_id,
            "scenario_type": d.scenario_type,
            "overall_score": d.overall_score,
            "hire_signal": d.hire_signal,
            "core_scores": d.core_scores,
            "scenario_scores": d.scenario_scores,
            "summary": d.summary,
            "strengths": d.strengths or [],
            "improvements": d.improvements or [],
            "focus_areas": d.focus_areas or [],
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
