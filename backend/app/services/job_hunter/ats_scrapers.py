# backend/app/services/job_hunter/ats_scrapers.py
"""
Public ATS API scrapers — no auth, no credentials required.
Greenhouse, Lever, and Ashby all expose public job board APIs by design.
"""
import asyncio
import httpx

# ~200 major tech companies across Greenhouse, Lever, Ashby
GREENHOUSE_SLUGS = [
    # Payments & Fintech
    "stripe", "plaid", "brex", "chime", "robinhood", "coinbase", "kraken",
    "affirm", "marqeta", "adyen", "checkout", "patreon", "recurly",
    # AI & ML
    "openai", "anthropic", "scale", "huggingface", "cohere", "mistral",
    "perplexity", "character", "inflection", "runway", "elevenlabs",
    "replicate", "modal", "together", "groq", "cerebras",
    # Developer Tools & Infra
    "hashicorp", "mongodb", "cockroachlabs", "planetscale",
    "datadog", "newrelic", "pagerduty", "grafana", "influxdata",
    "elastic", "splunk", "sumologic", "dynatrace",
    "cloudflare", "fastly", "akamai", "netlify",
    "confluent", "dbt-labs", "airbyte", "fivetran", "starburst",
    "supabase", "retool", "airplane",
    # Collaboration & Productivity
    "notion", "figma", "linear", "asana", "airtable", "coda",
    "miro", "loom", "descript", "canva",
    "box", "dropbox", "docusign",
    "clickup", "monday",
    # Consumer & Social
    "airbnb", "databricks", "discord", "reddit", "twitch",
    "roblox", "unity", "epicgames",
    "duolingo", "coursera",
    # Commerce & Ops
    "shopify", "squarespace", "webflow", "framer",
    "doordash", "instacart", "lyft", "waymo",
    "toast", "square", "lightspeed",
    # Security
    "okta", "crowdstrike", "sentinelone", "lacework", "snyk",
    "1password", "dashlane",
    # HR & Remote Work
    "lattice", "rippling", "deel", "remote", "gusto", "workos",
    # Marketing & Analytics
    "twilio", "sendgrid", "segment", "amplitude", "mixpanel",
    "zendesk", "intercom", "freshworks", "hubspot",
    "pendo", "productboard", "sprig",
    "census", "hightouch", "rudderstack",
    # Health & Bio
    "benchling", "veeva", "tempus", "recursion",
    # Other
    "palantir", "anduril", "samsara",
    "vercel", "tabnine", "replit",
]

LEVER_SLUGS = [
    # Big Tech (many use Lever)
    "netflix", "atlassian", "mozilla",
    # Dev Tools
    "gitlab", "jetbrains", "postman",
    "grafana", "posthog", "sentry",
    "deno", "railway", "render",
    "neon", "turso", "upstash",
    # Infra & Cloud
    "netlify", "cloudflare",
    "liveblocks", "ably", "pusher",
    # Comms & Messaging
    "resend", "loops", "customer-io",
    "appcues", "chameleon",
    "heap", "fullstory", "logrocket",
    # Productivity
    "linear", "shortcut",
    "cal", "savvycal", "reclaim",
    "pitch", "grain",
    # Security & Compliance
    "vanta", "drata", "secureframe",
    # Sustainability
    "watershed",
    # HR & Payroll
    "oyster", "personio", "hibob", "factorial",
    # Finance
    "ramp", "mercury", "brex",
    # Other
    "brave", "proton",
]

ASHBY_SLUGS = [
    # AI Labs
    "openai", "anthropic", "mistral", "cohere", "together-ai",
    "inflection", "adept", "imbue",
    "langchain", "langfuse", "braintrust", "weights-biases",
    # AI Coding
    "cursor", "codeium", "sourcegraph", "continue",
    # Terminal & Dev UX
    "warp", "fig", "zed",
    # Open Source SaaS
    "plane", "appflowy", "twenty", "erxes",
    # DB & Backend
    "supabase", "neon", "convex",
    "turso", "electric-sql",
    # Cloud & Serverless
    "fly-io", "modal", "beam", "porter",
    # Comms & Automation
    "trigger-dev", "inngest", "temporal",
    "resend", "loops",
    # Scheduling & Forms
    "cal-com", "formbricks", "documenso",
    # CRM & Sales
    "attio", "clay", "apollo",
    # Billing
    "lago", "hyperline", "orb",
    # Analytics & BI
    "metabase", "evidence", "rill", "cube",
    # Data Engineering
    "prefect", "dagster", "astronomer",
    # Vector & AI Infra
    "weaviate", "qdrant", "chroma", "pinecone",
    # ML Serving
    "bentoml", "anyscale", "ray",
    # Security
    "boundary", "teleport",
    # Other
    "linear", "highlight",
]

_HTTP_TIMEOUT = 10.0
_MAX_CONCURRENT = 20  # parallel requests per ATS


def _normalize(job: dict) -> dict:
    """Ensure all jobs have the same shape before returning."""
    return {
        "source": job.get("source", "ats"),
        "title": (job.get("title") or "").strip(),
        "company": (job.get("company") or "").strip(),
        "location": job.get("location"),
        "location_country": job.get("location_country"),
        "remote": job.get("remote", False),
        "url": job.get("url", ""),
        "apply_url": job.get("apply_url") or job.get("url", ""),
        "description": (job.get("description") or "")[:5000],
    }


