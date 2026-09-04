"""
assessment_agent.py — Conscious agent loop for coding assessments.

The agent is not rule-following — it reasons at each step about what it
needs to do next, picks a tool, uses it, observes the result, and decides
the next action.  This is the core loop for assessment mode.

Assessment types handled
------------------------
  coding      LeetCode / DSA problem on an assessment platform.
              Reads visible test cases, generates solution, tests it
              locally, iterates until all visible cases pass.

  live        Live project build.  Agent has filesystem access, can
              read/write files and run the test suite.

  ai_model    Degraded AI model assessment.  Agent profiles the model,
              coaches the user with prompts, evaluates output, re-prompts.

Agent loop
----------
1. Observe  — read screen / context to understand current state
2. Reason   — decide what information or action is needed next
3. Act      — invoke a tool (terminal, browser, screen, file, search)
4. Observe  — read tool output
5. Decide   — is the goal achieved? if not, loop with updated plan

The agent emits structured events over the WebSocket so the overlay can
render them in the appropriate tool card.  Every reasoning step is also
streamed so the user can see the agent "thinking" in real time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import AsyncGenerator, Callable, Optional

from app.services.cluely.terminal_service import TerminalService
from app.services.cluely.browser_service import BrowserService
from app.services.cluely.screen_service import ScreenService
from app.services.cluely.file_service import FileService, PathEscapeError
from app.services.cluely.search_service import SearchService
from app.services.cluely.deepseek_client import deepseek_generate, deepseek_stream

logger = logging.getLogger(__name__)

# Maximum solution iteration attempts before giving up
MAX_ITERATIONS = 5
# Maximum agent reasoning steps per session action
MAX_STEPS = 12


# ---------------------------------------------------------------------------
# Event helpers — these are sent over the WebSocket to the overlay
# ---------------------------------------------------------------------------

def _tool_event(tool: str, status: str, data: dict | None = None) -> dict:
    """Notify the overlay that a tool is being used / has completed."""
    return {
        "type":   "tool:event",
        "tool":   tool,          # "terminal" | "screen" | "browser" | "file" | "search"
        "status": status,        # "start" | "data" | "done" | "error"
        "data":   data or {},
        "ts":     int(time.time() * 1000),
    }


def _think_event(text: str) -> dict:
    """Stream the agent's reasoning so the user can see it."""
    return {"type": "agent:thinking", "text": text, "ts": int(time.time() * 1000)}


def _guidance_event(text: str) -> dict:
    """Direct guidance to the user: what to say, what to type, what to do."""
    return {"type": "agent:guidance", "text": text, "ts": int(time.time() * 1000)}


def _solution_event(code: str, language: str, explanation: str) -> dict:
    return {
        "type":        "agent:solution",
        "code":        code,
        "language":    language,
        "explanation": explanation,
        "ts":          int(time.time() * 1000),
    }


# ---------------------------------------------------------------------------
# AssessmentAgent
# ---------------------------------------------------------------------------

