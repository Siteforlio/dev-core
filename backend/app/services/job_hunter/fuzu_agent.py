# backend/app/services/job_hunter/fuzu_agent.py
"""
Fuzu Kenya job scraper using browser-use autonomous agent + Vertex Gemini.

Gives the agent a plain-English objective and lets it navigate, dismiss
popups, and extract job listings itself — no brittle CSS selectors.

Requires:
    VERTEX_API_KEY in environment (loaded from backend/.env)
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

# ── Environment ───────────────────────────────────────────────────────────────
_ENV_PATH = Path(__file__).parent.parent.parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

VERTEX_API_KEY = os.environ.get("VERTEX_API_KEY", "")
_VERTEX_ENDPOINT = (
    "https://aiplatform.googleapis.com/v1/publishers/google/models"
    "/gemini-2.5-flash-lite:generateContent"
)

# ── Category map ──────────────────────────────────────────────────────────────
_CATEGORY_MAP: dict[str, str] = {
    "software engineer":         "computers-software-development",
    "backend developer":         "computers-software-development",
    "frontend developer":        "computers-software-development",
    "full stack developer":      "computers-software-development",
    "python developer":          "computers-software-development",
    "data engineer":             "computers-software-development",
    "machine learning engineer": "computers-software-development",
    "devops engineer":           "computers-software-development",
    "mobile developer":          "computers-software-development",
    "cloud engineer":            "computers-software-development",
    "qa engineer":               "computers-software-development",
    "product manager":           "management-business-development",
    "data analyst":              "research-data-analysis",
    "data scientist":            "research-data-analysis",
    "ui designer":               "design",
    "ux designer":               "design",
    "network engineer":          "computers-it-networking",
    "sysadmin":                  "computers-it-networking",
    "it support":                "computers-it-networking",
    "cybersecurity":             "computers-it-networking",
}

_BASE_URL = "https://www.fuzu.com"
T = TypeVar("T")


# ── VertexGemini — browser-use BaseChatModel Protocol ────────────────────────
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
        from browser_use.llm.messages import UserMessage, SystemMessage, AssistantMessage

        contents: list[dict] = []
        system_instruction: str | None = None

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
        import httpx
        from browser_use.llm.views import ChatInvokeCompletion

        contents, system_instruction = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        if output_format is not None:
            from browser_use.llm.schema import SchemaOptimizer
            schema = SchemaOptimizer.create_optimized_json_schema(output_format)
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = schema

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                _VERTEX_ENDPOINT,
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
            clean = text.strip()
            if clean.startswith("```"):
                clean = re.sub(r"^```[a-z]*\n?", "", clean)
                clean = re.sub(r"\n?```$", "", clean)
            parsed = output_format.model_validate_json(clean)
            return ChatInvokeCompletion(completion=parsed, usage=None)

        return ChatInvokeCompletion(completion=text, usage=None)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _normalise(job: dict) -> dict:
    url = job.get("url", "")
    if url.startswith("/"):
        url = f"{_BASE_URL}{url}"
    return {
        "source": "fuzu",
        "title": (job.get("title") or "").strip(),
        "company": (job.get("company") or "").strip(),
        "location": job.get("location") or "Kenya",
        "location_country": "KE",
        "remote": False,
        "url": url,
        "apply_url": url,
        "description": (
            job.get("description")
            or f"Job on Fuzu Kenya: {job.get('title', '')} at {job.get('company', '')}"
        ),
    }


def _category_url(search_term: str) -> str:
    slug = _CATEGORY_MAP.get(search_term.lower())
    if slug:
        return f"{_BASE_URL}/kenya/job/{slug}?filters[country_id]=1"
    return f"{_BASE_URL}/kenya/jobs?q={search_term.replace(' ', '+')}"


# ── Main scrape function ──────────────────────────────────────────────────────
async def scrape_fuzu_agent(search_term: str) -> list[dict]:
    """
    Use browser-use + Vertex Gemini to autonomously scrape Fuzu Kenya.
    Falls back to [] on any error so callers are never broken.
    """
    if not VERTEX_API_KEY:
        print("[fuzu_agent] VERTEX_API_KEY not set", flush=True)
        return []

    try:
        from browser_use import Agent
        from browser_use.browser.session import BrowserSession
        from browser_use.browser.profile import BrowserProfile

        target_url = _category_url(search_term)
        llm = VertexGemini(api_key=VERTEX_API_KEY, temperature=0.0)

        task = (
            f"Go to {target_url} and find at least 10 tech job listings "
            f"(software, engineering, data, IT roles). "
            "For each job collect: title, company, location, and the full URL of the job detail page. "
            'Return ONLY a JSON array: [{"title": "...", "company": "...", "location": "...", "url": "..."}]'
        )

        browser_session = BrowserSession(browser_profile=BrowserProfile(headless=False))

        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser_session,
            use_vision=True,
            max_failures=5,
            max_steps=25,
        )

        result = await agent.run()

        raw_text = ""
        if hasattr(result, "final_result"):
            raw_text = result.final_result() or ""
        else:
            raw_text = str(result)

        # Try JSON array first
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if json_match:
            listings = json.loads(json_match.group(0))
            return [_normalise(j) for j in listings if j.get("title")]

        # Fallback: parse markdown bullet list the agent sometimes returns
        # Pattern: **Title:** ... **Company:** ... **Location:** ... **URL:** ...
        md_jobs = []
        blocks = re.split(r'\n(?=[-*]|\*\*Title)', raw_text)
        for block in blocks:
            title_m   = re.search(r'\*\*(?:Title|Job Title)[:\*]*\*?\*?\s*(.+)', block)
            company_m = re.search(r'\*\*Company[:\*]*\*?\*?\s*(.+)', block)
            loc_m     = re.search(r'\*\*Location[:\*]*\*?\*?\s*(.+)', block)
            url_m     = re.search(r'\*\*URL[:\*]*\*?\*?\s*(https?://\S+|/kenya/\S+)', block)
            if title_m:
                md_jobs.append({
                    "title":    title_m.group(1).strip().rstrip("*"),
                    "company":  company_m.group(1).strip().rstrip("*") if company_m else "",
                    "location": loc_m.group(1).strip().rstrip("*") if loc_m else "Kenya",
                    "url":      url_m.group(1).strip().rstrip("*") if url_m else "",
                })

        if md_jobs:
            print(f"[fuzu_agent] parsed {len(md_jobs)} jobs from markdown fallback", flush=True)
            return [_normalise(j) for j in md_jobs if j.get("title")]

        print(f"[fuzu_agent] no parseable output: {raw_text[:200]}", flush=True)
        return []

    except Exception as e:
        print(f"[fuzu_agent] error: {type(e).__name__}: {e}", flush=True)
        return []


# ── Standalone test ───────────────────────────────────────────────────────────
async def _main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    term = "software engineer"
    print("=" * 60)
    print(f"Fuzu Agent — search: {term}")
    print(f"URL: {_category_url(term)}")
    print("=" * 60)

    jobs = await scrape_fuzu_agent(term)

    print(f"\nJobs found: {len(jobs)}")
    print("-" * 60)
    for i, j in enumerate(jobs, 1):
        print(f"  {i:>2}. {j['title']:<50}  {j['company']:<35}  {j['location']}")


if __name__ == "__main__":
    asyncio.run(_main())