async def scrape_greenhouse(slug: str, client: httpx.AsyncClient) -> list[dict]:
    try:
        r = await client.get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        jobs = []
        for j in data.get("jobs", []):
            location = j.get("location", {}).get("name", "") or ""
            remote = "remote" in location.lower()
            country = ""
            if "," in location:
                country = location.split(",")[-1].strip()[:2].upper()
            content = j.get("content", "") or ""
            job_id  = j.get("id", "")
            # Use canonical Greenhouse job-boards URL so _detect_form_url can
            # rewrite it directly to the embed form, even when absolute_url is
            # a company-specific SPA page (e.g. stripe.com/jobs/search?gh_jid=…)
            canonical_url = (
                f"https://job-boards.greenhouse.io/{slug}/jobs/{job_id}"
                if job_id else j.get("absolute_url", "")
            )
            jobs.append(_normalize({
                "source": "greenhouse",
                "title": j.get("title", ""),
                "company": slug.replace("-", " ").title(),
                "location": location or None,
                "location_country": country or None,
                "remote": remote,
                "url": canonical_url,
                "apply_url": canonical_url,
                "description": content[:5000],
            }))
        return jobs
    except Exception:
        return []


async def scrape_lever(slug: str, client: httpx.AsyncClient) -> list[dict]:
    try:
        r = await client.get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json",
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        jobs = []
        for j in r.json():
            location = j.get("categories", {}).get("location", "") or ""
            remote = "remote" in location.lower()
            lists = j.get("lists", [])
            description = " ".join(l.get("content", "") for l in lists)
            jobs.append(_normalize({
                "source": "lever",
                "title": j.get("text", ""),
                "company": slug.replace("-", " ").title(),
                "location": location or None,
                "location_country": None,
                "remote": remote,
                "url": j.get("hostedUrl", ""),
                "apply_url": j.get("applyUrl", "") or j.get("hostedUrl", ""),
                "description": description[:5000],
            }))
        return jobs
    except Exception:
        return []


_ASHBY_GQL = """
query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
    jobBoard: jobBoardWithTeams(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
        jobPostings { id title }
    }
}
"""

async def scrape_ashby(slug: str, client: httpx.AsyncClient) -> list[dict]:
    try:
        r = await client.post(
            "https://jobs.ashbyhq.com/api/non-user-graphql",
            json={
                "operationName": "ApiJobBoardWithTeams",
                "variables": {"organizationHostedJobsPageName": slug},
                "query": _ASHBY_GQL,
            },
            headers={"content-type": "application/json"},
            timeout=_HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        board = ((r.json().get("data") or {}).get("jobBoard")) or {}
        postings = board.get("jobPostings") or []
        jobs = []
        for j in postings:
            job_url = f"https://jobs.ashbyhq.com/{slug}/{j['id']}"
            jobs.append(_normalize({
                "source": "ashby",
                "title": j.get("title", ""),
                "company": slug.replace("-", " ").title(),
                "location": None,
                "location_country": None,
                "remote": None,
                "url": job_url,
                # /application goes directly to the form, not the job description
                "apply_url": f"{job_url}/application",
                "description": "",
            }))
        return jobs
    except Exception:
        return []


async def scrape_all_ats(search_term: str, publish_fn=None) -> list[dict]:
    """
    Scrape Greenhouse, Lever, and Ashby in parallel.
    Returns all jobs — caller filters by relevance.
    search_term is used for logging only; ATS APIs return all open roles.
    """
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async def bounded(coro):
        async with semaphore:
            return await coro

    async with httpx.AsyncClient(follow_redirects=True) as client:
        gh_tasks = [bounded(scrape_greenhouse(s, client)) for s in GREENHOUSE_SLUGS]
        lv_tasks = [bounded(scrape_lever(s, client)) for s in LEVER_SLUGS]
        ab_tasks = [bounded(scrape_ashby(s, client)) for s in ASHBY_SLUGS]

        if publish_fn:
            await publish_fn(
                f"🏢 Querying {len(GREENHOUSE_SLUGS)} Greenhouse + "
                f"{len(LEVER_SLUGS)} Lever + {len(ASHBY_SLUGS)} Ashby companies in parallel..."
            )

        gh_results, lv_results, ab_results = await asyncio.gather(
            asyncio.gather(*gh_tasks),
            asyncio.gather(*lv_tasks),
            asyncio.gather(*ab_tasks),
        )

    all_jobs: list[dict] = []
    for batch in [*gh_results, *lv_results, *ab_results]:
        all_jobs.extend(batch)

    if publish_fn:
        gh_count = sum(len(r) for r in gh_results)
        lv_count = sum(len(r) for r in lv_results)
        ab_count = sum(len(r) for r in ab_results)
        await publish_fn(
            f"  ↳ Greenhouse: {gh_count} | Lever: {lv_count} | Ashby: {ab_count} "
            f"= {len(all_jobs)} total ATS listings"
        )

    return all_jobs
