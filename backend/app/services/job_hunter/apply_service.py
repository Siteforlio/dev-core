# backend/app/services/job_hunter/apply_service.py
"""
ApplyService — fills and submits job application forms using BrowserService (nodriver).

Supports:
  - Greenhouse  (boards.greenhouse.io)    — fast-path: known stable selectors
  - Lever       (jobs.lever.co)           — fast-path: known stable selectors
  - Ashby       (jobs.ashbyhq.com)        — fast-path: known stable selectors
  - Workday     (myworkdayjobs.com)       — universal filler (layout varies per company)
  - Generic     (any other ATS/careers page) — universal filler

Universal filler strategy (Workday + Generic):
  For each form step:
    1. JS DOM scan → structured field list [{label, type, selector, options}]
    2. One Haiku call → JSON mapping field_idx → value
    3. Apply answers (text / select / radio / checkbox / file)
    4. Click Next or Submit
    5. Repeat up to MAX_FORM_STEPS times
    6. Detect success via URL change or confirmation element
"""
import asyncio
import json
import logging
import re

from nodriver import cdp
from app.services.job_hunter.llm import call_llm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.pg.job_hunter import Application, JobListing, CampaignProfile
from app.services.job_hunter.browser_service import BrowserService

logger = logging.getLogger(__name__)

MAX_FORM_STEPS = 12   # maximum Next-button clicks before giving up

ATS_PATTERNS = {
    "greenhouse": ["boards.greenhouse.io", "grnh.se", "greenhouse.io"],
    "lever":      ["jobs.lever.co", "lever.co"],
    "ashby":      ["jobs.ashbyhq.com", "ashbyhq.com"],
    "workday":    ["myworkdayjobs.com", "workday.com"],
    "skip":       ["linkedin.com/jobs/apply"],
}

# JS that scans a page and returns all fillable fields with labels + selectors
_SCAN_FIELDS_JS = """
(function() {
    function getLabel(el) {
        if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
        if (el.placeholder) return el.placeholder.trim();
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) return lbl.innerText.trim();
        }
        const parentLabel = el.closest('label');
        if (parentLabel) {
            const clone = parentLabel.cloneNode(true);
            clone.querySelectorAll('input,select,textarea').forEach(n => n.remove());
            const txt = clone.innerText.trim();
            if (txt) return txt;
        }
        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const parts = labelledBy.split(' ');
            const txts = parts.map(id => {
                const e = document.getElementById(id);
                return e ? e.innerText.trim() : '';
            }).filter(Boolean);
            if (txts.length) return txts.join(' ');
        }
        const prev = el.previousElementSibling;
        if (prev && prev.tagName !== 'INPUT' && prev.innerText)
            return prev.innerText.trim();
        return el.name || el.getAttribute('data-automation-id') || '';
    }

    function uniqueSelector(el, idx) {
        if (el.id) return '#' + CSS.escape(el.id);
        if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
        return '__idx__' + idx;
    }

    const fields = [];
    const seen = new Set();

    // Radio groups — collect as single logical field
    const radioGroups = {};
    document.querySelectorAll('input[type=radio]:not([disabled])').forEach(el => {
        const grp = el.name || el.getAttribute('data-automation-id') || 'radio_' + el.id;
        if (!radioGroups[grp]) {
            radioGroups[grp] = {
                type: 'radio',
                name: grp,
                label: '',
                options: [],
                selector: 'input[type=radio][name="' + el.name + '"]',
            };
            // Label from fieldset legend or nearest group heading
            const fieldset = el.closest('fieldset');
            if (fieldset) {
                const leg = fieldset.querySelector('legend');
                if (leg) radioGroups[grp].label = leg.innerText.trim();
            }
            if (!radioGroups[grp].label) radioGroups[grp].label = getLabel(el);
        }
        const optLabel = getLabel(el) || el.value;
        radioGroups[grp].options.push({ value: el.value, label: optLabel });
    });
    Object.values(radioGroups).forEach((grp, i) => {
        fields.push({ idx: 'radio_' + i, ...grp });
    });

    // Checkboxes — each as standalone boolean field
    document.querySelectorAll('input[type=checkbox]:not([disabled])').forEach((el, i) => {
        const sel = uniqueSelector(el, 'cb_' + i);
        if (seen.has(sel)) return;
        seen.add(sel);
        fields.push({
            idx: 'cb_' + i,
            type: 'checkbox',
            label: getLabel(el),
            selector: sel,
            options: [],
        });
    });

    // Regular inputs, selects, textareas
    const regularEls = document.querySelectorAll(
        'input:not([type=hidden]):not([type=file]):not([type=radio]):not([type=checkbox]):not([disabled]),' +
        'select:not([disabled]),' +
        'textarea:not([disabled])'
    );
    regularEls.forEach((el, i) => {
        const sel = uniqueSelector(el, i);
        if (seen.has(sel)) return;
        seen.add(sel);
        const type = el.tagName === 'SELECT' ? 'select'
                   : el.tagName === 'TEXTAREA' ? 'textarea'
                   : (el.type || 'text');
        const options = el.tagName === 'SELECT'
            ? Array.from(el.options).map(o => o.text.trim()).filter(Boolean)
            : [];
        fields.push({
            idx: i,
            type,
            label: getLabel(el),
            selector: sel,
            options,
            required: el.required || false,
        });
    });

    return JSON.stringify(fields);
})()
"""

def _make_fill_js(selector: str, value: str, ftype: str) -> str:
    """
    Build a self-contained IIFE that fills one field.
    Values are JSON-escaped so any special chars (quotes, backslashes) are safe.
    nodriver's page.evaluate() cannot receive arguments, so we embed them directly.
    """
    import json as _json
    s = _json.dumps(selector)
    v = _json.dumps(value)
    f = _json.dumps(ftype)
    return f"""
(function() {{
    var selector = {s};
    var value = {v};
    var fieldType = {f};

    if (selector.startsWith('__idx__')) return false;

    if (fieldType === 'radio') {{
        var radios = document.querySelectorAll(selector);
        for (var i = 0; i < radios.length; i++) {{
            var r = radios[i];
            if (r.value === value || (r.getAttribute('aria-label') || '').trim() === value) {{
                r.click();
                return true;
            }}
        }}
        if (radios.length) {{ radios[0].click(); return true; }}
        return false;
    }}

    if (fieldType === 'checkbox') {{
        var el = document.querySelector(selector);
        if (!el) return false;
        var want = value === 'true' || value === true;
        if (el.checked !== want) el.click();
        return true;
    }}

    if (fieldType === 'select') {{
        var el = document.querySelector(selector);
        if (!el) return false;
        for (var i = 0; i < el.options.length; i++) {{
            var opt = el.options[i];
            if (opt.text.trim() === value || opt.value === value) {{
                el.value = opt.value;
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
        }}
        return false;
    }}

    // text / textarea / email / tel / number / date
    var el = document.querySelector(selector);
    if (!el) return false;
    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
              || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
    if (setter && setter.set) setter.set.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    return true;
}})()
"""


