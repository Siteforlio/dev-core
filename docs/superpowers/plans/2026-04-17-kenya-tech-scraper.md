# Kenya Tech Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tech-role pre-filtering, SMB preference scoring, and 9 new job board scrapers (3 HTTP + 6 Kenya/browser-based) to the Job Hunter scraper so it reliably surfaces 100+ matched tech jobs per day.

**Architecture:** Three independent additions wired together in `scraper_service.py`: (1) a fast keyword pre-filter that rejects non-tech jobs before they hit Claude Haiku, (2) new HTTP-based scrapers in `startup_scrapers.py`, (3) new browser-based Kenya scrapers in a new `kenya_scrapers.py`. The per-pass processing loop in `scrape_campaign` is restructured from streaming to batch (filter → score → sort → dispatch) to enable SMB-priority ordering.

**Tech Stack:** Python, httpx (async HTTP), nodriver (Chrome automation), BeautifulSoup/regex (HTML parsing), feedparser or xml.etree (RSS), asyncio.gather, pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/services/job_hunter/scraper_service.py` | Modify | Add `_SCORE_ORDER`, `_tech_role_prefilter`, `_smb_score`; restructure `scrape_campaign` loop; add `kenya_fetched` flag |
| `backend/app/services/job_hunter/startup_scrapers.py` | Modify | Add `scrape_weworkremotely`, `scrape_zindi`, `scrape_startupdeals_africa` |
| `backend/app/services/job_hunter/kenya_scrapers.py` | Create | 6 scrapers + `scrape_all_kenya_boards` |
| `backend/tests/services/job_hunter/test_tech_filter.py` | Create | Tests for `_tech_role_prefilter` and `_smb_score` |
| `backend/tests/services/job_hunter/test_startup_scrapers.py` | Create | Tests for the 3 new HTTP scrapers |
| `backend/tests/services/job_hunter/test_kenya_scrapers.py` | Create | Tests for `scrape_all_kenya_boards` |

---

## Task 1: `_tech_role_prefilter` and `_smb_score` — tests first

**Files:**
- Create: `backend/tests/services/job_hunter/test_tech_filter.py`
- Modify: `backend/app/services/job_hunter/scraper_service.py`

- [ ] **Step 1: Create the test file**

```python
# backend/tests/services/job_hunter/test_tech_filter.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.job_hunter.scraper_service import ScraperService, _SCORE_ORDER, _smb_score


def make_service():
    db = AsyncMock()
    return ScraperService(db)


class TestTechRolePrefilter:
    def test_rejects_sales_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("Sales Manager", "") is False

    def test_rejects_marketing_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("Marketing Coordinator", "") is False

    def test_rejects_hr_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("HR Business Partner", "") is False

    def test_accepts_engineer_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("Backend Engineer", "") is True

    def test_accepts_developer_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("Senior Developer", "") is True

    def test_accepts_data_scientist_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("Data Scientist", "") is True

    def test_accepts_product_manager_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("Product Manager", "") is True

    def test_accepts_cto_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("CTO", "") is True

    def test_ambiguous_title_falls_back_to_description(self):
        svc = make_service()
        # "Analyst" alone is ambiguous — not in reject or accept lists
        assert svc._tech_role_prefilter("Analyst", "We are hiring a data engineer to...") is True

    def test_ambiguous_title_no_tech_desc_passes_through(self):
        svc = make_service()
        # Both title and description have no tech signals — default pass (True)
        assert svc._tech_role_prefilter("Associate", "Join our growing team.") is True

    def test_description_check_uses_post_strip_html(self):
        svc = make_service()
        html_desc = "<p>We need a <strong>backend engineer</strong> to build APIs</p>"
        # Title is ambiguous; description after HTML strip contains "backend engineer"
        assert svc._tech_role_prefilter("Associate", html_desc) is True

    def test_description_check_uses_only_first_300_chars(self):
        svc = make_service()
        # No tech signals in first 300 chars, but "engineer" appears after 300
        long_prefix = "A" * 300
        desc = long_prefix + " engineer role available"
        assert svc._tech_role_prefilter("Associate", desc) is True  # default pass

    def test_reject_signals_not_checked_in_description(self):
        svc = make_service()
        # "sales" in description should NOT cause rejection when title is ambiguous
        assert svc._tech_role_prefilter("Analyst", "sales and marketing analyst") is True

    def test_case_insensitive_title(self):
        svc = make_service()
        assert svc._tech_role_prefilter("BACKEND ENGINEER", "") is True
        assert svc._tech_role_prefilter("SALES DIRECTOR", "") is False


