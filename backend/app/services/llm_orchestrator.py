import json
import re
import anthropic
from app.core.config import settings


class LLMOrchestrator:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _call_claude(self, prompt: str):
        message = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    async def generate_questions(
        self,
        company: str,
        role: str,
        round_type: str,
        graph_context: dict | None,
    ) -> list[str]:
        if not graph_context:
            context_note = "Use your general knowledge about this company's interview style."
        else:
            context_note = f"Known interview context: {json.dumps(graph_context)}"

        prompt = (
            f"You are preparing interview questions for a {round_type} interview at {company} "
            f"for a {role} position.\n{context_note}\n\n"
            "Generate 5 interview questions appropriate for this round. "
            'Return only a JSON array of question strings.\nExample: ["Question 1?", "Question 2?"]'
        )

        raw = await self._call_claude(prompt)
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\[.*?\]', str(raw), re.DOTALL)
            return json.loads(match.group()) if match else ["Tell me about yourself."]

    async def grade_answer(
        self,
        question: str,
        answer: str,
        company: str,
        role: str,
        round_type: str,
    ) -> dict:
        prompt = (
            f"You are a {round_type} interviewer at {company} evaluating a candidate for {role}.\n\n"
            f"Question: {question}\nCandidate answer: {answer}\n\n"
            "Grade this answer on a scale of 1-10. A score >= 6 means passed. Return JSON only:\n"
            '{"score": 7.5, "passed": true, "feedback": "Brief actionable feedback."}'
        )

        raw = await self._call_claude(prompt)
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\{.*?\}', str(raw), re.DOTALL)
            return json.loads(match.group()) if match else {
                "score": 5.0, "passed": False, "feedback": "Could not grade answer."
            }

    async def build_persona(self, company: str, role: str, manager_context: dict | None) -> str:
        context = json.dumps(manager_context) if manager_context else "No prior data available."
        prompt = (
            f"Build a concise interviewer persona for a hiring manager at {company} for the {role} role.\n"
            f"Known manager data: {context}\n"
            "Return a 2-3 sentence personality description the AI avatar should embody."
        )
        return await self._call_claude(prompt)