class ApplyService:
    def __init__(self, db: AsyncSession, headless: bool = True):
        self.db = db
        self._headless = headless

    def detect_ats(self, url: str) -> str:
        if not url:
            return "generic"
        url_lower = url.lower()
        for ats, patterns in ATS_PATTERNS.items():
            if any(p in url_lower for p in patterns):
                return ats
        return "generic"

    async def submit_application(self, application_id: str) -> bool:
        application = (await self.db.execute(
            select(Application).where(Application.id == application_id)
        )).scalar_one_or_none()
        if not application:
            logger.warning("submit_application: application %s not found", application_id)
            return False

        listing = (await self.db.execute(
            select(JobListing).where(JobListing.id == application.job_listing_id)
        )).scalar_one_or_none()
        if not listing or not listing.apply_url:
            application.status = "failed"
            await self.db.commit()
            return False

        profile = (await self.db.execute(
            select(CampaignProfile).where(CampaignProfile.campaign_id == listing.campaign_id)
        )).scalar_one_or_none()

        ats = self.detect_ats(listing.apply_url)
        logger.info("submit_application: %s | ats=%s | url=%s", application_id, ats, listing.apply_url)
        if ats == "skip":
            application.status = "skipped"
            await self.db.commit()
            return False

        ctx = self._build_context(application, profile, listing)

        try:
            success = await self._apply(listing.apply_url, ats, ctx, headless=self._headless)
        except Exception:
            logger.exception("submit_application: browser error for %s", application_id)
            success = False

        application.status = "applied" if success else "failed"
        listing.status = "applied" if success else "pending"
        await self.db.commit()
        logger.info("submit_application: %s → %s (%s)", application_id, application.status, ats)
        return success

    def _build_context(
        self,
        application: Application,
        profile: "CampaignProfile | None",
        listing: "JobListing | None" = None,
    ) -> dict:
        answers = application.form_answers or {}
        p = profile
        return {
            "full_name":     (p.full_name    if p else None) or answers.get("full_name", ""),
            "email":         (p.email        if p else None) or answers.get("email", ""),
            "phone":         (p.phone        if p else None) or answers.get("phone", ""),
            "city":          (p.city         if p else None) or "",
            "country":       (p.country      if p else None) or "",
            "linkedin_url":  (p.linkedin_url if p else None) or answers.get("linkedin_url", ""),
            "github_url":    (p.github_url   if p else None) or answers.get("github_url", ""),
            "portfolio_url": (p.portfolio_url if p else None) or "",
            "cover_letter":  application.cover_letter or "",
            "salary":        answers.get("salary", ""),
            "resume_pdf":    application.tailored_resume_pdf_url or "",
            "years_of_experience": (p.years_of_experience if p else None) or 0,
            "skills":        ", ".join((p.skills or [])[:15]) if p else "",
            "summary":       answers.get("summary", ""),
            "job_title":     (listing.title if listing else "") or "",
            "company":       (listing.company if listing else "") or "",
        }

    async def _detect_form_url(self, url: str) -> str | None:
        """
        Return the direct application form URL before Chrome opens.

        Priority:
          1. Greenhouse job-boards.greenhouse.io/COMPANY/jobs/JOB_ID
             → https://job-boards.greenhouse.io/embed/job_app?for=COMPANY&token=JOB_ID
          2. Old-format boards.greenhouse.io/COMPANY/jobs/JOB_ID
             → https://boards.greenhouse.io/embed/job_app?for=COMPANY&token=JOB_ID
          3. Already on a direct ATS domain (Lever, Ashby, Workday) → no rewrite needed
          4. Company career page with embedded ATS → HTTP-fetch and scan for iframe src
             or Greenhouse embed.js script tag
        """
        import httpx, re as _re
        from urllib.parse import urlparse, parse_qs

        # ── 1. Already on a Greenhouse embed form URL — nothing to do ─────────
        if '/embed/job_app' in url or '/embed/job_board/apply' in url:
            return None

        # ── 2. New-format Greenhouse SPA: job-boards.greenhouse.io/CO/jobs/ID ──
        #   The job description page requires clicking an Apply button (React SPA).
        #   Navigate directly to the embed form instead — no JS injection needed.
        m = re.search(r'job-boards\.greenhouse\.io/([^/?]+)/jobs/(\d+)', url)
        if m:
            form_url = (
                f"https://job-boards.greenhouse.io/embed/job_app"
                f"?for={m.group(1)}&token={m.group(2)}"
            )
            logger.info("_detect_form_url: new-format Greenhouse → %s", form_url)
            return form_url

        # ── 3. Old-format Greenhouse: boards.greenhouse.io/COMPANY/jobs/ID ────
        m = re.search(r'(?<!job-)boards\.greenhouse\.io/([^/?]+)/jobs/(\d+)', url)
        if m:
            form_url = (
                f"https://boards.greenhouse.io/embed/job_app"
                f"?for={m.group(1)}&token={m.group(2)}"
            )
            logger.info("_detect_form_url: old-format Greenhouse → %s", form_url)
            return form_url

        # ── 4. Already on a direct non-Greenhouse ATS domain — no rewrite ─────
        _ats_domains = [p for patterns in ATS_PATTERNS.values() for p in patterns
                        if p not in ("linkedin.com/jobs/apply", "greenhouse.io")]
        if any(d in url for d in _ats_domains):
            return None

        # ── 5. Company career page — HTTP-fetch and look for embedded ATS ─────
        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"},
            ) as hc:
                resp = await hc.get(url)
                html = resp.text

                # 5a. Iframe src already in static HTML
                m = _re.search(
                    r'<iframe[^>]+src="(https://[^"]*'
                    r'(?:greenhouse|lever|ashby|workday|myworkdayjobs)[^"]*)"',
                    html,
                )
                if m:
                    logger.info("_detect_form_url: iframe in HTML → %s", m.group(1)[:100])
                    return m.group(1)

                # 5b. Greenhouse embed.js → construct embed form URL
                #   boards.greenhouse.io/embed/job_board/js?for=COMPANY is the embed loader
                m_for = _re.search(
                    r'greenhouse\.io/embed/job_board/js\?for=([^"&\s]+)', html
                )
                if m_for:
                    company = m_for.group(1)
                    parsed = urlparse(url)
                    params = parse_qs(parsed.query)
                    job_id = (params.get('gh_jid') or params.get('token') or [None])[0]
                    if not job_id:
                        m_id = _re.search(r'/(\d{5,})', parsed.path)
                        if m_id:
                            job_id = m_id.group(1)
                    if job_id:
                        form_url = (
                            f"https://job-boards.greenhouse.io/embed/job_app"
                            f"?for={company}&token={job_id}"
                        )
                        logger.info("_detect_form_url: embed.js → %s", form_url)
                        return form_url
        except Exception as e:
            logger.debug("_detect_form_url: %s", e)

        return None

    async def _apply(self, url: str, ats: str, ctx: dict, headless: bool = True) -> bool:
        # Detect real form URL from static HTML BEFORE Chrome opens (avoids CDP idle-crash)
        form_url = await self._detect_form_url(url)
        navigate_to = form_url or url

        async with BrowserService(headless=headless) as browser:
            page = await browser.new_page()
            try:
                await browser.goto(page, navigate_to, wait=3.0)
                await browser.wait_past_cloudflare(page)
                # One intelligent path for all ATS types — scan fields, AI fills, submit
                return await self._fill_universal(browser, page, ctx, url=navigate_to)
            except Exception:
                await browser.screenshot(page, f"apply_error_{ats}")
                logger.exception("_apply: unhandled error on %s", url)
                return False

    # ── Greenhouse (hybrid: seed known fields, then AI-fill the rest) ────────────

    async def _fill_greenhouse(self, browser: BrowserService, page, ctx: dict) -> bool:
        """
        Greenhouse forms vary per company — some have only 5 fields, others have 20+.
        Strategy: seed the stable structural fields (name/email/phone/resume/linkedin)
        via direct selectors, then run the AI DOM-scan to fill any remaining custom
        fields (work auth, portfolio, salary, custom questions, EEO, etc.).
        """
        # 1. Seed stable fields — failures are non-fatal
        first = (ctx["full_name"] or "").split()[0]
        last = " ".join((ctx["full_name"] or "").split()[1:]) or "."
        for sel, val in [
            ('#first_name, input[name="first_name"]', first),
            ('#last_name, input[name="last_name"]', last),
            ('#email, input[name="email"]', ctx["email"]),
            ('#phone, input[name="phone"]', ctx["phone"]),
            ('input[name*="linkedin"]', ctx["linkedin_url"]),
            ('input[name*="github"], input[name*="github_url"]', ctx["github_url"]),
            ('input[name*="website"], input[name*="portfolio"]', ctx["portfolio_url"]),
        ]:
            if not val:
                continue
            try:
                await browser.type_human(page, sel, val)
            except Exception:
                pass

        # 2. Upload resume
        if ctx["resume_pdf"]:
            try:
                await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                await asyncio.sleep(1.0)
            except Exception:
                pass

        # 3. Cover letter textarea (if present)
        if ctx["cover_letter"]:
            for cover_sel in ['textarea[name*="cover"]', 'textarea[name*="letter"]',
                               '#cover_letter', 'textarea.cover-letter']:
                try:
                    await browser.fill_field(page, cover_sel, ctx["cover_letter"])
                    break
                except Exception:
                    pass

        # 4. AI-scan remaining fields and fill them
        await asyncio.sleep(1.0)
        _raw_scan = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
        fields: list[dict] = json.loads(_raw_scan) if isinstance(_raw_scan, str) else (_raw_scan or [])
        fillable = [f for f in fields if f.get("label") or f.get("options")]
        if fillable:
            answers = await self._ai_map_fields(fillable, ctx)
            combobox_selectors: set[str] = set()
            for i, f in enumerate(fields):
                nxt = fields[i + 1] if i + 1 < len(fields) else None
                if nxt and str(nxt.get("selector", "")).startswith("__idx__") and nxt.get("required"):
                    sel = f.get("selector", "")
                    if sel and not sel.startswith("__idx__"):
                        combobox_selectors.add(sel)
            for field in fillable:
                idx = str(field.get("idx", ""))
                value = answers.get(idx, "")
                if not value:
                    continue
                selector = field.get("selector", "")
                ftype = field.get("type", "text")
                label = (field.get("label") or "").strip()
                if selector.startswith("__idx__"):
                    continue
                try:
                    if ftype == "file":
                        if ctx["resume_pdf"]:
                            await browser.upload_file(page, selector, ctx["resume_pdf"])
                    elif selector in combobox_selectors:
                        await self._interact_combobox(browser, page, selector, str(value), label)
                    elif len(str(value)) > 80:
                        await browser.fill_field(page, selector, str(value))
                    else:
                        await page.evaluate(_make_fill_js(selector, str(value), ftype))
                    await asyncio.sleep(0.15)
                except Exception:
                    pass

        # 5. Submit
        clicked = await browser.click_human(page, '#submit_app, button[type="submit"]')
        if not clicked:
            logger.warning("_fill_greenhouse: submit button not found — taking screenshot")
            await browser.screenshot(page, "greenhouse_no_submit")
            return False

        await page.sleep(3)
        final_url = await browser.current_url(page)
        page_text = await page.evaluate("document.body ? document.body.innerText.slice(0, 300) : ''") or ""
        logger.info("_fill_greenhouse: post-submit url=%s snippet=%s", final_url, page_text[:150])
        return await self._is_success_page(browser, page, final_url)

    # ── Lever (hybrid: seed known fields, then AI-fill the rest) ─────────────

    async def _fill_lever(self, browser: BrowserService, page, ctx: dict) -> bool:
        # 1. Seed stable fields
        for sel, val in [
            ('input[name="name"]', ctx["full_name"]),
            ('input[name="email"]', ctx["email"]),
            ('input[name="phone"]', ctx["phone"]),
            ('input[name*="linkedin"]', ctx["linkedin_url"]),
            ('input[name*="github"]', ctx["github_url"]),
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

        # 2. AI-fill remaining custom fields
        await asyncio.sleep(1.0)
        _raw_scan = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
        fields: list[dict] = json.loads(_raw_scan) if isinstance(_raw_scan, str) else (_raw_scan or [])
        fillable = [f for f in fields if f.get("label") or f.get("options")]
        if fillable:
            answers = await self._ai_map_fields(fillable, ctx)
            combobox_selectors: set[str] = set()
            for i, f in enumerate(fields):
                nxt = fields[i + 1] if i + 1 < len(fields) else None
                if nxt and str(nxt.get("selector", "")).startswith("__idx__") and nxt.get("required"):
                    sel = f.get("selector", "")
                    if sel and not sel.startswith("__idx__"):
                        combobox_selectors.add(sel)
            for field in fillable:
                idx = str(field.get("idx", ""))
                value = answers.get(idx, "")
                if not value:
                    continue
                selector = field.get("selector", "")
                ftype = field.get("type", "text")
                label = (field.get("label") or "").strip()
                if selector.startswith("__idx__"):
                    continue
                try:
                    if ftype == "file":
                        if ctx["resume_pdf"]:
                            await browser.upload_file(page, selector, ctx["resume_pdf"])
                    elif selector in combobox_selectors:
                        await self._interact_combobox(browser, page, selector, str(value), label)
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
            return False
        await page.sleep(3)
        return await self._is_success_page(browser, page, await browser.current_url(page))

    # ── Ashby (fast-path) ─────────────────────────────────────────────────────

    async def _fill_ashby(self, browser: BrowserService, page, ctx: dict) -> bool:
        await browser.type_human(page,
                                  'input[placeholder*="name" i], input[name*="name"]',
                                  ctx["full_name"])
        await browser.type_human(page, 'input[type="email"]', ctx["email"])
        await browser.type_human(page, 'input[type="tel"]', ctx["phone"])
        await browser.type_human(page, 'input[placeholder*="linkedin" i]', ctx["linkedin_url"])

        if ctx["resume_pdf"]:
            await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
        if ctx["cover_letter"]:
            await browser.fill_field(page, 'textarea', ctx["cover_letter"])

        clicked = await browser.click_human(page, 'button[type="submit"]')
        if not clicked:
            return False
        await page.sleep(2)
        return await browser.wait_for(
            page,
            '[class*="success"], [class*="confirm"], [class*="thank"]',
            timeout=8,
        )

    # ── Universal intelligent filler (all ATS types) ─────────────────────────

    async def _fill_universal(self, browser: BrowserService, page, ctx: dict, url: str = "") -> bool:
        """
        Single intelligent path for all job application forms regardless of ATS.

        Each form step:
          1. Upload resume if a file input is present
          2. Scan every visible fillable field (inputs, selects, textareas, radios, checkboxes)
          3. Log what was found so we can see exactly what the form is asking
          4. One AI call maps every field label → the right answer from candidate profile
          5. Fill each field one by one
          6. Click Next/Submit and check for success

        Repeats up to MAX_FORM_STEPS times for multi-step forms.
        """
        submitted = False
        prev_url = await browser.current_url(page)
        resume_uploaded = False

        # ── Resolve real form page ────────────────────────────────────────────────
        # Static HTML detection (httpx) is now done in _detect_form_url() BEFORE Chrome
        # opens, so Chrome navigates directly to the form URL. Here we only need the
        # JS-based fallbacks for any remaining non-ATS cases.
        #
        # Detection order:
        #   0. Already on a known ATS domain → skip detection, form is on this page
        #   1. Poll for JS-injected iframe (shadow DOM traversal)
        #   2. Last resort: click an Apply button / follow an Apply link
        current = await browser.current_url(page)
        _ats_domains = [p for patterns in ATS_PATTERNS.values() for p in patterns
                        if p != "linkedin.com/jobs/apply"]
        already_on_ats = any(d in current for d in _ats_domains)

        if already_on_ats:
            logger.info("already on ATS page (%s) — skipping iframe detection", current[:80])
        else:
                # 2. Poll for JS-injected iframe.
                #    IMPORTANT: check iframe src FIRST every iteration.
                #    Never break early on stray form inputs (search bars, cookie popups, etc.)
                #    in the parent page — those are NOT the job application form.
                #    Shadow DOM traversal included — some sites (e.g. Datadog/Greenhouse embed)
                #    wrap the iframe inside a shadow root, making it invisible to plain
                #    document.querySelectorAll.
                iframe_found = False
                for _ in range(30):  # 30 × 0.5 s = 15 s max
                    src = await page.evaluate("""
                        (function() {
                            var skip = ['recaptcha','google.com','youtube','analytics',
                                        'about:','javascript:','doubleclick','facebook'];
                            function search(root) {
                                var frames = root.querySelectorAll('iframe');
                                for (var i = 0; i < frames.length; i++) {
                                    var s = frames[i].src || frames[i].getAttribute('src') || '';
                                    if (s && !skip.some(function(x) { return s.includes(x); }))
                                        return s;
                                }
                                var els = root.querySelectorAll('*');
                                for (var j = 0; j < els.length; j++) {
                                    if (els[j].shadowRoot) {
                                        var found = search(els[j].shadowRoot);
                                        if (found) return found;
                                    }
                                }
                                return null;
                            }
                            return search(document);
                        })()
                    """)
                    if src:
                        logger.info("found iframe via JS — navigating to: %s", src[:100])
                        await browser.goto(page, src, wait=5.0)
                        iframe_found = True
                        break
                    await asyncio.sleep(0.5)

                if not iframe_found:
                    # 3. Last resort: look for an Apply button/link (shadow DOM traversal)
                    apply_href = await page.evaluate("""
                        (function() {
                            var exclude = ['reapply','already applied','view application',
                                           'track application','withdraw'];
                            function find(root) {
                                var els = root.querySelectorAll('a,button,[role="button"],[role="link"]');
                                for (var i = 0; i < els.length; i++) {
                                    var el = els[i];
                                    var t = (el.innerText || el.textContent || '').toLowerCase().trim();
                                    if (!t.includes('apply')) continue;
                                    if (exclude.some(function(x) { return t.includes(x); })) continue;
                                    if (el.tagName === 'A' && el.href && !el.href.startsWith('javascript:'))
                                        return el.href;
                                    el.click();
                                    return 'clicked';
                                }
                                var all = root.querySelectorAll('*');
                                for (var j = 0; j < all.length; j++) {
                                    if (all[j].shadowRoot) {
                                        var r = find(all[j].shadowRoot);
                                        if (r) return r;
                                    }
                                }
                                return null;
                            }
                            return find(document);
                        })()
                    """)
                    if apply_href and apply_href != 'clicked':
                        logger.info("navigating to Apply link: %s", apply_href[:100])
                        await browser.goto(page, apply_href, wait=5.0)
                    elif apply_href == 'clicked':
                        logger.info("clicked Apply button — waiting for form")
                        await asyncio.sleep(4.0)
                    else:
                        # No iframe, no Apply button — proceed and scan whatever is here
                        logger.warning("no iframe or Apply button found — scanning current page as-is")

        # ── Pre-loop: navigate to the actual form if we're still on a description page ──
        # Poll for up to 10 s for fields to appear (React SPAs render asynchronously).
        pre_count = 0
        for _ in range(20):  # 20 × 0.5 s = 10 s
            await asyncio.sleep(0.5)
            pre_count = await page.evaluate(
                "document.querySelectorAll("
                "'input:not([type=hidden]):not([disabled]),"
                "select:not([disabled]),textarea:not([disabled])').length"
            ) or 0
            if pre_count > 0:
                break
        logger.info("pre-loop: %d field(s) visible after initial wait", pre_count)

        if pre_count == 0:
            logger.info("pre-loop: no form fields visible — locating application form")
            cur = await browser.current_url(page)
            navigated = False

            # Pattern 1: OLD-format Greenhouse only (boards.greenhouse.io, not job-boards.greenhouse.io).
            # The old embed format supports a direct /apply URL.
            # The NEW format (job-boards.greenhouse.io) is a React SPA — /apply gives 404.
            if 'boards.greenhouse.io' in cur and 'job-boards' not in cur and '/jobs/' in cur:
                base = cur.split('?')[0].rstrip('/')
                if not base.endswith('/apply'):
                    apply_attempt = base + '/apply'
                    logger.info("pre-loop: navigating to old-format Greenhouse /apply: %s", apply_attempt)
                    await browser.goto(page, apply_attempt, wait=5.0)
                    navigated = True

            if not navigated:
                # Pattern 2: broad Apply button/link search with shadow DOM traversal.
                # New Greenhouse SPA and some embedded sites render buttons inside shadow roots —
                # plain document.querySelectorAll('button') can't see them.
                _apply_raw = await page.evaluate("""
                    (function() {
                        var exclude = ['reapply','already applied','view application',
                                       'track application','withdraw'];
                        function find(root) {
                            var els = root.querySelectorAll('a,button,[role="button"],[role="link"]');
                            for (var i = 0; i < els.length; i++) {
                                var el = els[i];
                                var t = (el.innerText || el.textContent || '').toLowerCase().trim();
                                if (!t.includes('apply')) continue;
                                if (exclude.some(function(x) { return t.includes(x); })) continue;
                                if (el.tagName === 'A' && el.href && !el.href.startsWith('javascript:'))
                                    return JSON.stringify({action: 'navigate', url: el.href});
                                el.click();
                                return JSON.stringify({action: 'clicked'});
                            }
                            var all = root.querySelectorAll('*');
                            for (var j = 0; j < all.length; j++) {
                                if (all[j].shadowRoot) {
                                    var r = find(all[j].shadowRoot);
                                    if (r) return r;
                                }
                            }
                            return null;
                        }
                        return find(document);
                    })()
                """)
                apply_result = json.loads(_apply_raw) if isinstance(_apply_raw, str) and _apply_raw else None
                if apply_result:
                    if apply_result.get('action') == 'navigate':
                        logger.info("pre-loop: following Apply link: %s",
                                    str(apply_result.get('url', ''))[:100])
                        await browser.goto(page, apply_result['url'], wait=5.0)
                    else:
                        logger.info("pre-loop: clicked Apply button — polling for form (up to 8 s)")
                        # Poll for form fields to appear (React SPA renders asynchronously)
                        for _ in range(16):  # 16 × 0.5 s = 8 s
                            await asyncio.sleep(0.5)
                            cnt = await page.evaluate(
                                "document.querySelectorAll("
                                "'input:not([type=hidden]):not([disabled]),"
                                "select:not([disabled]),textarea:not([disabled])').length"
                            ) or 0
                            if cnt > 0:
                                logger.info("pre-loop: form appeared (%d fields)", cnt)
                                break
                        else:
                            logger.warning("pre-loop: form didn't appear after clicking Apply")
                else:
                    # Dump all clickable element texts so we can see what the DOM exposes
                    _btn_raw = await page.evaluate("""
                        JSON.stringify(
                            Array.from(document.querySelectorAll('a,button,[role="button"],[role="link"]'))
                                .map(function(el) { return (el.innerText || el.textContent || '').trim(); })
                                .filter(Boolean)
                                .slice(0, 40)
                        )
                    """) or "[]"
                    btn_texts = json.loads(_btn_raw) if isinstance(_btn_raw, str) else []
                    logger.warning("pre-loop: cannot find Apply entry point — DOM buttons: %s",
                                   btn_texts)
                    await browser.screenshot(page, "apply_button_not_found")

        url_stuck_count = 0  # consecutive retries on the same URL
        for step in range(MAX_FORM_STEPS):
            await asyncio.sleep(1.0)

            # ── Step 1: upload resume to any file input on this page ──────────
            if ctx["resume_pdf"] and not resume_uploaded:
                try:
                    await browser.upload_file(page, 'input[type="file"]', ctx["resume_pdf"])
                    resume_uploaded = True
                    logger.info("step %d: uploaded resume", step)
                    await asyncio.sleep(1.0)
                except Exception:
                    pass  # no file input on this step

            # ── Step 2: scan all visible fillable fields ──────────────────────
            _raw_scan = await page.evaluate(_SCAN_FIELDS_JS) or "[]"
            fields: list[dict] = json.loads(_raw_scan) if isinstance(_raw_scan, str) else (_raw_scan or [])

            # Log ALL raw scan results so we can see exactly what the DOM exposes
            logger.info("step %d: raw scan returned %d field(s)", step, len(fields))
            for f in fields[:30]:
                logger.info("  RAW field: type=%s label=%r name=%r selector=%s required=%s",
                            f.get("type"), f.get("label"), f.get("name"),
                            f.get("selector"), f.get("required"))

            # Include all fields — those without a label still have a selector/type
            # and the AI can infer from field name, type, and placeholder what to fill
            fillable = [f for f in fields if not str(f.get("selector", "")).startswith("__idx__")]

            # ── Step 3: log what we found ─────────────────────────────────────
            if fillable:
                logger.info("step %d: found %d field(s):", step, len(fillable))
                for f in fillable:
                    label = (f.get("label") or "").strip()
                    ftype = f.get("type", "text")
                    opts = f.get("options") or []
                    required = "* " if f.get("required") else "  "
                    if opts:
                        opt_preview = " | ".join(
                            (o["label"] if isinstance(o, dict) else str(o)) for o in opts[:5]
                        )
                        logger.info("  %s[%s] %s → options: %s", required, ftype, label, opt_preview)
                    else:
                        logger.info("  %s[%s] %s", required, ftype, label)
            else:
                logger.info("step %d: no fillable fields found — checking for success or next button", step)

            # ── Step 4: AI maps every field to a value ────────────────────────
            if fillable:
                # Build combobox set: any field where the NEXT raw field has
                # selector '__idx__N' — these are custom React/Select2 dropdowns.
                _PHONE_SKIP = ("phone_country", "phoneCountry", "phone-country", "country_code", "dial_code")
                combobox_selectors: set[str] = set()
                for i, f in enumerate(fields):
                    nxt = fields[i + 1] if i + 1 < len(fields) else None
                    if nxt and str(nxt.get("selector", "")).startswith("__idx__") and nxt.get("required"):
                        sel = f.get("selector", "")
                        if sel and not sel.startswith("__idx__") and not any(p in sel for p in _PHONE_SKIP):
                            combobox_selectors.add(sel)

                # Pre-read real options from every combobox so the LLM gets
                # actual choices instead of guessing. Runs before _ai_map_fields.
                if combobox_selectors:
                    logger.info("step %d: pre-reading options from %d combobox(es)",
                                step, len(combobox_selectors))
                    for field in fillable:
                        sel = field.get("selector", "")
                        if sel in combobox_selectors and not field.get("options"):
                            opts = await self._read_combobox_options(browser, page, sel)
                            if opts:
                                field["options"] = opts
                                logger.info("  combobox [%s] options: %s",
                                            (field.get("label") or sel)[:40], opts[:8])

                answers = await self._ai_map_fields(fillable, ctx)
                logger.info("step %d: AI produced %d answer(s)", step, len(answers))

                # ── Step 5: fill each field ───────────────────────────────────
                for field in fillable:
                    idx = str(field.get("idx", ""))
                    value = answers.get(idx, "")
                    selector = field.get("selector", "")
                    ftype = field.get("type", "text")
                    label = (field.get("label") or "").strip()

                    if not value:
                        logger.debug("  skip [%s] %s — no answer", ftype, label)
                        continue
                    if selector.startswith("__idx__"):
                        logger.debug("  skip [%s] %s — no reliable selector", ftype, label)
                        continue

                    try:
                        if ftype == "file":
                            if ctx["resume_pdf"] and not resume_uploaded:
                                await browser.upload_file(page, selector, ctx["resume_pdf"])
                                resume_uploaded = True
                        elif selector in combobox_selectors:
                            # Custom dropdown — must open and click option, not set .value
                            await self._interact_combobox(browser, page, selector, str(value), label)
                        elif len(str(value)) > 80:
                            await browser.fill_field(page, selector, str(value))
                        else:
                            await page.evaluate(_make_fill_js(selector, str(value), ftype))
                        logger.info("  filled [%s] %s = %s", ftype, label, str(value)[:60])
                    except Exception as e:
                        logger.warning("  failed [%s] %s: %s", ftype, label, e)

                    await asyncio.sleep(0.2)

            # ── Step 6: advance (Next or Submit) ──────────────────────────────
            advanced = await self._advance_form(browser, page)
            await asyncio.sleep(2.0)

            new_url = await browser.current_url(page)
            if await self._is_success_page(browser, page, new_url):
                logger.info("step %d: success page detected at %s", step, new_url)
                submitted = True
                break

            if not advanced:
                logger.info("step %d: no advance button found — stopping", step)
                break

            if new_url == prev_url:
                url_stuck_count += 1
                logger.info(
                    "step %d: URL unchanged after click — form may have validation errors "
                    "(attempt %d/3)",
                    step, url_stuck_count,
                )
                await browser.screenshot(page, f"form_stuck_step{step}_attempt{url_stuck_count}")
                if url_stuck_count >= 3:
                    logger.warning("step %d: URL stuck after 3 attempts — giving up", step)
                    break
                # Re-scan and re-fill the same page on the next loop iteration
                continue

            url_stuck_count = 0  # reset on successful navigation
            prev_url = new_url

        return submitted

    async def _cdp_key(self, page, key: str, code: str, vk: int) -> None:
        """Send a real key event via CDP — works cross-frame to the focused element."""
        for ktype in ("rawKeyDown", "keyUp"):
            await page.send(cdp.input_.dispatch_key_event(
                type_=ktype,
                key=key,
                code=code,
                windows_virtual_key_code=vk,
                native_virtual_key_code=vk,
            ))
            await asyncio.sleep(0.05)

    # Regex that matches phone country code option text: "Afghanistan+93", "Åland Islands+358"
    _PHONE_CODE_RE = re.compile(r'[A-Za-zÅÆØåæø].+\+\d{1,4}$')

    async def _read_combobox_options(
        self,
        browser: "BrowserService",
        page,
        selector: str,
    ) -> list[str]:
        """
        Click a custom dropdown open, read the visible option texts, then close it.
        Returns a list of option label strings (empty if not a dropdown or on error).
        Does NOT select anything.
        """
        try:
            # Dismiss any currently open dropdown before clicking the next one
            await self._cdp_key(page, "Escape", "Escape", 27)
            await asyncio.sleep(0.1)
            await page.evaluate("document.body && document.body.click()")
            await asyncio.sleep(0.3)

            el = await page.find(selector, timeout=4)
            if not el:
                return []
            await el.click()
            await asyncio.sleep(0.8)

            opts: list[str] = []
            for lb_sel in ('[role="listbox"]', '[class*="-menu"]', '.pac-container',
                           '[role="combobox"] + *', '[aria-expanded="true"] ~ *'):
                try:
                    listbox = await page.find(lb_sel, timeout=1)
                    if not listbox:
                        continue
                    for opt_sel in ('[role="option"]', 'li', '.pac-item'):
                        els = await listbox.query_selector_all(opt_sel)
                        if els:
                            for oe in els[:30]:
                                try:
                                    html = await oe.get_html()
                                    txt = re.sub(r'<[^>]+>', '', html or '').strip()
                                    # Skip pure dial codes (+93) and phone-code combo text
                                    if txt and not re.match(r'^\+\d+$', txt):
                                        opts.append(txt)
                                except Exception:
                                    pass
                            break
                    if opts:
                        break
                except Exception:
                    pass

            # Close the dropdown without selecting, then click body to fully dismiss
            await self._cdp_key(page, "Escape", "Escape", 27)
            await asyncio.sleep(0.2)
            await page.evaluate("document.body && document.body.click()")
            await asyncio.sleep(0.2)

            # Reject the result if it looks like a phone country picker
            # (options like "Afghanistan+93", "Åland Islands+358")
            if opts:
                phone_like = sum(1 for o in opts if self._PHONE_CODE_RE.match(o))
                if phone_like > min(3, len(opts) // 2):
                    logger.debug(
                        "_read_combobox_options: %s — looks like phone country picker, discarding",
                        selector[:50]
                    )
                    return []

            return opts

        except Exception:
            return []

    async def _interact_combobox(
        self,
        browser: "BrowserService",
        page,
        selector: str,
        value: str,
        label: str = "",
    ) -> bool:
        """
        Click a custom dropdown, read what options are actually there, pick the best match.

        Strategy:
          1. Click to open (no typing)
          2. Read all options from the open listbox via CDP (cross-frame)
          3. Score each option against `value`, click the best match
          4. If no listbox found, type prefix + ArrowDown+Enter as fallback
        """
        is_location = "candidate-location" in selector
        vl = str(value).lower()

        def score_option(text: str) -> int:
            tl = text.lower().strip()
            if not tl or re.match(r'^\+\d+$', tl):
                return -1  # skip phone codes
            if tl == vl:
                return 4
            if tl.startswith(vl[:min(len(vl), 6)]):
                return 3
            if vl[:3] and tl.startswith(vl[:3]):
                return 2
            if vl[:2] and vl[:2] in tl:
                return 1
            return 0

        try:
            el = await page.find(selector, timeout=5)
            if not el:
                logger.debug("_interact_combobox: element not found: %s", selector)
                return False

            # Click to open the dropdown
            await el.click()
            await asyncio.sleep(0.8)

            # ── Strategy 1: read listbox options via CDP ───────────────────────
            # Try [role="listbox"], then [class*="menu"] (React Select), then pac-container
            listbox = None
            for lb_sel in ('[role="listbox"]', '[class*="-menu"]', '.pac-container'):
                try:
                    listbox = await page.find(lb_sel, timeout=2)
                    if listbox:
                        break
                except Exception:
                    pass

            if listbox:
                # Read all options from the open listbox
                option_els = []
                for opt_sel in ('[role="option"]', 'li', '.pac-item'):
                    try:
                        option_els = await listbox.query_selector_all(opt_sel)
                        if option_els:
                            break
                    except Exception:
                        pass

                if option_els:
                    # Collect (text, score) — don't hold element references
                    scored = []
                    for opt_el in option_els[:30]:
                        try:
                            html = await opt_el.get_html()
                            txt = re.sub(r'<[^>]+>', '', html or '').strip()
                            s = score_option(txt)
                            if s >= 0:
                                scored.append((txt, s))
                        except Exception:
                            pass

                    if scored:
                        scored.sort(key=lambda x: x[1], reverse=True)
                        best_txt, best_score = scored[0]
                        logger.info("_interact_combobox: [%s] %s — options: %s",
                                    selector[:40], label[:20],
                                    [t for t, _ in scored[:5]])

                        # Find the option text via CDP page.find() for a real cross-frame click
                        try:
                            opt_el = await page.find(best_txt[:30], best_match=True, timeout=2)
                            if opt_el:
                                await opt_el.click()
                                await asyncio.sleep(0.4)
                                logger.info("_interact_combobox: picked %r (score=%d)",
                                            best_txt[:40], best_score)
                                return True
                        except Exception as ce:
                            logger.debug("_interact_combobox: CDP click failed: %s", ce)

            # ── Strategy 2: type to filter, then ArrowDown+Enter ───────────────
            logger.debug("_interact_combobox: no listbox/options found for %s — typing+ArrowDown",
                         selector[:40])

            await el.click()
            await asyncio.sleep(0.3)

            # Type just enough to filter — first 4 chars is plenty
            type_val = str(value)[:4]
            for char in type_val:
                await el.send_keys(char)
                await asyncio.sleep(0.08)

            wait = 2.5 if is_location else 1.0
            await asyncio.sleep(wait)

            await self._cdp_key(page, "ArrowDown", "ArrowDown", 40)
            await asyncio.sleep(0.3)
            await self._cdp_key(page, "Enter", "Enter", 13)
            await asyncio.sleep(0.4)

            logger.info("_interact_combobox: [%s] %s = %s (ArrowDown+Enter fallback)",
                        selector[:40], label[:30], value[:30])
            return True

        except Exception as e:
            logger.warning("_interact_combobox %s: %s", selector, e)
            return False

    async def _ai_map_fields(self, fields: list[dict], ctx: dict) -> dict:
        """
        One Haiku call per form page. Returns {field_idx_str: value_to_fill}.
        EEO/diversity questions get "Decline to answer" by default.
        """
        # Build compact field description
        field_lines = []
        for f in fields[:40]:  # cap at 40 fields to stay within token budget
            idx = str(f.get("idx", ""))
            label = (f.get("label") or "").strip()
            name = (f.get("name") or f.get("selector", "")).strip()
            ftype = f.get("type", "text")
            opts = f.get("options") or []
            # Use label if present, fall back to name/selector so AI still has signal
            display = label or name or ftype
            if opts:
                if isinstance(opts[0], dict):
                    opts_str = " | ".join(o.get("label", str(o)) for o in opts[:8])
                else:
                    opts_str = " | ".join(str(o) for o in opts[:8])
                field_lines.append(f"  [{idx}] {display} (select: {opts_str})")
            elif ftype == "radio":
                radio_opts_raw = f.get("options") or []
                radio_opts = " | ".join(
                    (o["label"] if isinstance(o, dict) else str(o)) for o in radio_opts_raw[:6]
                )
                field_lines.append(f"  [{idx}] {display} (radio: {radio_opts})")
            else:
                field_lines.append(f"  [{idx}] {display} ({ftype})")

        fields_block = "\n".join(field_lines)

        profile_block = (
            f"Full name: {ctx.get('full_name', '')}\n"
            f"Email: {ctx.get('email', '')}\n"
            f"Phone: {ctx.get('phone', '')}\n"
            f"City: {ctx.get('city', '')}\n"
            f"Country: {ctx.get('country', '')}\n"
            f"LinkedIn: {ctx.get('linkedin_url', '')}\n"
            f"GitHub: {ctx.get('github_url', '')}\n"
            f"Portfolio: {ctx.get('portfolio_url', '')}\n"
            f"Years of experience: {ctx.get('years_of_experience', '')}\n"
            f"Skills: {ctx.get('skills', '')}\n"
            f"Salary expectation: {ctx.get('salary', '')}\n"
            f"Applying for: {ctx.get('job_title', '')} at {ctx.get('company', '')}"
        )

        prompt = (
            "You are filling out a job application form. Map each field to the best value from the candidate profile.\n\n"
            f"FORM FIELDS:\n{fields_block}\n\n"
            f"CANDIDATE PROFILE:\n{profile_block}\n\n"
            "RULES:\n"
            "- For select/radio fields, use the EXACT short option text (e.g. 'Yes', 'No')\n"
            "- IMPORTANT: when a field has a finite list of options (select/radio/dropdown), you MUST always pick one — never leave it blank. If none match the candidate perfectly, pick the closest or most neutral option.\n"
            "- For location dropdowns where the candidate's city is not listed: pick the first non-empty option (e.g. the first city listed)\n"
            "- For EEO questions (race, ethnicity, gender, disability, veteran status, LGBTQ+): use 'Decline' as the value (the bot will find the exact 'Decline to...' option in the dropdown)\n"
            "- For 'Are you authorized / legally authorised to work...' questions: 'Yes'\n"
            "- For 'Are you currently located in the US / Bay Area': 'No'\n"
            "- For 'Do you require visa sponsorship': 'No'\n"
            "- For 'I certify / I confirm / I understand / I consent / I agree' dropdown fields: answer 'Yes' or 'I agree' — use the SHORT option text, NOT the full statement\n"
            "- For salary fields: use the salary expectation value\n"
            "- For cover letter / additional info / why work here fields: use the cover letter text provided\n"
            "- For checkbox fields (e.g. agree to terms, consent): 'true'\n"
            "- For 'How did you hear about this job': 'Internet / Job Board' or similar short option\n"
            "- Only skip fields with no options and no clear answer from the profile\n\n"
            f"Cover letter (use for cover letter / additional comments fields):\n{ctx.get('cover_letter', '')[:800]}\n\n"
            "Output ONLY valid JSON: {\"field_idx\": \"value\", ...}"
        )

        try:
            raw = (await call_llm(prompt, max_tokens=800)).strip()
            # Extract JSON even if wrapped in markdown
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            logger.exception("_ai_map_fields: AI call failed")

        return {}

    async def _advance_form(self, browser: BrowserService, page) -> bool:
        """
        Click the most appropriate button to advance the form.
        Tries Next/Continue first, falls back to Submit.
        Returns True if a button was clicked.
        """
        # Priority order: explicit Next/Continue buttons, then Submit
        next_selectors = [
            # Workday
            'button[data-automation-id="bottom-navigation-next-button"]',
            'button[data-automation-id="wd-CommandButton_uic_nextButton"]',
            # Generic text-based
            'button[type="button"]:not([disabled])',  # will be filtered below
        ]
        submit_selectors = [
            'button[data-automation-id="bottom-navigation-footer-button"]',
            'button[data-automation-id="wd-CommandButton_uic_submitButton"]',
            '#submit_app',
            'button[type="submit"]:not([disabled])',
            'input[type="submit"]:not([disabled])',
        ]

        # Try to find a "Next" or "Continue" button by text content
        next_clicked = await page.evaluate("""
            (function() {
                var btns = Array.from(document.querySelectorAll('button:not([disabled])'));
                var next = btns.find(function(b) {
                    var txt = (b.innerText || b.value || '').toLowerCase().trim();
                    return txt === 'next' || txt === 'continue' || txt === 'save and continue'
                        || txt === 'next step' || txt === 'proceed';
                });
                if (next) { next.click(); return true; }
                return false;
            })()
        """)
        if next_clicked:
            return True

        # Try submit selectors
        for sel in submit_selectors:
            if await browser.click_human(page, sel):
                return True

        return False

    async def _is_success_page(self, browser: BrowserService, page, url: str) -> bool:
        """Detect post-submission confirmation page via URL patterns and page content."""
        url_lower = url.lower()
        if any(s in url_lower for s in ("confirmation", "thank", "success", "submitted", "complete", "applied")):
            return True
        # Check for on-page confirmation text (covers in-page confirmations with no URL change)
        found = await page.evaluate("""
            (function() {
                var body = (document.body && document.body.innerText) ? document.body.innerText.toLowerCase() : '';
                return body.includes('application submitted')
                    || body.includes('application complete')
                    || body.includes('application received')
                    || body.includes('thank you for applying')
                    || body.includes('thank you for your application')
                    || body.includes('thank you for submitting')
                    || body.includes('successfully submitted')
                    || body.includes('successfully applied')
                    || body.includes('your application has been received')
                    || body.includes('we have received your application')
                    || body.includes('we received your application')
                    || body.includes("you've applied")
                    || body.includes('you have applied')
                    || body.includes("you've submitted");
            })()
        """)
        if found:
            return True
        # Check for ATS-specific confirmation elements
        has_confirm_el = await page.evaluate("""
            Boolean(document.querySelector(
                '.confirmation, .application-confirmation, .thank-you, '
                + '[class*="confirm"], [class*="success-message"], '
                + '[data-qa="application-submitted"], #confirmation'
            ))
        """)
        return bool(has_confirm_el)

    # ── Static helpers for board_appliers package ─────────────────────────────
    # These expose instance-method logic as static/class methods so per-board
    # applier files can call them without instantiating ApplyService.

    @classmethod
    async def _ai_map_fields_static(cls, fields: list[dict], ctx: dict) -> dict:
        """Static alias for _ai_map_fields — used by board appliers."""
        svc = cls.__new__(cls)
        return await svc._ai_map_fields(fields, ctx)

    @classmethod
    async def _read_combobox_options_static(cls, browser, page, selector: str) -> list[str]:
        """Static alias for _read_combobox_options — used by board appliers and tests."""
        svc = cls.__new__(cls)
        return await svc._read_combobox_options(browser, page, selector)

    @classmethod
    async def _is_success_page_static(cls, browser, page, url: str) -> bool:
        """Static alias for _is_success_page — used by board appliers."""
        svc = cls.__new__(cls)
        return await svc._is_success_page(browser, page, url)

    # ── Per-board dispatcher ───────────────────────────────────────────────────

    async def submit_application_for_board(self, application_id: str, board_id: str) -> bool:
        """
        Route application submission to the correct per-board applier.

        Called instead of submit_application() when board_id is known.
        Falls back to submit_application() for unknown boards.
        """
        from app.services.job_hunter.board_appliers import get_applier

        application = (await self.db.execute(
            select(Application).where(Application.id == application_id)
        )).scalar_one_or_none()
        if not application:
            logger.warning("submit_application_for_board: application %s not found", application_id)
            return False

        listing = (await self.db.execute(
            select(JobListing).where(JobListing.id == application.job_listing_id)
        )).scalar_one_or_none()
        if not listing or not listing.apply_url:
            application.status = "failed"
            await self.db.commit()
            return False

        profile = (await self.db.execute(
            select(CampaignProfile).where(CampaignProfile.campaign_id == listing.campaign_id)
        )).scalar_one_or_none()

        ctx = self._build_context(application, profile, listing)
        applier = get_applier(board_id)

        logger.info(
            "submit_application_for_board: %s | board=%s | applier=%s | url=%s",
            application_id, board_id, type(applier).__name__, listing.apply_url,
        )

        try:
            # Detect real form URL before opening browser
            form_url = await self._detect_form_url(listing.apply_url)
            navigate_to = form_url or listing.apply_url

            async with BrowserService(headless=self._headless) as browser:
                page = await browser.new_page()
                await browser.goto(page, navigate_to, wait=3.0)
                await browser.wait_past_cloudflare(page)

                from app.services.job_hunter.board_appliers import ApplyResult
                result: ApplyResult = await applier.apply(navigate_to, ctx, browser, page)

        except Exception:
            logger.exception("submit_application_for_board: browser error for %s", application_id)
            result = ApplyResult(success=False, skipped=False, reason="browser exception")

        if result.skipped:
            application.status = "skipped"
            logger.info("application %s skipped: %s", application_id, result.reason)
        elif result.success:
            application.status = "applied"
            listing.status = "applied"
        else:
            application.status = "failed"
            logger.warning("application %s failed: %s", application_id, result.reason)

        await self.db.commit()
        return result.success
