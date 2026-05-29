# backend/app/services/sim_llm_orchestrator.py
import json
import re
import openai
from dataclasses import dataclass, field
from app.core.config import settings


@dataclass
class ToolCall:
    tool: str           # "terminal" | "code" | "file"
    command: str
    output: str = ""
    duration_ms: int = 0


@dataclass
class SimResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    end_signal: bool = False


@dataclass
class DebriefResult:
    overall_score: float
    hire_signal: str
    core_scores: dict
    scenario_scores: dict
    summary: str
    strengths: list
    improvements: list
    focus_areas: list


class SimLLMOrchestrator:
    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self._fast = "deepseek-chat"
        self._think = "deepseek-reasoner"

    async def _call(self, prompt: str, think: bool = False) -> str:
        model = self._think if think else self._fast
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    def _parse_json(self, raw: str, fallback: dict) -> dict:
        if isinstance(raw, dict):
            return raw
        try:
            return {**fallback, **json.loads(raw)}
        except (json.JSONDecodeError, TypeError):
            m = re.search(r'\{.*\}', str(raw), re.DOTALL)
            try:
                return {**fallback, **json.loads(m.group())} if m else fallback
            except (json.JSONDecodeError, AttributeError):
                return fallback

    def _get_field(self, brief: dict, name: str) -> str:
        """Extract a field value from brief.fields list by label."""
        for f in brief.get("fields", []):
            if isinstance(f, dict) and f.get("label", "").lower() == name.lower():
                return f.get("value", "")
        return ""

    async def build_sim_persona(self, brief: dict) -> str:
        role_playing = self._get_field(brief, "I'll play")
        pressure = self._get_field(brief, "Pressure")
        summary = brief.get("summaryParts", ["a simulation"])
        prompt = (
            f"You are about to play a character in a simulation. "
            f"Your character: {role_playing}. "
            f"Pressure level: {pressure}. "
            f"Context: {' '.join(summary) if isinstance(summary, list) else summary}\n\n"
            "Write a 2-3 sentence internal character note describing exactly how this character "
            "speaks, what they care about, and how they push back. Be concrete, no fluff. "
            "This is a private note — write as if briefing an actor."
        )
        return await self._call(prompt)

    async def respond(
        self,
        brief: dict,
        turns: list[dict],
        user_content: str,
        attachment_context: str,
        time_remaining_pct: float,
    ) -> SimResponse:
        scenario = self._get_field(brief, "Scenario")
        format_field = self._get_field(brief, "Format")
        push_on = self._get_field(brief, "I'll push on")
        persona_note = brief.get("_persona", "")

        time_pressure = ""
        if time_remaining_pct < 0.10:
            time_pressure = "CRITICAL: Less than 10% of time remains. You may cut off mid-sentence if needed. Be very direct."
        elif time_remaining_pct < 0.20:
            time_pressure = "Time is running short. Be more pressing and direct."

        history = "\n".join(
            f"[{t['speaker'].upper()}] {t['content']}"
            for t in (turns[-20:] if len(turns) > 20 else turns)
        )

        tool_instruction = (
            'If you need to run code or read a file, reply with JSON in this exact format: '
            '{"tool": "terminal", "command": "<shell command>"} — on its own line before your spoken response. '
            'For file reads: {"tool": "file", "command": "<path>"}. '
            'For code execution: {"tool": "code", "command": "<python code>"}. '
            'You may only use a tool if the attachment context shows files or code are available.'
            if attachment_context else
            ""
        )

        prompt = f"""You are playing this character:
{persona_note}

Scenario: {scenario}
Format: {format_field}
Push on: {push_on}
{time_pressure}

Attached context (pre-analyzed — you know this already, simulate discovering it live):
{attachment_context or "No attachments."}

Conversation so far:
{history}

[USER]: {user_content}

{tool_instruction}

Respond as your character now. Stay in role. One focused response — no rambling.
If the simulation is naturally complete (e.g. Q&A period ended, session goal achieved),
add a final line: END_SESSION"""

        raw = await self._call(prompt)

        # Detect tool call
        tool_calls: list[ToolCall] = []
        tool_match = re.search(r'\{"tool":\s*"([^"]+)",\s*"command":\s*"([^"]+)"\}', raw)
        if tool_match:
            tool_calls.append(ToolCall(tool=tool_match.group(1), command=tool_match.group(2)))
            raw = raw[:tool_match.start()].strip() + raw[tool_match.end():].strip()

        end_signal = "END_SESSION" in raw
        text = raw.replace("END_SESSION", "").strip()

        return SimResponse(text=text, tool_calls=tool_calls, end_signal=end_signal)

    async def debrief(self, brief: dict, turns: list[dict], think: bool = True) -> DebriefResult:
        scenario = self._get_field(brief, "Scenario")
        format_field = self._get_field(brief, "Format")
        transcript = "\n".join(
            f"[{t['speaker'].upper()} t={t.get('time_offset_seconds', 0)}s] {t['content']}"
            for t in turns
        )

        fallback = {
            "overall_score": 5.0,
            "hire_signal": "borderline",
            "core_scores": {
                "communication": 5.0, "time_management": 5.0,
                "pressure_handling": 5.0, "structure": 5.0, "depth": 5.0,
            },
            "scenario_scores": {},
            "summary": "Unable to generate debrief.",
            "strengths": [],
            "improvements": [],
            "focus_areas": [],
        }

        prompt = f"""You are an expert evaluator. Analyze this simulation transcript and return structured JSON feedback.

Scenario: {scenario}
Format: {format_field}

Transcript:
{transcript}

Return ONLY valid JSON with this exact structure:
{{
  "overall_score": <float 0-10>,
  "hire_signal": "<strong_yes|yes|borderline|no|strong_no>",
  "core_scores": {{
    "communication": <0-10>,
    "time_management": <0-10>,
    "pressure_handling": <0-10>,
    "structure": <0-10>,
    "depth": <0-10>
  }},
  "scenario_scores": {{
    "<dimension_name>": <0-10>,
    ...  (2-4 dimensions specific to THIS scenario format, you decide what matters)
  }},
  "summary": "<2-3 sentence honest summary>",
  "strengths": ["<specific strength>", ...],
  "improvements": ["<specific improvement>", ...],
  "focus_areas": ["<top focus>", "<second>", "<third>"]
}}"""

        raw = await self._call(prompt, think=think)
        data = self._parse_json(raw, fallback)
        return DebriefResult(
            overall_score=float(data.get("overall_score", 5.0)),
            hire_signal=data.get("hire_signal", "borderline"),
            core_scores=data.get("core_scores", fallback["core_scores"]),
            scenario_scores=data.get("scenario_scores", {}),
            summary=data.get("summary", ""),
            strengths=data.get("strengths", []),
            improvements=data.get("improvements", []),
            focus_areas=data.get("focus_areas", []),
        )
