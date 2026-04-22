# board_appliers/arc.py
"""
Arc.dev applier — arc.dev

Arc.dev is a vetted remote talent network.
Apply flow: job detail → "Apply" button → profile-based apply form
(name, email, LinkedIn, GitHub, portfolio, cover note, desired salary).

No account required for the initial application form.
"""
from __future__ import annotations
import asyncio
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)


class ArcApplier(BaseBoardApplier):
    board_id = "arc"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        await asyncio.sleep(1.5)

        # Click Apply button if on job listing page
        try:
            await browser.click_human(
                page,
                'button:has-text("Apply"), a:has-text("Apply Now"), '
                '[data-testid*="apply-button"], .apply-button'
            )
            await asyncio.sleep(2.0)
        except Exception:
            pass

        # Seed known stable fields
        for sel, val in [
            ('input[name*="name"], input[placeholder*="name" i]',      ctx["full_name"]),
            ('input[type="email"]',                                      ctx["email"]),
            ('input[type="tel"], input[name*="phone"]',                  ctx["phone"]),
            ('input[name*="linkedin"], input[placeholder*="linkedin" i]', ctx["linkedin_url"]),
            ('input[name*="github"],  input[placeholder*="github" i]',   ctx["github_url"]),
            ('input[name*="portfolio"], input[name*="website"]',          ctx["portfolio_url"]),
        ]:
            if not val:
                continue
            try:
                await browser.type_human(page, sel, val)
            except Exception:
                pass

        # Resume upload
        if ctx["resume_pdf"]:
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                await asyncio.sleep(1.0)
            except Exception:
                pass

        # Cover letter / motivation
        if ctx["cover_letter"]:
            try:
                await browser.fill_field(page, 'textarea', ctx["cover_letter"])
            except Exception:
                pass

        # AI-fill remaining fields
        from app.services.job_hunter.apply_service import ApplyService, _SCAN_FIELDS_JS, _make_fill_js
        import json
        raw = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
        fields: list[dict] = json.loads(raw) if isinstance(raw, str) else (raw or [])
        fillable = [f for f in fields if f.get("label") or f.get("options")]
        if fillable:
            answers = await ApplyService._ai_map_fields_static(fillable, ctx)
            for field in fillable:
                value    = answers.get(str(field.get("idx", "")), "")
                selector = field.get("selector", "")
                ftype    = field.get("type", "text")
                if not value or selector.startswith("__idx__"):
                    continue
                try:
                    if len(str(value)) > 80:
                        await browser.fill_field(page, selector, str(value))
                    else:
                        await page.evaluate(_make_fill_js(selector, str(value), ftype))
                    await asyncio.sleep(0.15)
                except Exception:
                    pass

        # Submit
        clicked = await browser.click_human(page, 'button[type="submit"], button:has-text("Submit")')
        if not clicked:
            return ApplyResult.fail("submit button not found")

        await page.sleep(3)
        url_after = await browser.current_url(page)
        if await ApplyService._is_success_page_static(browser, page, url_after):
            return ApplyResult.ok()
        return ApplyResult.fail(f"success not detected — url: {url_after}")
