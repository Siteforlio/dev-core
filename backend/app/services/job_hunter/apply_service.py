# backend/app/services/job_hunter/apply_service.py
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pg.job_hunter import Application, JobListing

ATS_PATTERNS = {
    "greenhouse": ["boards.greenhouse.io", "grnh.se"],
    "lever": ["jobs.lever.co", "lever.co"],
    "ashby": ["jobs.ashbyhq.com", "ashbyhq.com"],
    "workday": ["myworkdayjobs.com", "workday.com"],
    "skip": ["linkedin.com/jobs/apply"],
}

class ApplyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def detect_ats(self, url: str) -> str:
        url_lower = url.lower()
        for ats, patterns in ATS_PATTERNS.items():
            if any(p in url_lower for p in patterns):
                return ats
        return "generic"

    async def submit_application(self, application_id: str) -> bool:
        result = await self.db.execute(select(Application).where(Application.id == application_id))
        application = result.scalar_one_or_none()
        if not application:
            return False

        listing_result = await self.db.execute(select(JobListing).where(JobListing.id == application.job_listing_id))
        listing = listing_result.scalar_one_or_none()
        if not listing or not listing.apply_url:
            application.status = "failed"
            await self.db.commit()
            return False

        ats = self.detect_ats(listing.apply_url)
        if ats == "skip":
            application.status = "failed"
            await self.db.commit()
            return False

        try:
            success = await asyncio.to_thread(
                self._fill_form_sync,
                listing.apply_url, ats, application.form_answers or {},
                application.cover_letter or "",
            )
            application.status = "applied" if success else "failed"
            listing.status = "applied" if success else "failed"
        except Exception:
            application.status = "failed"
            listing.status = "failed"
        await self.db.commit()
        return application.status == "applied"

    def _fill_form_sync(self, apply_url: str, ats: str, form_answers: dict, cover_letter: str) -> bool:
        """Playwright form filling — runs in thread via asyncio.to_thread."""
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            try:
                page.goto(apply_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
                # Fill common fields present across most ATS
                for selector, value in [
                    ('input[name*="name"], input[placeholder*="name"]', form_answers.get("full_name", "")),
                    ('input[name*="email"], input[type="email"]', form_answers.get("email", "")),
                    ('input[name*="phone"], input[type="tel"]', form_answers.get("phone", "")),
                    ('input[name*="linkedin"]', form_answers.get("linkedin_url", "")),
                    ('input[name*="github"]', form_answers.get("github_url", "")),
                    ('textarea[name*="cover"], textarea[placeholder*="cover"]', cover_letter),
                ]:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible(timeout=2000):
                            el.fill(value)
                    except Exception:
                        pass
                # Submit
                submit = page.locator('button[type="submit"], input[type="submit"]').first
                if submit.is_visible(timeout=3000):
                    submit.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                return True
            except Exception:
                return False
            finally:
                browser.close()
