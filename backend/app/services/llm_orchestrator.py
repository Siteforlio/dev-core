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
            parsed = json.loads(raw)
            return {**fallback, **parsed}
        except (json.JSONDecodeError, TypeError):
            match = re.search(r'\{.*\}', str(raw), re.DOTALL)
            try:
                parsed = json.loads(match.group()) if match else fallback
                return {**fallback, **parsed}
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
                f"{label}: {m.get('question', 'Unknown question')}\n"
                f"Answer: {m.get('answer', '')}{timing}{rewrites}{score_str}]"
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
        if rewrite_count < 1:
            return "Take your time."
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

    async def generate_skills_task(
        self,
        company: str,
        role: str,
        career_track: str,
        level: str,
        jd_text: str | None = None,
        graph_context: dict | None = None,
        knowledge_context: dict | None = None,
    ) -> dict:
        """Generate a hands-on skills task for a skills_task round."""
        TECH_TRACKS = {"technology", "data_science", "product", "design"}
        input_type = "code" if career_track in TECH_TRACKS else "text"

        context_parts = []
        if graph_context:
            context_parts.append(f"Company context: {json.dumps(graph_context)}")
        if knowledge_context:
            context_parts.append(f"Role knowledge: {json.dumps(knowledge_context)}")
        if jd_text:
            context_parts.append(f"Job description excerpt: {jd_text[:600]}")
        context_note = "\n".join(context_parts) or "Use general industry knowledge."

        tech_note = (
            'Set "language" to the primary programming language for the role (e.g. "python", "ruby", "javascript"). '
            'Set "starter_code" to a realistic but incomplete code snippet the candidate should complete/fix.'
            if input_type == "code"
            else 'Set "language" to null and "starter_code" to null.'
        )

        prompt = (
            f"You are a senior hiring manager at {company} designing a practical skills assessment for a {role} candidate "
            f"at {level} level in the {career_track} track.\n\n"
            f"{context_note}\n\n"
            "Design a realistic, hands-on task that directly tests day-to-day job skills — NOT trivia or quiz questions.\n"
            "The task must be completable in 60-90 minutes.\n\n"
            f"Input type: {input_type}. {tech_note}\n\n"
            "Return JSON only:\n"
            '{\n'
            '  "title": "Short task title",\n'
            '  "brief": "Clear, detailed task description (3-5 sentences). Tell the candidate exactly what to do.",\n'
            f'  "input_type": "{input_type}",\n'
            '  "language": null,\n'
            '  "starter_code": null,\n'
            '  "evaluation_criteria": ["criterion 1", "criterion 2", "criterion 3"],\n'
            '  "time_hint": "60 minutes"\n'
            '}'
        )
        raw = await self._call_llm(prompt)
        return self._parse_json(raw, {
            "title": "Skills Assessment",
            "brief": "Complete the assigned task demonstrating your core skills for this role.",
            "input_type": input_type,
            "language": None,
            "starter_code": None,
            "evaluation_criteria": ["correctness", "clarity", "completeness"],
            "time_hint": "60 minutes",
        })

    async def grade_skills_task(
        self,
        task_brief: dict,
        submission: str,
        career_track: str,
        role: str,
        level: str,
    ) -> dict:
        """Grade a skills_task Phase 1 submission and generate the first follow-up question."""
        criteria = "\n".join(f"- {c}" for c in task_brief.get("evaluation_criteria", []))
        prompt = (
            f"You are a senior evaluator at a top company grading a {role} ({level}) skills assessment.\n\n"
            f"Task: {task_brief.get('title', 'Skills Assessment')}\n"
            f"Brief: {task_brief.get('brief', '')}\n\n"
            f"Evaluation criteria:\n{criteria}\n\n"
            f"Candidate submission:\n{submission}\n\n"
            "Grade honestly using the scoring scale:\n"
            "- 9-10: Exceptional, production-ready\n"
            "- 7-8: Good, meets bar with minor gaps\n"
            "- 5-6: Mediocre, functional but has clear weaknesses\n"
            "- 3-4: Poor, significant issues\n"
            "- 1-2: Unacceptable\n\n"
            "Then generate the FIRST follow-up question to probe their understanding — "
            "ask them to explain a specific decision they made, or a weakness you noticed.\n\n"
            "Return JSON only:\n"
            '{"score": 6.5, "what_worked": "One sentence.", "what_was_missing": "One sentence.", '
            '"stronger_version": "One sentence.", "first_followup": "Specific probing question?", '
            '"factual_errors": [], "confidence_signal": "confident"}\n\n'
            "confidence_signal: confident | hesitant | uncertain | rushed"
        )
        raw = await self._call_llm(prompt)
        return self._parse_json(raw, {
            "score": 5.0,
            "what_worked": "",
            "what_was_missing": "Could not grade submission.",
            "stronger_version": "",
            "first_followup": "Can you walk me through the key decisions you made in your solution?",
            "factual_errors": [],
            "confidence_signal": "uncertain",
        })

    async def decide_followup(
        self,
        task_brief: dict,
        submission: str,
        conversation: list[dict],
        time_remaining_pct: float,
        career_track: str,
        evaluation_criteria: list[str],
    ) -> str | None:
        """Decide whether to ask another follow-up question or stop.

        Returns a follow-up question string, or None if the session should end.
        """
        if time_remaining_pct <= 0.10:
            return None

        transcript = "\n".join(
            f"{'Interviewer' if m.get('role') == 'interviewer' else 'Candidate'}: {m.get('content', '')}"
            for m in conversation
        )
        criteria_covered = "\n".join(f"- {c}" for c in evaluation_criteria)
        prompt = (
            f"You are evaluating a {career_track} candidate's skills task explanation.\n\n"
            f"Task: {task_brief.get('title', '')}\n"
            f"Brief: {task_brief.get('brief', '')}\n\n"
            f"Evaluation criteria you must cover:\n{criteria_covered}\n\n"
            f"Conversation so far:\n{transcript}\n\n"
            f"Time remaining: {int(time_remaining_pct * 100)}% of budget.\n\n"
            "Based on what has been discussed, decide:\n"
            "1. Are there important evaluation criteria still uncovered?\n"
            "2. Is there a specific weakness or vague answer worth probing deeper?\n"
            "3. Do you have enough signal to evaluate the candidate?\n\n"
            "If you should ask another follow-up, return a specific probing question as a plain string.\n"
            "If you have enough signal (all criteria covered, or candidate has shown consistent quality/weakness), "
            "return the JSON: {\"stop\": true}\n\n"
            "Return ONLY the question string OR the JSON — nothing else."
        )
        raw = await self._call_llm(prompt)
        raw = raw.strip().strip('"')
        # Detect stop signal
        if "stop" in raw.lower() and len(raw) < 50:
            try:
                parsed = json.loads(raw)
                if parsed.get("stop"):
                    return None
            except (json.JSONDecodeError, AttributeError):
                pass
        # If it looks like a question, return it
        if len(raw) > 10 and "?" in raw:
            return raw
        # Default: keep going if time remains
        if time_remaining_pct > 0.3:
            return "Can you tell me more about how you approached the most challenging part of this task?"
        return None

    async def coach_candidate(
        self,
        question: str,
        company: str,
        role: str,
        round_type: str,
        career_track: str,
        level: str,
        conversation_history: list[dict],
    ):
        """
        Async generator — streams coaching tokens for the in-session coach panel.

        On the first call (empty conversation_history) the coach decodes what the
        question is really testing and asks 1-2 prompts to surface the candidate's
        own stories.  On follow-up calls it answers the candidate's specific
        question concisely while keeping them focused on structure and their own
        experience.

        Yields str chunks as they arrive from DeepSeek V3.
        """
        system_prompt = (
            f"You are a private interview coach helping a candidate in real-time during "
            f"a {round_type} interview at {company} for a {role} position "
            f"({level}, {career_track} track).\n\n"
            "Your coaching rules:\n"
            "1. NEVER write the candidate's answer for them. They must use their own words and stories.\n"
            "2. Decode the question: explain in one sentence what the interviewer is really testing.\n"
            "3. Ask 1-2 short questions to help the candidate surface a relevant story from their own experience.\n"
            "4. If they ask you something specific, answer in 2-3 sentences max — stay grounded in THIS question and THIS company.\n"
            "5. If they're stuck, suggest a structure (STAR, problem/solution/impact) — don't fill it in.\n"
            "6. Be direct. Sound like a coach in a hallway, not a textbook.\n"
            "7. Max 4 sentences per response. No bullet lists unless the candidate explicitly asks for one.\n"
        )

        is_first_message = len(conversation_history) == 0
        if is_first_message:
            user_content = (
                f'The interviewer just asked: "{question}"\n\n'
                "Decode what they are really testing with this question, then ask me 1-2 questions "
                "to help me find a relevant story from my own experience."
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
        else:
            messages = [{"role": "system", "content": system_prompt}]
            # Inject question context as the first exchange if not already there
            messages.append({
                "role": "user",
                "content": f'We are working on this interview question: "{question}"',
            })
            messages.append({
                "role": "assistant",
                "content": "Got it, I'll help you work through this.",
            })
            messages.extend(conversation_history)

        stream = await self._client.chat.completions.create(
            model=self._model_fast,
            messages=messages,
            max_tokens=300,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def react_to_code(self, code_snapshot: str, question: str, company: str) -> str:
        prompt = (
            f"You are a technical interviewer at {company}.\n"
            f"The candidate is solving: {question}\n\nTheir current code:\n{code_snapshot}\n\n"
            "Give a brief (1-2 sentence) natural spoken reaction as an interviewer watching them code. "
            "Don't give away the answer. Be encouraging but probe for edge cases if appropriate."
        )
        return await self._call_llm(prompt)
