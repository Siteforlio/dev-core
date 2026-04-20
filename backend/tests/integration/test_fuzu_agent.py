# backend/tests/integration/test_fuzu_agent.py
"""
Simple browser-use agent test: scrape Fuzu Kenya and find 10 different tech jobs.

Run:
    cd backend
    venv/Scripts/python.exe tests/integration/test_fuzu_agent.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, overload

# Windows: ProactorEventLoop required for nodriver/Chrome subprocess
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Force UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load .env
_ENV = Path(__file__).parent.parent.parent / ".env"
if _ENV.exists():
    for _line in _ENV.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            k, _, v = _line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

VERTEX_API_KEY = os.environ.get("VERTEX_API_KEY", "")
VERTEX_ENDPOINT = (
    "https://aiplatform.googleapis.com/v1/publishers/google/models"
    "/gemini-2.5-flash-lite:generateContent"
)

SEP = "-" * 60
T = TypeVar("T")


# ---------------------------------------------------------------------------
# VertexGemini — implements browser-use BaseChatModel Protocol
# ---------------------------------------------------------------------------
@dataclass
class VertexGemini:
    """
    Calls the Vertex AI REST endpoint directly with an API key.
    Implements the browser-use BaseChatModel Protocol (not LangChain's).
    """
    model: str = "gemini-2.5-flash-lite"
    api_key: str = ""
    temperature: float = 0.0

    _verified_api_keys: bool = field(default=False, init=False)

    @property
    def provider(self) -> str:
        return "google"

    @property
    def name(self) -> str:
        return self.model

    @property
    def model_name(self) -> str:
        return self.model

    def _convert_messages(self, messages: list) -> tuple[list[dict], str | None]:
        """Convert browser-use messages to Vertex AI contents format."""
        from browser_use.llm.messages import UserMessage, SystemMessage, AssistantMessage

        contents = []
        system_instruction = None

        for m in messages:
            if isinstance(m, SystemMessage):
                system_instruction = m.text
            elif isinstance(m, UserMessage):
                if isinstance(m.content, list):
                    parts = []
                    for part in m.content:
                        if part.type == "text":
                            parts.append({"text": part.text})
                        elif part.type == "image_url":
                            url = part.image_url.url
                            if url.startswith("data:"):
                                header, b64 = url.split(",", 1)
                                mime = header.split(":")[1].split(";")[0]
                                parts.append({
                                    "inline_data": {"mime_type": mime, "data": b64}
                                })
                    contents.append({"role": "user", "parts": parts or [{"text": m.text}]})
                else:
                    contents.append({"role": "user", "parts": [{"text": m.text}]})
            elif isinstance(m, AssistantMessage):
                contents.append({"role": "model", "parts": [{"text": m.text}]})

        return contents, system_instruction

    @overload
    async def ainvoke(self, messages: list, output_format: None = None, **kwargs: Any) -> Any: ...
    @overload
    async def ainvoke(self, messages: list, output_format: type[T], **kwargs: Any) -> Any: ...

    async def ainvoke(self, messages: list, output_format=None, **kwargs: Any) -> Any:
        from browser_use.llm.views import ChatInvokeCompletion

        import httpx
        contents, system_instruction = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if output_format is not None:
            # Ask Gemini to return JSON matching the schema
            from browser_use.llm.schema import SchemaOptimizer
            schema = SchemaOptimizer.create_optimized_json_schema(output_format)
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = schema

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                VERTEX_ENDPOINT,
                params={"key": self.api_key},
                json=payload,
            )
        response.raise_for_status()
        data = response.json()

        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if output_format is not None:
            # Strip markdown fences if present
            clean = text.strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```[a-z]*\n?", "", clean)
                clean = re.sub(r"\n?```$", "", clean)
            parsed = output_format.model_validate_json(clean)
            return ChatInvokeCompletion(completion=parsed, usage=None)

        return ChatInvokeCompletion(completion=text, usage=None)


# ---------------------------------------------------------------------------
# Agent task
# ---------------------------------------------------------------------------
TARGET_URL = (
    "https://www.fuzu.com/kenya/job/computers-software-development"
    "?filters[country_id]=1"
)

TASK = (
    "Go to https://www.fuzu.com/kenya/job/computers-software-development?filters[country_id]=1 "
    "and find at least 10 tech job listings (software, engineering, data, IT roles). "
    "For each job collect: title, company, location, and the full URL of the job detail page. "
    "Return ONLY a JSON array: "
    '[{"title": "...", "company": "...", "location": "...", "url": "..."}]'
)


async def run_agent_test() -> list[dict]:
    from browser_use import Agent
    from browser_use.browser.session import BrowserSession
    from browser_use.browser.profile import BrowserProfile
    from browser_use.llm.messages import UserMessage

    print(f"\n{SEP}")
    print("  FUZU AGENT TEST -- browser-use + Vertex Gemini 2.5 Flash Lite")
    print(SEP)

    if not VERTEX_API_KEY:
        print("  ERROR: VERTEX_API_KEY not set in .env")
        return []

    llm = VertexGemini(api_key=VERTEX_API_KEY, temperature=0.0)

    print("\n[1/4] Smoke-testing LLM...")
    try:
        resp = await llm.ainvoke([UserMessage(content="Reply with exactly: OK")])
        print(f"  LLM smoke-test: {str(resp.completion).strip()[:40]}")
    except Exception as e:
        print(f"  LLM smoke-test FAILED: {e}")
        return []

    print("\n[2/4] Launching browser agent...")
    print(f"  URL: {TARGET_URL}")

    browser_profile = BrowserProfile(headless=False)  # headless=False for Cloudflare
    browser_session = BrowserSession(browser_profile=browser_profile)

    def on_step(state, output, step_num):
        goal = getattr(output, "current_state", None)
        if goal:
            next_goal = getattr(goal, "next_goal", "")
            memory = getattr(goal, "memory", "")
            if next_goal:
                print(f"  Step {step_num}: {next_goal[:100]}")
            if memory:
                print(f"           {memory[:100]}")

    agent = Agent(
        task=TASK,
        llm=llm,
        browser_session=browser_session,
        use_vision=True,
        max_failures=5,
        register_new_step_callback=on_step,
    )

    print("\n[3/4] Running agent (watching browser)...")
    result = await agent.run(max_steps=25)

    print("\n[4/4] Parsing results...")
    raw_text = ""
    if hasattr(result, "final_result"):
        raw_text = result.final_result() or ""
    else:
        raw_text = str(result)

    print(f"  Raw output: {raw_text[:300]}")

    # Check if agent reported failure
    if hasattr(result, "is_done") and not result.is_done():
        print("\n  AGENT DID NOT COMPLETE. Diagnosis:")
        errors = getattr(result, "errors", []) or []
        for err in errors[-3:]:
            print(f"    - {err}")
        print("\n  Recommendation: check browser logs above for the last step taken.")
        return []

    json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if not json_match:
        print(f"\n  WARNING: No JSON array found in output.")
        print(f"  Agent said: {raw_text[:500]}")
        print("\n  Recommendation: agent may have navigated to wrong page or hit max_steps.")
        return []

    try:
        jobs = json.loads(json_match.group(0))
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}\n{json_match.group(0)[:300]}")
        return []

    # Fix relative URLs
    for j in jobs:
        url = j.get("url", "")
        if url.startswith("/"):
            j["url"] = "https://www.fuzu.com" + url
    return [j for j in jobs if j.get("title")]


async def main():
    jobs = await run_agent_test()

    print(f"\n{SEP}")
    print(f"  RESULTS: {len(jobs)} jobs found")
    print(SEP)

    for i, j in enumerate(jobs, 1):
        title   = (j.get("title") or "")[:55]
        company = (j.get("company") or "")[:35]
        loc     = (j.get("location") or "Kenya")[:20]
        print(f"  {i:>2}. {title:<55}  {company:<35}  {loc}")

    print()
    if len(jobs) >= 10:
        print(f"  PASS: found {len(jobs)} jobs (target: 10)")
    else:
        print(f"  FAIL: only found {len(jobs)} jobs (target: 10)")

    return jobs


if __name__ == "__main__":
    asyncio.run(main())
