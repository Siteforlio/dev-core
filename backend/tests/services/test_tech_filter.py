# backend/tests/services/test_tech_filter.py
import pytest
from unittest.mock import AsyncMock
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
        assert svc._tech_role_prefilter("Analyst", "We are hiring a data engineer to...") is True

    def test_ambiguous_title_no_tech_desc_passes_through(self):
        svc = make_service()
        assert svc._tech_role_prefilter("Associate", "Join our growing team.") is True

    def test_description_check_uses_post_strip_html(self):
        svc = make_service()
        html_desc = "<p>We need a <strong>backend engineer</strong> to build APIs</p>"
        assert svc._tech_role_prefilter("Associate", html_desc) is True

    def test_description_check_uses_only_first_300_chars(self):
        svc = make_service()
        long_prefix = "A" * 300
        desc = long_prefix + " engineer role available"
        assert svc._tech_role_prefilter("Associate", desc) is True  # default pass

    def test_reject_signals_not_checked_in_description(self):
        svc = make_service()
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
        assert _smb_score(job) == 0

    def test_large_corp_from_startup_source_still_no_company_bonus(self):
        job = {"source": "remotive", "company": "Microsoft"}
        assert _smb_score(job) == 2  # +2 source + 0 large-corp

    def test_empty_company_no_company_bonus(self):
        job = {"source": "greenhouse", "company": ""}
        assert _smb_score(job) == 0

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
