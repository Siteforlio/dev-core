# backend/app/services/llm_orchestrator.py
import json
import re
import openai
from app.core.config import settings


class LLMOrchestrator:
    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
        self._model_fast = "deepseek-chat"       # DeepSeek-V3
        self._model_think = "deepseek-reasoner"  # DeepSeek-R1

    async def _call_llm(self, prompt: str, think: bool = False) -> str:
        model = self._model_think if think else self._model_fast
        response = await self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return response.choices[0].message.content

    def _parse_json(self, raw: str, fallback: dict) -> dict:
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\{.*\}', str(raw), re.DOTALL)
            try:
                return json.loads(match.group()) if match else fallback
            except (json.JSONDecodeError, AttributeError):
                return fallback

    def _parse_list(self, raw: str, fallback: list) -> list:
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\[.*\]', str(raw), re.DOTALL)
            try:
                return json.loads(match.group()) if match else fallback
            except (json.JSONDecodeError, AttributeError):
                return fallback

    async def generate_questions(
        self,
        company: str,
        role: str,
        round_type: str,
        graph_context: dict | None,
        knowledge_context: dict | None = None,
    ) -> list[str]:
        context_note = (
            f"Known interview context: {json.dumps(graph_context)}"
            if graph_context
            else "Use your general knowledge about this company's interview style."
        )
        knowledge_note = (
            f"\nRole knowledge base: {json.dumps(knowledge_context)}"
            if knowledge_context
            else ""
        )
        prompt = (
            f"You are preparing interview questions for a {round_type} interview at {company} "
            f"for a {role} position.\n{context_note}{knowledge_note}\n\n"
            "Generate 5 interview questions appropriate for this round and seniority level. "
            'Return only a JSON array of question strings.\nExample: ["Question 1?", "Question 2?"]'
        )
        raw = await self._call_llm(prompt)
        return self._parse_list(raw, ["Tell me about yourself."])

    async def grade_answer(
        self,
        question: str,
        answer: str,
        company: str,
        role: str,
        round_type: str,
        time_taken_seconds: int | None = None,
        rewrite_count: int = 0,
    ) -> dict:
        # Timing note
        if time_taken_seconds is not None:
            if time_taken_seconds < 10:
                timing_note = f"Behavioral note: candidate answered suspiciously fast ({time_taken_seconds}s) — likely insufficient depth."
            elif time_taken_seconds > 180:
                timing_note = f"Behavioral note: candidate took significantly over time ({time_taken_seconds}s) — affects confidence assessment."
            elif time_taken_seconds > 120:
                timing_note = f"Behavioral note: slow response ({time_taken_seconds}s) — possible hesitation."
            else:
                timing_note = ""
        else:
            timing_note = ""

        # Rewrite note
        if rewrite_count == 1:
            rewrite_note = "Behavioral note: candidate rewrote their answer once — minor hesitation."
        elif rewrite_count >= 2:
            rewrite_note = f"Behavioral note: candidate rewrote their answer {rewrite_count} times — appears uncertain."
        else:
            rewrite_note = ""

        behavioral_context = "\n".join(filter(None, [timing_note, rewrite_note]))
        behavioral_section = f"\nBehavioral context:\n{behavioral_context}\n" if behavioral_context else ""

        prompt = (
            f"You are a senior interviewer at {company} evaluating a {role} candidate in a {round_type} interview.\n\n"
            "You are direct, fair, and brutally honest. You do not inflate scores to be encouraging.\n"
            "Scoring guide:\n"
            "- 9-10: Exceptional. Would hire immediately.\n"
            "- 7-8: Good. Meets bar for this role.\n"
            "- 5-6: Mediocre. Passes but has clear gaps.\n"
            "- 3-4: Poor. Significant gaps, weak structure, or factual errors.\n"
            "- 1-2: Unacceptable. Wrong facts, no structure, or completely off-topic.\n\n"
            "Factual accuracy: If the candidate states something demonstrably false, note it explicitly and lower the score.\n"
            f"{behavioral_section}\n"
            f"Question: {question}\n"
            f"Candidate answer: {answer}\n\n"
            "Return JSON only — no other text:\n"
            '{"score": 6.5, "what_worked": "One sentence.", "what_was_missing": "One sentence.", '
            '"stronger_version": "One sentence.", "follow_up": null, "factual_errors": [], '
            '"confidence_signal": "confident"}\n\n'
            "follow_up should be a specific probing question (string) if score < 7 AND there is a clear gap worth exploring, "
            "otherwise null. confidence_signal must be one of: confident, hesitant, uncertain, rushed."
        )
        raw = await self._call_llm(prompt)
        result = self._parse_json(raw, {
            "score": 5.0,
            "what_worked": "",
            "what_was_missing": "Could not grade answer.",
            "stronger_version": "",
            "follow_up": None,
            "factual_errors": [],
            "confidence_signal": "uncertain",
        })
        # Remove 'passed' if LLM included it — engine derives this
        result.pop("passed", None)
        return result

    async def evaluate_candidate(
        self,
        company: str,
        role: str,
        round_type: str,
        moments: list[dict],
        time_budget_seconds: int,
        actual_duration_seconds: int,
    ) -> dict:
        transcript_lines = []
        for i, m in enumerate(moments, 1):
            label = "Follow-up" if m.get("is_followup") else f"Q{i}"
            timing = f" [{m.get('time_taken_seconds', '?')}s"
            rewrites = f", rewrote {m['rewrite_count']}x" if m.get("rewrite_count", 0) > 0 else ""
            score_str = f", score {m.get('score', '?')}/10"
            transcript_lines.append(
                f"{label}: {m['question']}\n"
                f"Answer: {m['answer']}{timing}{rewrites}{score_str}]"
            )
        transcript = "\n\n".join(transcript_lines) or "No answers recorded."

        prompt = (
            f"You are the hiring manager at {company}. A candidate just completed "
            f"a {round_type} interview for {role}.\n\n"
            f"Full transcript with behavioral data:\n{transcript}\n\n"
            f"Time used: {actual_duration_seconds}s of {time_budget_seconds}s allowed.\n\n"
            "Evaluate the candidate holistically. Consider:\n"
            "- Answer quality and depth across all prepared questions\n"
            "- Follow-up performance (did they recover from weak initial answers?)\n"
            "- Consistency across the session\n"
            "- Confidence signals: response times, rewrites, hesitation\n"
            "- Factual accuracy\n"
            "- Whether you have enough signal to make a hire decision\n\n"
            "Be honest and direct. Do not hedge. A 'borderline' means you genuinely cannot decide.\n\n"
            "Return JSON only:\n"
            '{"hire_recommendation": "yes", "confidence_rating": "medium", "overall_score": 6.8, '
            '"summary": "Two honest sentences.", "strengths": [], "concerns": [], "time_management": "adequate"}\n\n'
            "hire_recommendation: strong_yes | yes | borderline | no | strong_no\n"
            "confidence_rating: high | medium | low | erratic\n"
            "time_management: efficient | adequate | slow | over_time"
        )
        raw = await self._call_llm(prompt, think=True)
        return self._parse_json(raw, {
            "hire_recommendation": "borderline",
            "confidence_rating": "low",
            "overall_score": 5.0,
            "summary": "Evaluation could not be completed.",
            "strengths": [],
            "concerns": [],
            "time_management": "adequate",
        })

    async def react_to_rewrite(self, company: str, role: str, rewrite_count: int) -> str:
        if rewrite_count == 1:
            situation = "is reconsidering their answer for the first time"
        else:
            situation = f"has rewritten their answer {rewrite_count} times"
        prompt = (
            f"You are an interviewer at {company} for a {role} role. "
            f"The candidate {situation}. "
            "Give a single natural spoken sentence reacting to this — be human and calm, "
            "neither dismissive nor over-encouraging. Do not give away anything about the question. "
            "Return only the sentence, no quotes."
        )
        return await self._call_llm(prompt)  # fast model (default)

    async def build_persona(self, company: str, role: str, manager_context: dict | None) -> str:
        context = json.dumps(manager_context) if manager_context else "No prior data available."
        prompt = (
            f"Build a concise interviewer persona for a hiring manager at {company} for the {role} role.\n"
            f"Known manager data: {context}\n"
            "Return a 2-3 sentence personality description the AI avatar should embody."
        )
        return await self._call_llm(prompt)

    async def react_to_code(self, code_snapshot: str, question: str, company: str) -> str:
        prompt = (
            f"You are a technical interviewer at {company}.\n"
            f"The candidate is solving: {question}\n\nTheir current code:\n{code_snapshot}\n\n"
            "Give a brief (1-2 sentence) natural spoken reaction as an interviewer watching them code. "
            "Don't give away the answer. Be encouraging but probe for edge cases if appropriate."
        )
        return await self._call_llm(prompt)