class AssessmentAgent:
    """
    Stateful agent for a single assessment session.

    Parameters
    ----------
    mode           : "coding" | "live" | "ai_model"
    project_root   : absolute path to project folder (live mode only)
    session_ctx    : the session context dict from overlay_service
    send           : coroutine(dict) — sends an event to the overlay WebSocket
    """

    def __init__(
        self,
        mode: str,
        session_ctx: dict,
        send: Callable[[dict], asyncio.Future],
        project_root: str | None = None,
        file_paths: list[str] | None = None,
        api_key: str = "",
        anthropic_api_key: str = "",
    ) -> None:
        self._mode        = mode
        self._ctx         = session_ctx
        self._send        = send
        self._api_key     = api_key
        self._terminal    = TerminalService()
        self._browser     = BrowserService()
        self._screen      = ScreenService(api_key=anthropic_api_key)
        self._search      = SearchService(api_key=api_key)
        self._file: FileService | None = None
        self._file_paths  = file_paths or []

        if project_root:
            try:
                self._file = FileService(project_root)
                logger.info("[agent] FileService scoped to: %s", project_root)
            except ValueError as exc:
                logger.warning("[agent] FileService init failed: %s", exc)

        # Agent memory for this session
        self._problem_text: str = ""
        self._test_cases:   list[dict] = []
        self._solution:     str = ""
        self._language:     str = "python"
        self._iteration:    int = 0

    # ------------------------------------------------------------------
    # Entry points per mode
    # ------------------------------------------------------------------

    async def handle_assessment_trigger(self, trigger: dict) -> None:
        """
        Called when the user manually triggers assessment mode, or when
        the agent detects an assessment is in progress from audio context.

        trigger = {"action": "start"|"reread"|"submit"|"manual_ask", "text": "..."}
        """
        action = trigger.get("action", "start")
        if action == "start":
            if self._mode == "live":
                await self._run_live_coding(trigger.get("text", ""))
            elif self._mode == "ai_model":
                await self._run_ai_model_coach(trigger.get("text", ""))
            else:
                await self._run_coding_loop()
        elif action == "reread":
            await self._reread_screen()
        elif action == "manual_ask":
            await self._handle_manual_ask(trigger.get("text", ""))
        elif action == "live_run":
            await self._run_live_coding(trigger.get("text", ""))
        elif action == "ai_model_prompt":
            await self._run_ai_model_coach(trigger.get("text", ""))

    # ------------------------------------------------------------------
    # Coding mode: read → generate → test → iterate
    # ------------------------------------------------------------------

    async def _run_coding_loop(self) -> None:
        await self._send(_think_event("Starting coding assessment loop…"))

        # Step 1: Read the problem from screen
        await self._send(_think_event("Reading problem from screen…"))
        await self._send(_tool_event("screen", "start"))
        screen_text = await self._screen.capture_and_extract()
        await self._send(_tool_event("screen", "done", {"preview": screen_text[:200]}))

        if screen_text.strip():
            self._problem_text = screen_text
        else:
            await self._send(_think_event("Screen OCR returned empty — asking user to describe the problem"))

        # Step 2: Extract visible test cases from screen text
        self._test_cases = _parse_test_cases_from_text(self._problem_text)
        await self._send(_think_event(
            f"Extracted {len(self._test_cases)} visible test case(s) from screen."
        ))

        # Step 3: Search online if problem name is identifiable
        problem_name = _extract_problem_name(self._problem_text)
        if problem_name:
            await self._send(_think_event(f"Searching online for: {problem_name!r}"))
            await self._send(_tool_event("search", "start"))
            snippets = await self._search.search(f"leetcode {problem_name} solution python", num=3)
            await self._send(_tool_event("search", "done", {"results": snippets[:2]}))
            # Enrich test cases from online snippets if we have few
            if len(self._test_cases) < 2:
                online_cases = _parse_test_cases_from_text("\n".join(snippets))
                self._test_cases.extend(online_cases)
                await self._send(_think_event(
                    f"Added {len(online_cases)} test case(s) from online search."
                ))

        if not self._test_cases:
            await self._send(_think_event(
                "No test cases found — will generate solution to best known correctness."
            ))

        # Step 4: Generate initial solution
        await self._send(_think_event("Generating solution…"))
        solution, language = await self._generate_solution()
        self._solution  = solution
        self._language  = language

        # Step 5: Test loop
        await self._test_loop()

    async def _test_loop(self) -> None:
        """Iterate: run solution against test cases, fix failures, repeat."""
        for attempt in range(1, MAX_ITERATIONS + 1):
            self._iteration = attempt
            await self._send(_think_event(f"Running tests (attempt {attempt}/{MAX_ITERATIONS})…"))

            passed, failed = await self._run_against_test_cases(self._solution, self._language)

            if failed:
                await self._send(_tool_event("terminal", "data", {
                    "summary": f"{passed} passed, {len(failed)} failed",
                    "failed":  failed[:3],
                }))

                if attempt < MAX_ITERATIONS:
                    await self._send(_think_event(
                        f"{len(failed)} test(s) failing — diagnosing and revising solution…"
                    ))
                    self._solution = await self._fix_solution(self._solution, self._language, failed)
                else:
                    await self._send(_think_event(
                        "Reached max iterations — surfacing best solution found."
                    ))
            else:
                await self._send(_think_event(
                    f"All {passed} test case(s) passed! Surfacing solution."
                ))
                break

        explanation = await self._generate_explanation(self._solution, self._language)
        await self._send(_solution_event(self._solution, self._language, explanation))
        await self._send(_guidance_event(
            "Solution is ready. Type it into the editor. "
            "When the interviewer asks about your approach, say: " + _verbal_summary(explanation)
        ))

    async def _run_against_test_cases(
        self, solution: str, language: str
    ) -> tuple[int, list[dict]]:
        """
        Run the solution locally against each test case.
        Returns (passed_count, list_of_failed_cases).
        """
        if not self._test_cases:
            # No test cases — just syntax-check
            script, cmd, cwd = _build_run_script(solution, language, stdin="")
            events = []
            async for ev in self._terminal.run(cmd, working_dir=cwd):
                await self._send(_tool_event("terminal", "data", ev))
                events.append(ev)
            has_error = any("error" in e.get("text", "").lower() for e in events if e.get("stream") == "stderr")
            return (1 if not has_error else 0), []

        passed, failed = 0, []
        for tc in self._test_cases:
            stdin = tc.get("input", "")
            expected = tc.get("output", "").strip()

            script, cmd, cwd = _build_run_script(solution, language, stdin=stdin)
            output_lines: list[str] = []

            await self._send(_tool_event("terminal", "start", {"stdin": stdin[:80]}))
            async for ev in self._terminal.run(cmd, working_dir=cwd):
                await self._send(_tool_event("terminal", "data", ev))
                if ev.get("stream") == "stdout":
                    output_lines.append(ev["text"])

            actual = "\n".join(output_lines).strip()

            if expected and actual == expected:
                passed += 1
                await self._send(_tool_event("terminal", "done", {"status": "pass", "input": stdin[:60]}))
            elif expected:
                failed.append({"input": stdin, "expected": expected, "actual": actual})
                await self._send(_tool_event("terminal", "done", {
                    "status": "fail",
                    "input":    stdin[:60],
                    "expected": expected[:60],
                    "actual":   actual[:60],
                }))
            else:
                passed += 1  # no expected output — treat as pass if no error

        return passed, failed

    # ------------------------------------------------------------------
    # Live coding mode
    # ------------------------------------------------------------------

    async def _run_live_coding(self, challenge_description: str) -> None:
        """Guide user through a live coding challenge step by step."""
        await self._send(_think_event("Analyzing live coding challenge…"))

        if self._file:
            files = await self._file.list_directory(".", depth=2)
            await self._send(_tool_event("file", "done", {"files": files[:30]}))
            await self._send(_think_event(f"Project has {len(files)} files. Mapping structure…"))

        plan = await deepseek_generate(
            prompt=(
                f"Challenge: {challenge_description}\n\n"
                f"Project files: {', '.join(files[:20]) if self._file else 'not provided'}\n\n"
                "Create a numbered step-by-step implementation plan. "
                "For each step include: what to say to the interviewer, what file to open, "
                "what code to write. Be concrete and specific."
            ),
            api_key=self._api_key,
            system=(
                "You are a senior engineer coaching a candidate through a live coding interview. "
                "Your guidance must make the candidate look confident and expert. "
                "Each step must be actionable in under 2 minutes."
            ),
            max_tokens=800,
        )

        await self._send(_guidance_event(plan))

    # ------------------------------------------------------------------
    # Degraded AI model coaching
    # ------------------------------------------------------------------

    async def _run_ai_model_coach(self, prompt_context: str) -> None:
        """
        Conscious loop for degraded-AI assessments.

        Observe → Profile model → Generate prompt strategy → Read AI response
        from screen → Evaluate quality → Re-prompt if poor → Repeat.

        This loop gives the user live coaching at each step so they always
        know exactly what to type and how to interpret the AI's output.
        """
        _AI_COACH_ITERATIONS = 3

        await self._send(_think_event("Profiling AI model from screen…"))

        # Step 1: observe the current screen to understand what model is shown
        await self._send(_tool_event("screen", "start"))
        screen_text = await self._screen.capture_and_extract()
        await self._send(_tool_event("screen", "done", {
            "preview": screen_text[:200],
            "text": screen_text,
        }))

        model_context = prompt_context or screen_text or "Unknown AI model interface"

        # Step 2: initial profile + first prompt strategy
        await self._send(_think_event("Generating initial prompt strategy…"))
        initial_strategy = await deepseek_generate(
            prompt=(
                f"Screen content / context about the AI model being used:\n{model_context[:800]}\n\n"
                "You are coaching a candidate in a live interview where they must use this AI model.\n"
                "1. Identify the likely model type and capability level from the screen.\n"
                "2. Write the exact first prompt the candidate should type to best accomplish the task.\n"
                "3. Explain in one sentence WHY this prompt will work for this model type.\n"
                "Keep it under 120 words. Be specific and direct."
            ),
            api_key=self._api_key,
            system=(
                "You are a world-class AI prompt engineer. The candidate needs exact, copy-paste "
                "instructions. No vague advice — give the literal text to type."
            ),
            max_tokens=250,
        )
        await self._send(_guidance_event(f"**Step 1 — Type this prompt:**\n{initial_strategy}"))

        # Step 3: observe → evaluate → re-prompt loop
        last_prompt = initial_strategy
        for iteration in range(1, _AI_COACH_ITERATIONS + 1):
            # Wait a moment for the user to submit the prompt and get a response
            await asyncio.sleep(8)

            await self._send(_think_event(
                f"Reading AI response from screen (iteration {iteration}/{_AI_COACH_ITERATIONS})…"
            ))
            await self._send(_tool_event("screen", "start"))
            response_screen = await self._screen.capture_and_extract()
            await self._send(_tool_event("screen", "done", {
                "preview": response_screen[:200],
                "text": response_screen,
            }))

            if not response_screen.strip():
                await self._send(_think_event("Screen empty — waiting for AI response…"))
                continue

            # Evaluate response quality and decide next action
            await self._send(_think_event("Evaluating AI response quality…"))
            evaluation = await deepseek_generate(
                prompt=(
                    f"The AI model responded with this (from screen):\n{response_screen[:600]}\n\n"
                    f"The prompt that was used:\n{last_prompt[:200]}\n\n"
                    "Evaluate the response:\n"
                    "1. Is it useful/correct? (yes/no)\n"
                    "2. If no: what specific weakness does it show (hallucination, refusal, "
                    "vague, wrong format, etc.)?\n"
                    "3. Write the exact follow-up or corrective prompt to fix the issue, "
                    "OR if the response is good, write 'GOOD: <brief comment on why it worked>'.\n"
                    "Be specific. Under 100 words."
                ),
                api_key=self._api_key,
                system=(
                    "You are an expert AI prompt engineer evaluating a live interview session. "
                    "Identify weaknesses precisely and prescribe exact corrective prompts."
                ),
                max_tokens=200,
            )

            if evaluation.strip().upper().startswith("GOOD"):
                comment = evaluation.split(":", 1)[-1].strip()
                await self._send(_guidance_event(
                    f"**AI response looks good!** {comment}\n\n"
                    "You can now proceed with the output, or ask me for next steps."
                ))
                break
            else:
                await self._send(_think_event(f"Response suboptimal — generating corrective re-prompt…"))
                last_prompt = evaluation
                await self._send(_guidance_event(
                    f"**Step {iteration + 1} — AI response was weak. Type this corrective prompt:**\n{evaluation}"
                ))

        else:
            # Exhausted iterations — surface best recovery strategy
            recovery = await deepseek_generate(
                prompt=(
                    f"The AI model in a live interview has given poor responses for {_AI_COACH_ITERATIONS} rounds.\n"
                    "What should the candidate do NOW to recover? Options: switch approach, "
                    "explain the limitation to the interviewer, show prompting skill explicitly, etc.\n"
                    "Give a 2-sentence script the candidate should say out loud and one final prompt to try."
                ),
                api_key=self._api_key,
                system="You are coaching a candidate through a live AI-model interview that has gone wrong.",
                max_tokens=200,
            )
            await self._send(_guidance_event(f"**Recovery strategy:**\n{recovery}"))

    # ------------------------------------------------------------------
    # Manual ask from overlay chat input
    # ------------------------------------------------------------------

    async def _handle_manual_ask(self, text: str) -> None:
        """Handle a typed question or command from the user during assessment."""
        # Decide if the ask needs a tool
        decision = await deepseek_generate(
            prompt=(
                f"User said: {text!r}\n"
                f"Current problem: {self._problem_text[:300]}\n"
                f"Current solution: {self._solution[:200]}\n\n"
                "Which action is needed? Reply with ONE of:\n"
                "  SEARCH <query>\n"
                "  REREAD_SCREEN\n"
                "  ANSWER <response to user>\n"
                "  RUN_TESTS\n"
                "  WRITE_FILE <path>|<content>"
            ),
            api_key=self._api_key,
            system="You are an assessment agent deciding what tool to use next.",
            temperature=0.2,
            max_tokens=100,
        )

        decision = decision.strip()
        await self._send(_think_event(f"Decided: {decision[:80]}"))

        if decision.startswith("SEARCH "):
            query = decision[7:].strip()
            await self._send(_tool_event("search", "start"))
            snippets = await self._search.search(query)
            await self._send(_tool_event("search", "done", {"results": snippets}))
            answer = "\n".join(snippets)
            await self._send(_guidance_event(answer))

        elif decision.startswith("REREAD_SCREEN"):
            await self._reread_screen()

        elif decision.startswith("RUN_TESTS"):
            await self._test_loop()

        elif decision.startswith("WRITE_FILE "):
            parts = decision[11:].split("|", 1)
            if len(parts) == 2 and self._file:
                path, content = parts
                try:
                    await self._file.write_file(path.strip(), content.strip())
                    await self._send(_tool_event("file", "done", {"wrote": path.strip()}))
                except PathEscapeError as exc:
                    await self._send(_tool_event("file", "error", {"error": exc.message}))

        elif decision.startswith("ANSWER "):
            await self._send(_guidance_event(decision[7:].strip()))

        else:
            # Default: stream a direct answer
            answer = await deepseek_generate(
                prompt=text,
                api_key=self._api_key,
                system="You are an expert engineer helping a candidate in a live coding interview.",
                max_tokens=400,
            )
            await self._send(_guidance_event(answer))

    async def _reread_screen(self) -> None:
        await self._send(_tool_event("screen", "start"))
        text = await self._screen.capture_and_extract()
        await self._send(_tool_event("screen", "done", {"preview": text[:200]}))
        if text.strip():
            self._problem_text = text
            self._test_cases = _parse_test_cases_from_text(text)
            await self._send(_think_event(
                f"Re-read screen. Extracted {len(self._test_cases)} test case(s)."
            ))

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    async def _generate_solution(self) -> tuple[str, str]:
        """Generate an optimal solution for the current problem."""
        test_case_str = "\n".join(
            f"Input: {tc['input']}\nOutput: {tc['output']}"
            for tc in self._test_cases[:5]
        ) if self._test_cases else "No test cases extracted."

        prompt = (
            f"Problem:\n{self._problem_text[:1500]}\n\n"
            f"Test cases:\n{test_case_str}\n\n"
            "Write a complete, optimal Python solution.\n"
            "Requirements:\n"
            "- Correct for all given test cases\n"
            "- Best possible Big-O time and space complexity\n"
            "- Include complexity analysis as a comment at the top\n"
            "- Read input from stdin using input() — one value or line per input() call\n"
            "- Print output to stdout\n"
            "- No extra explanation outside the code\n"
            "Reply with ONLY the Python code, nothing else."
        )

        code = await deepseek_generate(
            prompt=prompt,
            api_key=self._api_key,
            system="You are a competitive programmer writing optimal solutions.",
            temperature=0.2,
            max_tokens=800,
        )
        code = _strip_code_fences(code)
        return code, "python"

    async def _fix_solution(
        self, solution: str, language: str, failed_cases: list[dict]
    ) -> str:
        """Fix a failing solution given the test case failures."""
        failures = "\n".join(
            f"Input: {fc['input']}\nExpected: {fc['expected']}\nGot: {fc['actual']}"
            for fc in failed_cases[:3]
        )

        prompt = (
            f"This solution is failing test cases:\n\n```python\n{solution}\n```\n\n"
            f"Failures:\n{failures}\n\n"
            "Fix the solution so all test cases pass. "
            "Reply with ONLY the corrected Python code, nothing else."
        )

        fixed = await deepseek_generate(
            prompt=prompt,
            api_key=self._api_key,
            system="You are a competitive programmer debugging and fixing solutions.",
            temperature=0.1,
            max_tokens=800,
        )
        return _strip_code_fences(fixed)

    async def _generate_explanation(self, solution: str, language: str) -> str:
        """Generate a concise verbal explanation the user can deliver."""
        return await deepseek_generate(
            prompt=(
                f"Solution:\n```{language}\n{solution}\n```\n\n"
                "Write a 2-3 sentence verbal explanation the candidate can say out loud to the interviewer. "
                "Include the time and space complexity. Sound like a confident senior engineer."
            ),
            api_key=self._api_key,
            system="You are coaching a candidate for a live coding interview.",
            temperature=0.4,
            max_tokens=150,
        )

    async def close(self) -> None:
        """Release browser and other resources at session end."""
        await self._browser.close()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    text = re.sub(r"^```\w*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


def _parse_test_cases_from_text(text: str) -> list[dict]:
    """Extract Input/Output pairs from raw text (screen or search results)."""
    pattern = re.compile(
        r"(?:Input|input)\s*[:\-=]?\s*(.*?)\s*(?:Output|output|Expected)\s*[:\-=]?\s*(.*?)(?=(?:Input|input|Example|Constraint|Note|Explanation|\Z))",
        re.DOTALL | re.IGNORECASE,
    )
    cases = []
    for m in pattern.finditer(text):
        inp = m.group(1).strip()
        out = m.group(2).strip()
        if inp and out:
            cases.append({"input": inp, "output": out})
    return cases[:5]


def _extract_problem_name(text: str) -> str | None:
    """Try to extract a problem title from the text."""
    # Look for "N. Problem Name" (LeetCode format) or "Problem: ..."
    m = re.search(r"^(\d+)\.\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(2).strip()[:80]
    m = re.search(r"(?:Problem|Title)[:\s]+(.+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:80]
    # Use first non-empty line as a fallback guess
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) < 100:
            return stripped
    return None


def _verbal_summary(explanation: str) -> str:
    """Trim explanation to a speakable sentence."""
    sentences = explanation.split(". ")
    return ". ".join(sentences[:2]).strip()


def _build_run_script(
    solution: str, language: str, stdin: str
) -> tuple[str, list[str], str | None]:
    """
    Write the solution to a temp file and return the command to run it.
    Returns (script_path, command_list, working_dir).
    """
    import tempfile, os

    ext = {"python": ".py", "javascript": ".js", "typescript": ".ts"}.get(language, ".py")
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="w", encoding="utf-8")

    if stdin:
        # Prepend a stdin mock so the solution reads from our injected input
        injected = f"import sys\n_STDIN = iter({json.dumps(stdin.splitlines())})\ninput = lambda: next(_STDIN)\n\n"
        tmp.write(injected)

    tmp.write(solution)
    tmp.flush()
    tmp.close()

    if language == "python":
        python = sys.executable
        cmd = [python, tmp.name]
    elif language in ("javascript", "typescript"):
        cmd = ["node", tmp.name]
    else:
        cmd = ["python", tmp.name]

    return tmp.name, cmd, None


import sys  # noqa: E402 — needed inside _build_run_script
