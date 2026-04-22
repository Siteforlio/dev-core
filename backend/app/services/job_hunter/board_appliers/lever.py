# board_appliers/lever.py
"""
Lever ATS applier — jobs.lever.co

Single-page form with known stable field names.
Seed structural fields, then AI-fill custom questions.
"""
from __future__ import annotations
import asyncio
import json
import logging

from .base import BaseBoardApplier, ApplyResult

logger = logging.getLogger(__name__)


class LeverApplier(BaseBoardApplier):
    board_id = "lever"

    async def apply(self, url: str, ctx: dict, browser, page) -> ApplyResult:
        from app.services.job_hunter.apply_service import _SCAN_FIELDS_JS, _make_fill_js

        # 1. Seed stable fields
        for sel, val in [
            ('input[name="name"]',                             ctx["full_name"]),
            ('input[name="email"]',                            ctx["email"]),
            ('input[name="phone"]',                            ctx["phone"]),
            ('input[name*="linkedin"]',                        ctx["linkedin_url"]),
            ('input[name*="github"]',                          ctx["github_url"]),
            ('input[name*="website"], input[name*="portfolio"]', ctx["portfolio_url"]),
        ]:
            if not val:
                continue
            try:
                await browser.type_human(page, sel, val)
            except Exception:
                pass

        if ctx["resume_pdf"]:
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                await asyncio.sleep(1.0)
            except Exception:
                pass

        if ctx["cover_letter"]:
            try:
                await browser.fill_field(
                    page,
                    'textarea[name*="comments"], textarea[name*="cover"]',
                    ctx["cover_letter"],
                )
            except Exception:
                pass

        # 2. AI-fill custom fields
        await asyncio.sleep(1.0)
        raw = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
        fields: list[dict] = json.loads(raw) if isinstance(raw, str) else (raw or [])
        fillable = [f for f in fields if f.get("label") or f.get("options")]
        if fillable:
            from app.services.job_hunter.apply_service import ApplyService
            answers = await ApplyService._ai_map_fields_static(fillable, ctx)
            for field in fillable:
                idx      = str(field.get("idx", ""))
                value    = answers.get(idx, "")
                selector = field.get("selector", "")
                ftype    = field.get("type", "text")
                if not value or selector.startswith("__idx__"):
                    continue
                try:
                    if ftype == "file" and ctx["resume_pdf"]:
                        await browser.upload_file(page, selector, ctx["resume_pdf"])
                    elif len(str(value)) > 80:
                        await browser.fill_field(page, selector, str(value))
                    else:
                        await page.evaluate(_make_fill_js(selector, str(value), ftype))
                    await asyncio.sleep(0.15)
                except Exception:
                    pass

        # 3. Submit
        clicked = await browser.click_human(page, 'button[type="submit"]')
        if not clicked:
            return ApplyResult.fail("submit button not found")
        await page.sleep(3)
        url_after = await browser.current_url(page)
        from app.services.job_hunter.apply_service import ApplyService
        if await ApplyService._is_success_page_static(browser, page, url_after):
            return ApplyResult.ok()
        return ApplyResult.fail(f"success not detected — url: {url_after}")