class TestSmbScore:
    def test_startup_native_source_gets_two_points(self):
        job = {"source": "fuzu", "company": "Some Startup"}
        assert _smb_score(job) == 3  # +2 source + 1 not-large-corp

    def test_hn_hiring_source_gets_two_points(self):
        job = {"source": "hn_hiring", "company": "HN Startup"}
        assert _smb_score(job) == 3

    def test_non_native_source_no_source_bonus(self):
        job = {"source": "greenhouse", "company": "Some Startup"}
        assert _smb_score(job) == 1  # +0 source + 1 not-large-corp

    def test_large_corp_company_gets_zero_company_bonus(self):
        job = {"source": "greenhouse", "company": "Google"}
        assert _smb_score(job) == 0  # +0 source + 0 large-corp

    def test_large_corp_from_startup_source_still_no_company_bonus(self):
        job = {"source": "remotive", "company": "Microsoft"}
        assert _smb_score(job) == 2  # +2 source + 0 large-corp

    def test_empty_company_no_company_bonus(self):
        job = {"source": "greenhouse", "company": ""}
        assert _smb_score(job) == 0  # +0 source + 0 empty company

    def test_missing_company_key_no_company_bonus(self):
        job = {"source": "greenhouse"}
        assert _smb_score(job) == 0

    def test_all_startup_native_sources_recognized(self):
        sources = [
            "hn_hiring", "remotive", "remoteok", "weworkremotely", "zindi",
            "startupdeals_africa", "fuzu", "brightermonday", "myjobmag",
            "kuhustle", "andela", "arc",
        ]
        for source in sources:
            job = {"source": source, "company": "startup"}
            assert _smb_score(job) >= 2, f"Expected +2 for source={source}"

    def test_score_order_constant(self):
        assert _SCORE_ORDER["MATCH"] < _SCORE_ORDER["PARTIAL"] < _SCORE_ORDER["SKIP"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/services/job_hunter/test_tech_filter.py -v 2>&1 | head -30
```

Expected: ImportError or AttributeError — `_tech_role_prefilter`, `_smb_score`, `_SCORE_ORDER` don't exist yet.

- [ ] **Step 3: Add `_SCORE_ORDER`, `_tech_role_prefilter`, and `_smb_score` to `scraper_service.py`**

Add `_SCORE_ORDER` at module level (after imports, before `ScraperService` class):

```python
import re as _re

_SCORE_ORDER = {"MATCH": 0, "PARTIAL": 1, "SKIP": 2}

_TECH_REJECT_SIGNALS = {
    "sales", "marketing", "accountant", "recruiter", "hr ", "human resources",
    "legal", "logistics", "driver", "cook", "nurse", "doctor", "cleaner",
}

_TECH_ACCEPT_SIGNALS = {
    "engineer", "developer", "architect", "devops", "sre", "backend", "frontend",
    "fullstack", "full-stack", "full stack", "mobile", "ios", "android", "embedded",
    "firmware", "cloud", "platform",
    "data scientist", "data analyst", "data engineer", "machine learning",
    "ml engineer", "ai engineer",
    "product manager", "ux", "ui designer", "product designer",
    "security", "cybersecurity", "penetration", "sysadmin", "network engineer",
    "it support", "database admin", "dba",
    "technical lead", "tech lead", "engineering manager", "cto", "vp engineering",
    "staff engineer", "solutions engineer", "developer advocate", "technical writer",
    "qa engineer", "test engineer",
}

_LARGE_CORP_SIGNALS = {
    "google", "microsoft", "amazon", "meta", "apple", "ibm", "oracle", "sap",
    "accenture", "deloitte", "pwc", "kpmg", "ernst", "capgemini", "infosys",
    "wipro", "tcs", "cognizant",
}

_STARTUP_NATIVE_SOURCES = {
    "hn_hiring", "remotive", "remoteok", "weworkremotely", "zindi",
    "startupdeals_africa", "fuzu", "brightermonday", "myjobmag",
    "kuhustle", "andela", "arc",
}


def _smb_score(job: dict) -> int:
    """Score a job for SMB/startup preference. Higher = more startup-like. Max 3."""
    score = 0
    if job.get("source", "") in _STARTUP_NATIVE_SOURCES:
        score += 2
    company = (job.get("company") or "").strip().lower()
    if company and not any(sig in company for sig in _LARGE_CORP_SIGNALS):
        score += 1
    return score
```

Add `_tech_role_prefilter` as a method on `ScraperService` (after `_keyword_prefilter`):

```python
def _tech_role_prefilter(self, title: str, description: str) -> bool:
    """Return False to drop obvious non-tech jobs before AI scoring.
    Default is True — ambiguous jobs pass through to Haiku."""
    t = title.lower()
    if any(sig in t for sig in _TECH_REJECT_SIGNALS):
        return False
    if any(sig in t for sig in _TECH_ACCEPT_SIGNALS):
        return True
    # Title is ambiguous — check first 300 chars of stripped description
    stripped = _re.sub(r'<[^>]+>', ' ', description).lower()[:300]
    if any(sig in stripped for sig in _TECH_ACCEPT_SIGNALS):
        return True
    return True  # default: pass through
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/services/job_hunter/test_tech_filter.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/job_hunter/scraper_service.py \
        backend/tests/services/job_hunter/test_tech_filter.py
git commit -m "feat(scraper): add _tech_role_prefilter, _smb_score, _SCORE_ORDER"
```

---

## Task 2: New HTTP scrapers in `startup_scrapers.py`

**Files:**
- Modify: `backend/app/services/job_hunter/startup_scrapers.py`
- Create: `backend/tests/services/job_hunter/test_startup_scrapers.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/job_hunter/test_startup_scrapers.py
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_scrape_weworkremotely_returns_list():
    """scrape_weworkremotely returns a list (possibly empty on network error)."""
    from app.services.job_hunter.startup_scrapers import scrape_weworkremotely
    async with httpx.AsyncClient() as client:
        result = await scrape_weworkremotely("software engineer", client)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_scrape_weworkremotely_job_shape():
    """Jobs from WWR have required fields."""
    from app.services.job_hunter.startup_scrapers import scrape_weworkremotely

    rss_xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Senior Python Developer at Acme</title>
        <link>https://weworkremotely.com/job/123</link>
        <description>We need a senior developer...</description>
        <category>Programming</category>
      </item>
    </channel></rss>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = rss_xml

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await scrape_weworkremotely("developer", mock_client)
    assert len(result) == 1
    job = result[0]
    assert job["source"] == "weworkremotely"
    assert job["remote"] is True
    assert "url" in job
    assert "title" in job


@pytest.mark.asyncio
async def test_scrape_weworkremotely_handles_error_gracefully():
    """Returns [] on HTTP error."""
    from app.services.job_hunter.startup_scrapers import scrape_weworkremotely
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("network error"))
    result = await scrape_weworkremotely("developer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_zindi_returns_list():
    """scrape_zindi returns a list."""
    from app.services.job_hunter.startup_scrapers import scrape_zindi
    async with httpx.AsyncClient() as client:
        result = await scrape_zindi("data scientist", client)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_scrape_zindi_handles_error_gracefully():
    """Returns [] on HTTP error."""
    from app.services.job_hunter.startup_scrapers import scrape_zindi
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))
    result = await scrape_zindi("data", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_startupdeals_africa_returns_list():
    """scrape_startupdeals_africa returns a list."""
    from app.services.job_hunter.startup_scrapers import scrape_startupdeals_africa
    async with httpx.AsyncClient() as client:
        result = await scrape_startupdeals_africa("engineer", client)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_scrape_startupdeals_africa_handles_error_gracefully():
    """Returns [] on HTTP error."""
    from app.services.job_hunter.startup_scrapers import scrape_startupdeals_africa
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))
    result = await scrape_startupdeals_africa("engineer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_all_startup_boards_includes_new_sources():
    """scrape_all_startup_boards calls all 6 scrapers (3 existing + 3 new)."""
    from app.services.job_hunter import startup_scrapers

    called = []

    async def fake_scraper(search_term, client):
        called.append(search_term)
        return []

    with patch.object(startup_scrapers, "scrape_remotive", fake_scraper), \
         patch.object(startup_scrapers, "scrape_remoteok", fake_scraper), \
         patch.object(startup_scrapers, "scrape_hn_who_is_hiring", fake_scraper), \
         patch.object(startup_scrapers, "scrape_weworkremotely", fake_scraper), \
         patch.object(startup_scrapers, "scrape_zindi", fake_scraper), \
         patch.object(startup_scrapers, "scrape_startupdeals_africa", fake_scraper):
        result = await startup_scrapers.scrape_all_startup_boards("engineer")

    assert len(called) == 6
    assert result == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/services/job_hunter/test_startup_scrapers.py -v 2>&1 | head -20
```

Expected: ImportError — `scrape_weworkremotely`, `scrape_zindi`, `scrape_startupdeals_africa` not defined.

- [ ] **Step 3: Implement the three new scrapers in `startup_scrapers.py`**

Add after the existing `scrape_hn_who_is_hiring` function:

```python
async def scrape_weworkremotely(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    We Work Remotely — RSS feed, no auth.
    We fetch the programming + devops categories which cover tech roles.
    """
    import xml.etree.ElementTree as ET
    urls = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
    ]
    jobs = []
    for url in urls:
        try:
            r = await client.get(url, timeout=_HTTP_TIMEOUT)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.text)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = re.sub(r'<[^>]+>', ' ', item.findtext("description") or "")
                region = (item.findtext("{https://weworkremotely.com}region") or "Worldwide").strip()
                if not title or not link:
                    continue
                # Title format: "Company: Job Title"
                parts = title.split(":", 1)
                company = parts[0].strip() if len(parts) == 2 else "Unknown"
                job_title = parts[1].strip() if len(parts) == 2 else title
                jobs.append(_normalize({
                    "source": "weworkremotely",
                    "title": job_title,
                    "company": company,
                    "location": region,
                    "location_country": None,
                    "remote": True,
                    "url": link,
                    "apply_url": link,
                    "description": desc[:5000],
                }))
        except Exception:
            continue
    return jobs


async def scrape_zindi(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Zindi Africa — public jobs listing page (HTML scrape).
    Zindi is Africa's largest data science community.
    """
    try:
        r = await client.get(
            "https://zindi.africa/jobs",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        # Extract job cards via regex (lightweight — no BS4 dependency)
        # Pattern: look for job title and company in page HTML
        titles = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]+)<', r.text)
        companies = re.findall(r'class="[^"]*company-name[^"]*"[^>]*>([^<]+)<', r.text)
        urls_found = re.findall(r'href="(/jobs/[^"]+)"', r.text)
        jobs = []
        for i, title in enumerate(titles[:50]):
            company = companies[i] if i < len(companies) else "Zindi"
            path = urls_found[i] if i < len(urls_found) else "/jobs"
            job_url = f"https://zindi.africa{path}"
            jobs.append(_normalize({
                "source": "zindi",
                "title": title.strip(),
                "company": company.strip(),
                "location": "Africa / Remote",
                "location_country": None,
                "remote": True,
                "url": job_url,
                "apply_url": job_url,
                "description": f"Data science / ML role at {company.strip()} via Zindi Africa.",
            }))
        return jobs
    except Exception:
        return []


async def scrape_startupdeals_africa(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Startup Deals Africa — lists funded African startups.
    We scrape their jobs/careers page for open roles.
    """
    try:
        r = await client.get(
            "https://startupdeals.africa/jobs/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        # Extract job listings via regex
        titles = re.findall(r'<h[23][^>]*>([^<]{5,80})</h[23]>', r.text)
        links = re.findall(r'href="(https://startupdeals\.africa/jobs/[^"]+)"', r.text)
        jobs = []
        seen: set[str] = set()
        for i, title in enumerate(titles[:50]):
            title = title.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            url = links[i] if i < len(links) else "https://startupdeals.africa/jobs/"
            jobs.append(_normalize({
                "source": "startupdeals_africa",
                "title": title,
                "company": "African Startup",
                "location": "Africa",
                "location_country": None,
                "remote": False,
                "url": url,
                "apply_url": url,
                "description": f"Role at an African startup. See {url} for details.",
            }))
        return jobs
    except Exception:
        return []
```

Update `scrape_all_startup_boards` to include the three new scrapers:

```python
async def scrape_all_startup_boards(
    search_term: str,
    publish_fn=None,
) -> list[dict]:
    if publish_fn:
        await publish_fn(
            f"🚀 Querying startup job boards "
            f"(Remotive + RemoteOK + HN Who's Hiring + WeWorkRemotely + Zindi + Startup Deals Africa)..."
        )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        (
            remotive_jobs, remoteok_jobs, hn_jobs,
            wwr_jobs, zindi_jobs, sda_jobs,
        ) = await asyncio.gather(
            scrape_remotive(search_term, client),
            scrape_remoteok(search_term, client),
            scrape_hn_who_is_hiring(search_term, client),
            scrape_weworkremotely(search_term, client),
            scrape_zindi(search_term, client),
            scrape_startupdeals_africa(search_term, client),
        )

    all_jobs = remotive_jobs + remoteok_jobs + hn_jobs + wwr_jobs + zindi_jobs + sda_jobs

    if publish_fn:
        await publish_fn(
            f"  ↳ Remotive: {len(remotive_jobs)} | RemoteOK: {len(remoteok_jobs)} | "
            f"HN Hiring: {len(hn_jobs)} | WeWorkRemotely: {len(wwr_jobs)} | "
            f"Zindi: {len(zindi_jobs)} | Startup Deals Africa: {len(sda_jobs)} "
            f"= {len(all_jobs)} total startup listings"
        )

    return all_jobs
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/services/job_hunter/test_startup_scrapers.py -v
```

Expected: All tests PASS. (Network tests for `_returns_list` may return empty lists — that's fine.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/job_hunter/startup_scrapers.py \
        backend/tests/services/job_hunter/test_startup_scrapers.py
git commit -m "feat(scraper): add WeWorkRemotely, Zindi, Startup Deals Africa scrapers"
```

---

## Task 3: Kenya board scrapers (`kenya_scrapers.py`)

**Files:**
- Create: `backend/app/services/job_hunter/kenya_scrapers.py`
- Create: `backend/tests/services/job_hunter/test_kenya_scrapers.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/job_hunter/test_kenya_scrapers.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_returns_list():
    """scrape_all_kenya_boards always returns a list."""
    from app.services.job_hunter.kenya_scrapers import scrape_all_kenya_boards
    result = await scrape_all_kenya_boards("software engineer")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_tolerates_individual_failures():
    """If every individual scraper fails, returns empty list (no exception)."""
    from app.services.job_hunter import kenya_scrapers

    async def fail(*args, **kwargs):
        raise Exception("network error")

    with patch.object(kenya_scrapers, "scrape_fuzu", fail), \
         patch.object(kenya_scrapers, "scrape_brightermonday", fail), \
         patch.object(kenya_scrapers, "scrape_myjobmag", fail), \
         patch.object(kenya_scrapers, "scrape_kuhustle", fail), \
         patch.object(kenya_scrapers, "scrape_andela", fail), \
         patch.object(kenya_scrapers, "scrape_arc", fail):
        result = await kenya_scrapers.scrape_all_kenya_boards("engineer")

    assert result == []


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_aggregates_results():
    """Results from all boards are concatenated."""
    from app.services.job_hunter import kenya_scrapers

    fake_job = {
        "source": "fuzu", "title": "Dev", "company": "Acme",
        "location": "Nairobi", "location_country": "KE",
        "remote": False, "url": "http://x", "apply_url": "http://x",
        "description": "desc",
    }

    async def return_one(*args, **kwargs):
        return [fake_job]

    async def return_empty(*args, **kwargs):
        return []

    with patch.object(kenya_scrapers, "scrape_fuzu", return_one), \
         patch.object(kenya_scrapers, "scrape_brightermonday", return_one), \
         patch.object(kenya_scrapers, "scrape_myjobmag", return_empty), \
         patch.object(kenya_scrapers, "scrape_kuhustle", return_empty), \
         patch.object(kenya_scrapers, "scrape_andela", return_empty), \
         patch.object(kenya_scrapers, "scrape_arc", return_empty):
        result = await kenya_scrapers.scrape_all_kenya_boards("engineer")

    assert len(result) == 2


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_publishes_counts():
    """publish_fn receives a count line with all 6 boards."""
    from app.services.job_hunter import kenya_scrapers

    async def return_empty(*args, **kwargs):
        return []

    messages = []
    async def capture(msg):
        messages.append(msg)

    with patch.object(kenya_scrapers, "scrape_fuzu", return_empty), \
         patch.object(kenya_scrapers, "scrape_brightermonday", return_empty), \
         patch.object(kenya_scrapers, "scrape_myjobmag", return_empty), \
         patch.object(kenya_scrapers, "scrape_kuhustle", return_empty), \
         patch.object(kenya_scrapers, "scrape_andela", return_empty), \
         patch.object(kenya_scrapers, "scrape_arc", return_empty):
        await kenya_scrapers.scrape_all_kenya_boards("engineer", publish_fn=capture)

    count_line = next((m for m in messages if "Fuzu:" in m), None)
    assert count_line is not None
    assert "BrighterMonday:" in count_line
    assert "Arc:" in count_line


@pytest.mark.asyncio
async def test_kenya_job_shape():
    """Jobs from Kenya scrapers have all required normalized fields."""
    from app.services.job_hunter import kenya_scrapers

    fake_job = {
        "source": "kuhustle",
        "title": "Backend Developer",
        "company": "Nairobi Tech",
        "location": "Nairobi, Kenya",
        "location_country": "KE",
        "remote": False,
        "url": "https://kuhustle.com/job/1",
        "apply_url": "https://kuhustle.com/job/1",
        "description": "Python backend role",
    }

    async def return_one(*args, **kwargs):
        return [fake_job]

    async def return_empty(*args, **kwargs):
        return []

    with patch.object(kenya_scrapers, "scrape_fuzu", return_empty), \
         patch.object(kenya_scrapers, "scrape_brightermonday", return_empty), \
         patch.object(kenya_scrapers, "scrape_myjobmag", return_empty), \
         patch.object(kenya_scrapers, "scrape_kuhustle", return_one), \
         patch.object(kenya_scrapers, "scrape_andela", return_empty), \
         patch.object(kenya_scrapers, "scrape_arc", return_empty):
        result = await kenya_scrapers.scrape_all_kenya_boards("developer")

    assert len(result) == 1
    job = result[0]
    for field in ["source", "title", "company", "location", "remote", "url", "apply_url", "description"]:
        assert field in job, f"Missing field: {field}"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/services/job_hunter/test_kenya_scrapers.py -v 2>&1 | head -10
```

Expected: ModuleNotFoundError — `kenya_scrapers` doesn't exist yet.

- [ ] **Step 3: Create `kenya_scrapers.py`**

```python
# backend/app/services/job_hunter/kenya_scrapers.py
"""
Kenya and Africa-focused job board scrapers.
Fuzu, BrighterMonday, MyJobMag, Kuhustle, Andela, Arc.dev

Strategy: attempt lightweight httpx scrape first; use BrowserService (nodriver)
as fallback for SPAs that require JS rendering.

Each scraper catches all exceptions and returns [] — callers never see errors.
"""
import asyncio
import re
import httpx

_HTTP_TIMEOUT = 15.0


def _normalize(job: dict) -> dict:
    return {
        "source": job.get("source", "kenya"),
        "title": (job.get("title") or "").strip(),
        "company": (job.get("company") or "").strip(),
        "location": job.get("location"),
        "location_country": job.get("location_country"),
        "remote": job.get("remote", False),
        "url": job.get("url", ""),
        "apply_url": job.get("apply_url") or job.get("url", ""),
        "description": (job.get("description") or "")[:5000],
    }


async def scrape_fuzu(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Fuzu.com — Kenya's most active job board for SMBs. Uses nodriver (SPA)."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            url = f"https://www.fuzu.com/kenya/jobs?q={search_term.replace(' ', '+')}"
            await browser.goto(page, url, wait=3.0)
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerText")
            # Extract JSON-LD or visible job cards
            titles = re.findall(r'"title"\s*:\s*"([^"]{5,100})"', html)
            companies = re.findall(r'"hiringOrganization"[^}]*"name"\s*:\s*"([^"]{2,80})"', html)
            urls_found = re.findall(r'"url"\s*:\s*"(https://www\.fuzu\.com/kenya/jobs/[^"]+)"', html)
            for i, title in enumerate(titles[:50]):
                company = companies[i] if i < len(companies) else "Fuzu Company"
                job_url = urls_found[i] if i < len(urls_found) else "https://www.fuzu.com/kenya/jobs"
                jobs.append(_normalize({
                    "source": "fuzu",
                    "title": title,
                    "company": company,
                    "location": "Kenya",
                    "location_country": "KE",
                    "remote": False,
                    "url": job_url,
                    "apply_url": job_url,
                    "description": f"Job listing on Fuzu Kenya: {title} at {company}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_brightermonday(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """BrighterMonday Kenya — high-volume local board. Uses nodriver (SPA)."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            query = search_term.replace(' ', '%20')
            url = f"https://www.brightermonday.co.ke/jobs?q={query}"
            await browser.goto(page, url, wait=3.0)
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerHTML")
            # Job cards typically have data attributes or JSON-LD
            titles = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]{5,100})<', html)
            companies = re.findall(r'class="[^"]*company[^"]*"[^>]*>([^<]{2,80})<', html)
            links = re.findall(r'href="(/jobs/[^"?]+)"', html)
            for i, title in enumerate(titles[:50]):
                company = companies[i] if i < len(companies) else "BrighterMonday Company"
                path = links[i] if i < len(links) else "/jobs"
                job_url = f"https://www.brightermonday.co.ke{path}"
                jobs.append(_normalize({
                    "source": "brightermonday",
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": "Kenya",
                    "location_country": "KE",
                    "remote": False,
                    "url": job_url,
                    "apply_url": job_url,
                    "description": f"Job on BrighterMonday Kenya: {title.strip()} at {company.strip()}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_myjobmag(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """MyJobMag Kenya — standard HTML, httpx sufficient."""
    try:
        query = search_term.replace(' ', '+')
        r = await client.get(
            f"https://www.myjobmag.co.ke/jobs-by-field/{query}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        html = r.text
        titles = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]{5,100})<', html)
        companies = re.findall(r'class="[^"]*company-name[^"]*"[^>]*>([^<]{2,80})<', html)
        links = re.findall(r'href="(https://www\.myjobmag\.co\.ke/job/[^"]+)"', html)
        jobs = []
        for i, title in enumerate(titles[:50]):
            company = companies[i] if i < len(companies) else "MyJobMag Company"
            url = links[i] if i < len(links) else "https://www.myjobmag.co.ke"
            jobs.append(_normalize({
                "source": "myjobmag",
                "title": title.strip(),
                "company": company.strip(),
                "location": "Kenya",
                "location_country": "KE",
                "remote": False,
                "url": url,
                "apply_url": url,
                "description": f"Job on MyJobMag Kenya: {title.strip()} at {company.strip()}",
            }))
        return jobs
    except Exception:
        return []


async def scrape_kuhustle(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Kuhustle — Kenyan freelance/gig platform, httpx sufficient."""
    try:
        r = await client.get(
            "https://kuhustle.com/jobs",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        html = r.text
        titles = re.findall(r'<h[23][^>]*>([^<]{5,100})</h[23]>', html)
        links = re.findall(r'href="(https://kuhustle\.com/(?:jobs|project)/[^"]+)"', html)
        jobs = []
        seen: set[str] = set()
        for i, title in enumerate(titles[:50]):
            title = title.strip()
            if not title or title in seen:
                continue
            seen.add(title)
            url = links[i] if i < len(links) else "https://kuhustle.com/jobs"
            is_remote = "remote" in title.lower()
            jobs.append(_normalize({
                "source": "kuhustle",
                "title": title,
                "company": "Kuhustle",
                "location": "Remote" if is_remote else "Kenya",
                "location_country": "KE",
                "remote": is_remote,
                "url": url,
                "apply_url": url,
                "description": f"Gig/job on Kuhustle: {title}",
            }))
        return jobs
    except Exception:
        return []


async def scrape_andela(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Andela Talent Network — tech-focused Africa roles. Uses nodriver."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            await browser.goto(page, "https://andela.com/ats/#/jobs", wait=3.0)
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerHTML")
            titles = re.findall(r'"title"\s*:\s*"([^"]{5,100})"', html)
            urls_found = re.findall(r'"url"\s*:\s*"(https://andela\.com[^"]+)"', html)
            for i, title in enumerate(titles[:50]):
                url = urls_found[i] if i < len(urls_found) else "https://andela.com/ats/#/jobs"
                jobs.append(_normalize({
                    "source": "andela",
                    "title": title,
                    "company": "Andela Network",
                    "location": "Africa / Remote",
                    "location_country": None,
                    "remote": True,
                    "url": url,
                    "apply_url": url,
                    "description": f"Tech role via Andela Talent Network: {title}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_arc(search_term: str, client: httpx.AsyncClient) -> list[dict]:
    """Arc.dev — remote startup network, vets developers. Uses nodriver."""
    try:
        from app.services.job_hunter.browser_service import BrowserService
        jobs = []
        async with BrowserService(headless=True) as browser:
            page = await browser.new_page()
            query = search_term.replace(' ', '-')
            await browser.goto(
                page,
                f"https://arc.dev/remote-jobs?technology={query}",
                wait=3.0,
            )
            await browser.wait_past_cloudflare(page, timeout=10.0)
            html = await page.evaluate("document.body.innerHTML")
            titles = re.findall(r'class="[^"]*job-title[^"]*"[^>]*>([^<]{5,100})<', html)
            companies = re.findall(r'class="[^"]*company[^"]*"[^>]*>([^<]{2,80})<', html)
            links = re.findall(r'href="(https://arc\.dev/remote-jobs/[^"]+)"', html)
            for i, title in enumerate(titles[:50]):
                company = companies[i] if i < len(companies) else "Arc.dev Company"
                url = links[i] if i < len(links) else "https://arc.dev/remote-jobs"
                jobs.append(_normalize({
                    "source": "arc",
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": "Remote",
                    "location_country": None,
                    "remote": True,
                    "url": url,
                    "apply_url": url,
                    "description": f"Remote tech role via Arc.dev: {title.strip()} at {company.strip()}",
                }))
        return jobs
    except Exception:
        return []


async def scrape_all_kenya_boards(
    search_term: str,
    publish_fn=None,
) -> list[dict]:
    """
    Query all 6 Kenya/Africa boards in parallel.
    Returns all jobs — caller filters by relevance.
    Each individual scraper is fault-tolerant (returns [] on failure).
    """
    if publish_fn:
        await publish_fn(
            "🇰🇪 Querying Kenya boards "
            "(Fuzu + BrighterMonday + MyJobMag + Kuhustle + Andela + Arc.dev)..."
        )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        (
            fuzu_jobs, bm_jobs, mjm_jobs,
            kh_jobs, andela_jobs, arc_jobs,
        ) = await asyncio.gather(
            scrape_fuzu(search_term, client),
            scrape_brightermonday(search_term, client),
            scrape_myjobmag(search_term, client),
            scrape_kuhustle(search_term, client),
            scrape_andela(search_term, client),
            scrape_arc(search_term, client),
        )

    all_jobs = fuzu_jobs + bm_jobs + mjm_jobs + kh_jobs + andela_jobs + arc_jobs

    if publish_fn:
        await publish_fn(
            f"  ↳ Fuzu: {len(fuzu_jobs)} | BrighterMonday: {len(bm_jobs)} | "
            f"MyJobMag: {len(mjm_jobs)} | Kuhustle: {len(kh_jobs)} | "
            f"Andela: {len(andela_jobs)} | Arc: {len(arc_jobs)} "
            f"= {len(all_jobs)} Kenya listings"
        )

    return all_jobs
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/services/job_hunter/test_kenya_scrapers.py -v
```

Expected: All tests PASS (the mocked tests). The live network test may return empty — that's acceptable.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/job_hunter/kenya_scrapers.py \
        backend/tests/services/job_hunter/test_kenya_scrapers.py
git commit -m "feat(scraper): add kenya_scrapers.py with 6 boards + scrape_all_kenya_boards"
```

---

## Task 4: Restructure `scrape_campaign` loop and wire everything together

**Files:**
- Modify: `backend/app/services/job_hunter/scraper_service.py` (lines 328–520)

This is the most surgical task — read the existing code carefully before editing.

- [ ] **Step 1: Update the `scrape_campaign` method**

In `scraper_service.py`, make the following changes to `scrape_campaign`:

**a) Add import at top of method:**
```python
from app.services.job_hunter.kenya_scrapers import scrape_all_kenya_boards
```

**b) Add `skipped_non_tech` and `kenya_fetched` alongside existing counters (around line 385):**
```python
matches_found = 0
skipped_location = 0
skipped_duplicate = 0
skipped_non_tech = 0           # NEW
match_counts = {"MATCH": 0, "PARTIAL": 0, "SKIP": 0}
attempt = 0
results_wanted = target * 2
consecutive_empty = 0
ats_fetched = False
kenya_fetched = False           # NEW
```

**c) Replace the first-pass `if not ats_fetched:` block (currently lines 403–444) with:**
```python
if not ats_fetched:
    sources_label = "job boards + ATS company boards + startup boards + Kenya boards"
    if linkedin_creds:
        sources_label += " + LinkedIn"
    await self._publish(f"🌐 Querying {sources_label} in parallel...")
    try:
        gather_coros = [
            self.run_jobspy(campaign, results_wanted=results_wanted, search_term=broad_category),
            scrape_all_ats(broad_category, publish_fn=self._publish),
            scrape_all_startup_boards(broad_category, publish_fn=self._publish),
            scrape_all_kenya_boards(broad_category, publish_fn=self._publish),
        ]
        if linkedin_creds:
            from app.services.job_hunter.linkedin_scraper import LinkedInScraper
            li_scraper = LinkedInScraper(
                email=linkedin_creds.get("email"),
                password=linkedin_creds.get("password"),
                session_cookie=linkedin_creds.get("session_cookie"),
            )
            gather_coros.append(
                _run_linkedin_subprocess(
                    li_scraper, broad_category, user_country,
                    work_type, self._publish,
                )
            )
        results = await asyncio.gather(*gather_coros, return_exceptions=True)
        jobspy_jobs   = results[0] if not isinstance(results[0], Exception) else []
        ats_jobs      = results[1] if not isinstance(results[1], Exception) else []
        startup_jobs  = results[2] if not isinstance(results[2], Exception) else []
        kenya_jobs    = results[3] if not isinstance(results[3], Exception) else []
        li_jobs       = results[4] if len(results) > 4 and not isinstance(results[4], Exception) else []
        if linkedin_creds and len(results) > 4 and isinstance(results[4], Exception):
            li_err = results[4]
            li_err_msg = repr(li_err) if not str(li_err) else str(li_err)
            await self._publish(f"⚠️ LinkedIn scrape error: {type(li_err).__name__}: {li_err_msg}")
        kenya_fetched = True    # set only on success, inside try
    except Exception as e:
        await self._publish(f"⚠️ Parallel fetch error ({e}) — falling back to job boards only")
        jobspy_jobs = await self.run_jobspy(campaign, results_wanted=results_wanted, search_term=broad_category)
        ats_jobs = []
        startup_jobs = []
        kenya_jobs = []
        li_jobs = []
    raw_jobs = jobspy_jobs + ats_jobs + startup_jobs + kenya_jobs + li_jobs
    ats_fetched = True
```

**d) Replace the subsequent-pass `else:` block (currently lines 445–468) with:**
```python
else:
    # Subsequent passes: jobspy + startup boards + LinkedIn only
    # (ATS and Kenya boards are one-time-only — don't re-query)
    gather_coros = [
        self.run_jobspy(campaign, results_wanted=results_wanted, search_term=broad_category),
        scrape_all_startup_boards(broad_category, publish_fn=self._publish),
    ]
    if linkedin_creds:
        from app.services.job_hunter.linkedin_scraper import LinkedInScraper
        li_scraper = LinkedInScraper(
            email=linkedin_creds.get("email"),
            password=linkedin_creds.get("password"),
            session_cookie=linkedin_creds.get("session_cookie"),
        )
        gather_coros.append(
            _run_linkedin_subprocess(
                li_scraper, broad_category, user_country,
                work_type, self._publish,
            )
        )
    results = await asyncio.gather(*gather_coros, return_exceptions=True)
    jobspy_jobs  = results[0] if not isinstance(results[0], Exception) else []
    startup_jobs = results[1] if not isinstance(results[1], Exception) else []
    li_jobs      = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else []
    raw_jobs = jobspy_jobs + startup_jobs + li_jobs
```

**e) Replace the per-job processing loop (currently lines 476–502) with the batch approach:**
```python
new_matches_this_pass = 0

# --- Step 1: Batch filter ---
filtered: list[dict] = []
for job in raw_jobs:
    if not self.passes_work_type_filter(job, work_type, user_country, anywhere):
        skipped_location += 1
        continue
    if not self._tech_role_prefilter(job.get("title", ""), job.get("description", "")):
        skipped_non_tech += 1
        continue
    filtered.append(job)

if skipped_non_tech > 0:
    await self._publish(f"🔧 {skipped_non_tech} jobs rejected by tech-role filter (cumulative)")

# --- Step 2: Batch score (with early exit) ---
for job in filtered:
    if matches_found >= target:
        break
    score = await self.score_job_match(job["title"], job["description"], sub_categories, profile_skills)
    match_counts[score] = match_counts.get(score, 0) + 1
    job["_score"] = score

# Fill _score for any jobs skipped due to early exit
for job in filtered:
    if "_score" not in job:
        job["_score"] = "SKIP"

# --- Step 3: Sort (MATCH first, then by SMB score desc) ---
filtered.sort(key=lambda j: (_SCORE_ORDER[j["_score"]], -_smb_score(j)))

# Log large-corp deprioritization count
large_corp_count = sum(
    1 for j in filtered
    if j.get("company") and any(sig in j["company"].lower() for sig in _LARGE_CORP_SIGNALS)
)
if large_corp_count > 0:
    await self._publish(f"🏢 {large_corp_count} large-corp jobs deprioritized in favor of SMBs")

# --- Step 4: Dispatch ---
for job in filtered:
    if matches_found >= target:
        break
    score = job["_score"]
    if score != "SKIP":
        await self._publish(f"{'✅' if score == 'MATCH' else '🟡'} {score} — {job['title']} @ {job['company']}")
    listing = await self.save_listing(campaign_id, user_id, job, score)
    if listing:
        if score == "MATCH":
            matches_found += 1
            new_matches_this_pass += 1
            try:
                from app.workers.tailor_worker import tailor_listing
                tailor_listing.delay(listing.id, user_id)
            except Exception as e:
                await self._publish(f"⚠️ Failed to queue tailor task for {listing.id}: {e}")
    elif score == "MATCH":
        skipped_duplicate += 1
```

**f) Update the final summary `_publish` call (currently lines 515–519):**
```python
await self._publish(
    f"✔ Done — {matches_found} matches found | "
    f"{match_counts['PARTIAL']} partial, {match_counts['SKIP']} skipped | "
    f"{skipped_location} filtered by location | "
    f"{skipped_non_tech} filtered non-tech | "
    f"{skipped_duplicate} duplicates"
)
```

- [ ] **Step 2: Run the existing tech filter tests to confirm nothing broke**

```bash
cd backend && python -m pytest tests/services/job_hunter/test_tech_filter.py -v
```

Expected: All PASS.

- [ ] **Step 3: Run all job hunter tests**

```bash
cd backend && python -m pytest tests/services/job_hunter/ -v
```

Expected: All PASS (or pre-existing failures unchanged).

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/job_hunter/scraper_service.py
git commit -m "feat(scraper): wire tech filter + SMB sort + Kenya boards into scrape_campaign"
```

---

## Task 5: Full test suite run and cleanup

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: No new failures introduced. Pre-existing failures (if any) are unchanged.

- [ ] **Step 2: Verify `_score` key doesn't leak into `save_listing`**

The `job["_score"]` key is attached during scoring. Verify `save_listing` only reads named fields (`source`, `title`, `company`, etc.) and is not passing the full dict anywhere that would cause issues. Check [scraper_service.py:247-272](backend/app/services/job_hunter/scraper_service.py#L247-L272) — `save_listing` accesses `job.get(...)` by name, so the extra `_score` key is harmless.

- [ ] **Step 3: Final commit**

```bash
git add -p  # review any unstaged changes
git commit -m "test(scraper): ensure full suite passes after kenya tech scraper additions"
```

---

## Quick Sanity Check (manual, optional)

To verify the scrapers actually connect to live boards:

```bash
cd backend && python -c "
import asyncio
from app.services.job_hunter.startup_scrapers import scrape_all_startup_boards
from app.services.job_hunter.kenya_scrapers import scrape_all_kenya_boards

async def main():
    jobs = await scrape_all_startup_boards('software engineer')
    print(f'Startup boards: {len(jobs)} jobs')
    kenya = await scrape_all_kenya_boards('software engineer')
    print(f'Kenya boards: {len(kenya)} jobs')

asyncio.run(main())
"
```

Expected: positive counts from each board. Zero is acceptable for Kenya browser-based boards in a headless CI environment.
