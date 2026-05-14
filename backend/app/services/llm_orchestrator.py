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
    ) -> dict:
        prompt = (
            f"You are a {round_type} interviewer at {company} evaluating a candidate for {role}.\n\n"
            f"Question: {question}\nCandidate answer: {answer}\n\n"
            "Grade this answer on a scale of 1-10. A score >= 6 means passed.\n"
            "Return JSON only — no other text:\n"
            '{"score": 7.5, "passed": true, "what_worked": "One sentence.", '
            '"what_was_missing": "One sentence.", "stronger_version": "One sentence showing improvement."}'
        )
        raw = await self._call_llm(prompt)
        return self._parse_json(raw, {
            "score": 5.0, "passed": False,
            "what_worked": "", "what_was_missing": "Could not grade answer.",
            "stronger_version": ""
        })

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
