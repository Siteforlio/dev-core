# board_appliers/lever.py
"""
Lever ATS applier — jobs.lever.co

Lever forms are single-page with stable field names and standard <select>
elements (no React Select). Strategy:
  1. Seed structural fields via known selectors
  2. Upload resume
  3. Pre-read real options from any custom dropdowns
  4. Gemini maps all fields to exact values
  5. Fill — comboboxes via _interact_combobox, standard via _make_fill_js
  6. Submit and verify confirmation page
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
        from app.services.job_hunter.apply_service import (
            ApplyService, _SCAN_FIELDS_JS, _make_fill_js,
        )

        # ── 1. Seed stable structural fields ─────────────────────────────────
        for sel, val in [
            ('input[name="name"]',                               ctx.get("full_name", "")),
            ('input[name="email"]',                              ctx.get("email", "")),
            ('input[name="phone"]',                              ctx.get("phone", "")),
            ('input[name*="linkedin"], input[name*="LinkedIn"]', ctx.get("linkedin_url", "")),
            ('input[name*="github"],   input[name*="GitHub"]',   ctx.get("github_url", "")),
            ('input[name*="website"],  input[name*="portfolio"]', ctx.get("portfolio_url", "")),
        ]:
            if not val:
                continue
            try:
                await browser.type_human(page, sel, val)
            except Exception:
                pass

        # ── 2. Resume upload ──────────────────────────────────────────────────
        resume_uploaded = False
        if ctx.get("resume_pdf"):
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                resume_uploaded = True
                await asyncio.sleep(1.0)
            except Exception:
                pass

        # ── 3. Cover letter ───────────────────────────────────────────────────
        if ctx.get("cover_letter"):
            for csel in [
                'textarea[name*="comments"]',
                'textarea[name*="cover"]',
                'textarea[name*="letter"]',
                '#cover-letter',
            ]:
                try:
                    await browser.fill_field(page, csel, ctx["cover_letter"])
                    break
                except Exception:
                    pass

        # ── 4. Scan all fields ────────────────────────────────────────────────
        await asyncio.sleep(1.0)
        raw = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
        fields: list[dict] = json.loads(raw) if isinstance(raw, str) else (raw or [])
        fillable = [f for f in fields if not str(f.get("selector", "")).startswith("__idx__")]

        if fillable:
            # ── 4a. Detect custom dropdowns ───────────────────────────────────
            combobox_selectors: set[str] = set()
            for i, f in enumerate(fields):
                nxt = fields[i + 1] if i + 1 < len(fields) else None
                if (nxt and str(nxt.get("selector", "")).startswith("__idx__")
                        and nxt.get("required")):
                    sel = f.get("selector", "")
                    if sel and not sel.startswith("__idx__"):
                        combobox_selectors.add(sel)

            # ── 4b. Pre-read real dropdown options ────────────────────────────
            if combobox_selectors:
                logger.info("lever: pre-reading %d combobox(es)", len(combobox_selectors))
                for field in fillable:
                    sel = field.get("selector", "")
                    if sel in combobox_selectors and not field.get("options"):
                        opts = await ApplyService._read_combobox_options_static(
                            browser, page, sel
                        )
                        if opts:
                            field["options"] = opts
                            logger.info("  [%s] options: %s",
                                        (field.get("label") or sel)[:40], opts[:6])

            # ── 4c. Gemini maps all fields → exact values ─────────────────────
            answers = await ApplyService._ai_map_fields_static(fillable, ctx)

            # ── 4d. Fill every field ──────────────────────────────────────────
            for field in fillable:
                idx      = str(field.get("idx", ""))
                value    = answers.get(idx, "")
                selector = field.get("selector", "")
                ftype    = field.get("type", "text")
                label    = (field.get("label") or "").strip()

                if not value or selector.startswith("__idx__"):
                    continue

                try:
                    if ftype == "file":
                        if ctx.get("resume_pdf") and not resume_uploaded:
                            await browser.upload_file(page, selector, ctx["resume_pdf"])
                            resume_uploaded = True
                    elif selector in combobox_selectors:
                        svc = ApplyService.__new__(ApplyService)
                        await svc._interact_combobox(browser, page, selector, str(value), label)
                    elif len(str(value)) > 80:
                        await browser.fill_field(page, selector, str(value))
                    else:
                        await page.evaluate(_make_fill_js(selector, str(value), ftype))
                    await asyncio.sleep(0.15)
                except Exception as e:
                    logger.debug("lever: fill failed [%s] %s: %s", ftype, label, e)

        # ── 5. Submit ─────────────────────────────────────────────────────────
        clicked = await browser.click_human(
            page, 'button[type="submit"], input[type="submit"], .application-submit button'
        )
        if not clicked:
            await browser.screenshot(page, "lever_no_submit")
            return ApplyResult.fail("submit button not found")

        await asyncio.sleep(4)
        url_after = await browser.current_url(page)
        if await ApplyService._is_success_page_static(browser, page, url_after):
            return ApplyResult.ok(f"submitted — {url_after}")
        return ApplyResult.fail(f"no confirmation after submit — url: {url_after}")
