# backend/tests/services/test_apply_service.py
import pytest
from app.services.job_hunter.apply_service import ApplyService

def test_detect_ats_greenhouse():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://boards.greenhouse.io/stripe/jobs/123") == "greenhouse"

def test_detect_ats_lever():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://jobs.lever.co/openai/abc") == "lever"

def test_detect_ats_ashby():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://jobs.ashbyhq.com/anthropic/123") == "ashby"

def test_detect_ats_unknown():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://careers.somecompany.com/apply") == "generic"

def test_skip_linkedin_easy_apply():
    service = ApplyService.__new__(ApplyService)
    assert service.detect_ats("https://www.linkedin.com/jobs/apply/123") == "skip"
