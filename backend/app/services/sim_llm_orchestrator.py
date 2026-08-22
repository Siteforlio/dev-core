# backend/app/services/sim_llm_orchestrator.py
import json
import re
import asyncio
import openai
from dataclasses import dataclass, field
from app.core.config import settings


@dataclass
class ToolCall:
    tool: str
    command: str
    output: str = ""
    duration_ms: int = 0


@dataclass
class SimResponse:
    text: str                          # spoken interviewer response
    tool_calls: list[ToolCall] = field(default_factory=list)
    end_signal: bool = False
    feedback: dict = field(default_factory=dict)  # private — sent to coach only, never shown


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
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            return response.choices[0].message.content or ""
        except openai.APIError as e:
            raise RuntimeError(f"LLM call failed: {e}") from e

    async def _call_stream(self, messages: list[dict], max_tokens: int = 1024):
        """Async generator yielding text chunks from streaming completion."""
        stream = await self._client.chat.completions.create(
            model=self._fast,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

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
        for f in brief.get("fields", []):
            if not isinstance(f, dict):
                continue
            key = f.get("label") or f.get("k") or ""
            if key.lower() == name.lower():
                return f.get("value") or f.get("v") or ""
        return ""

    @staticmethod
    def _flatten_summary(parts: list) -> str:
        out = []
        for p in parts:
            if isinstance(p, str):
                out.append(p)
            elif isinstance(p, dict):
                out.append(p.get("hl") or "")
        return "".join(out)

    async def build_sim_persona(self, brief: dict) -> str:
        role_playing = self._get_field(brief, "I'll play")
        pressure = self._get_field(brief, "Pressure")
        raw_summary = brief.get("summaryParts", ["a simulation"])
        summary = self._flatten_summary(raw_summary) if isinstance(raw_summary, list) else str(raw_summary)
        prompt = (
            f"You are about to play a character in a simulation. "
            f"Your character: {role_playing}. "
            f"Pressure level: {pressure}. "
            f"Context: {summary}\n\n"
            "Write a 2-3 sentence internal character note describing exactly how this character "
            "speaks, what they care about, and how they push back. Be concrete, no fluff. "
            "This is a private note — write as if briefing an actor."
        )
        return await self._call(prompt)

    async def opening_message(self, brief: dict, persona_note: str) -> str:
        scenario = self._get_field(brief, "Scenario")
        format_field = self._get_field(brief, "Format")
        role_playing = self._get_field(brief, "I'll play")
        prompt = (
            f"You are playing this character:\n{persona_note}\n\n"
            f"Scenario: {scenario}\n"
            f"Format: {format_field}\n"
            f"Your role: {role_playing}\n\n"
            "Open the simulation with a single in-character statement that sets the scene "
            "and immediately gives the candidate something to respond to. "
            "Do NOT introduce yourself at length — get right into it. "
            "Keep it under 4 sentences. No meta-commentary."
        )
        return await self._call(prompt)

    async def respond_stream(
        self,
        brief: dict,
        turns: list[dict],
        user_content: str,
        attachment_context: str,
        time_remaining_pct: float,
    ):
        """
        Async generator that streams the interviewer's spoken response token by token.

        Yields: str chunks for the spoken response.
        Final yield: a dict {"__feedback__": {...}} containing private evaluation data.

        Architecture:
        - Single LLM call returns JSON with two fields:
            "say": <interviewer's spoken words — streamed>
            "eval": <private feedback — returned at end>
        - Caller streams "say" to TTS immediately for low latency.
        - "eval" is stored and sent to coach only, never rendered on screen.
        """
        scenario = self._get_field(brief, "Scenario")
        format_field = self._get_field(brief, "Format")
        push_on = self._get_field(brief, "I'll push on")
        persona_note = brief.get("_persona", "")

        time_pressure = ""
        if time_remaining_pct < 0.10:
            time_pressure = "CRITICAL: Less than 10% time remains. Be very direct, cut if needed."
        elif time_remaining_pct < 0.20:
            time_pressure = "Time is running short. Be more pressing."

        # Build conversation history (last 20 turns)
        history_turns = turns[-20:] if len(turns) > 20 else turns
        history = "\n".join(
            f"[{t['speaker'].upper()}] {t['content']}"
            for t in history_turns
        )

        # Count user turns to track interview depth
        user_turns = [t for t in turns if t.get("speaker") == "user"]
        turn_number = len(user_turns) + 1

        tool_instruction = (
            'If you need to run code or read a file, include a tool call JSON on its own line '
            'inside "say": {"tool": "terminal", "command": "<cmd>"}. '
            if attachment_context else ""
        )

        system_prompt = f"""You are playing this interviewer character:
{persona_note}

Scenario: {scenario}
Format: {format_field}
Push on: {push_on}
{time_pressure}

INTERVIEW INTELLIGENCE RULES (follow these strictly):
1. VAGUE ANSWERS: If the candidate's answer lacks specifics, concrete examples, or measurable outcomes — probe deeper. Ask "Can you give me a specific example?" or "What was the actual outcome?"
2. OFF-TOPIC DRIFT: If the candidate starts talking about something unrelated to the scenario/question — redirect them immediately. Say something like "That's interesting, but let's stay focused on [topic]."
3. INCONSISTENCY: If the candidate contradicts something they said earlier in this conversation — call it out naturally. "Earlier you mentioned X, but now you're saying Y — help me understand."
4. INCOMPLETE ANSWERS: If they only answered part of a multi-part question — explicitly ask about the missing part.
5. STRONG ANSWERS: If the answer is clear, specific, and complete — acknowledge briefly and move the interview forward naturally.
6. FOLLOW-UP DEPTH: Push for 2-3 layers of depth on important topics before moving on. Real interviewers do this.

{tool_instruction}

Conversation so far:
{history}

[CANDIDATE - Turn {turn_number}]: {user_content}

Attachments: {attachment_context or "None."}"""

        user_prompt = """Respond with ONLY this JSON (no other text):
{
  "say": "<your in-character spoken response — what you actually say out loud>",
  "end_session": false,
  "eval": {
    "answer_quality": "<strong|adequate|vague|incomplete|off_topic|inconsistent>",
    "score": <0-10 float for this specific answer>,
    "what_worked": "<one sentence — what was good, or empty string>",
    "gap": "<one sentence — what was missing or wrong, or empty string>",
    "follow_up_needed": <true|false>,
    "topic_drift": <true|false>,
    "inconsistency": <true|false>
  }
}

Rules for "say":
- Stay in character. No meta-commentary.
- One focused response. No rambling.
- If the simulation is naturally complete, set end_session to true and give a closing line.
- Include END_SESSION as a word in "say" only if end_session is true."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Collect full response for JSON parsing
        full_response = ""
        async for chunk in self._call_stream(messages, max_tokens=1024):
            full_response += chunk

        # Parse JSON response
        parsed = self._parse_json(full_response, {
            "say": full_response,  # fallback: treat whole response as spoken text
            "end_session": False,
            "eval": {},
        })

        say_text = parsed.get("say", "").strip()
        end_signal = bool(parsed.get("end_session", False)) or bool(re.search(r'\bEND_SESSION\b', say_text))
        say_text = re.sub(r'\s*\bEND_SESSION\b\s*', '', say_text).strip()

        # Extract tool calls from say_text
        tool_calls: list[ToolCall] = []
        clean_lines = []
        for line in say_text.splitlines():
            stripped = line.strip()
            if stripped.startswith('{"tool":'):
                try:
                    obj = json.loads(stripped)
                    if "tool" in obj and "command" in obj:
                        tool_calls.append(ToolCall(tool=obj["tool"], command=obj["command"]))
                        continue
                except json.JSONDecodeError:
                    pass
            clean_lines.append(line)
        say_text = "\n".join(clean_lines).strip()

        # Yield the spoken text and feedback
        yield say_text
        yield {"__tool_calls__": [{"tool": tc.tool, "command": tc.command} for tc in tool_calls]}
        yield {"__feedback__": parsed.get("eval", {}), "__end__": end_signal}

    async def respond(
        self,
        brief: dict,
        turns: list[dict],
        user_content: str,
        attachment_context: str,
        time_remaining_pct: float,
    ) -> SimResponse:
        """Non-streaming wrapper — collects full response. Used as fallback."""
        say_text = ""
        feedback = {}
        end_signal = False
        tool_calls = []

        async for item in self.respond_stream(brief, turns, user_content, attachment_context, time_remaining_pct):
            if isinstance(item, str):
                say_text = item
            elif isinstance(item, dict):
                if "__feedback__" in item:
                    feedback = item["__feedback__"]
                    end_signal = item.get("__end__", False)
                elif "__tool_calls__" in item:
                    tool_calls = [ToolCall(tool=t["tool"], command=t["command"]) for t in item["__tool_calls__"]]

        return SimResponse(text=say_text, tool_calls=tool_calls, end_signal=end_signal, feedback=feedback)

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

Return ONLY valid JSON:
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
    "<dimension>": <0-10>
  }},
  "summary": "<2-3 sentence honest summary>",
  "strengths": ["<specific>"],
  "improvements": ["<specific>"],
  "focus_areas": ["<top>", "<second>", "<third>"]
}}"""

        raw = await self._call(prompt, think=think)
        data = self._parse_json(raw, fallback)
        return DebriefResult(
            overall_score=max(0.0, min(10.0, float(data.get("overall_score", 5.0)))),
            hire_signal=data.get("hire_signal", "borderline"),
            core_scores=data.get("core_scores", fallback["core_scores"]),
            scenario_scores=data.get("scenario_scores", {}),
            summary=data.get("summary", ""),
            strengths=data.get("strengths", []),
            improvements=data.get("improvements", []),
            focus_areas=data.get("focus_areas", []),
        )
