# backend/tests/services/test_deduplicator.py
import pytest
from app.services.job_hunter.deduplicator import fingerprint, deduplicate


def _job(title: str, company: str, source: str = "indeed") -> dict:
    return {"title": title, "company": company, "source": source}


# ── fingerprint ───────────────────────────────────────────────────────────────

def test_fingerprint_same_job_same_key():
    j1 = _job("Backend Engineer", "Stripe")
    j2 = _job("Backend Engineer", "Stripe")
    assert fingerprint(j1) == fingerprint(j2)


def test_fingerprint_different_company():
    j1 = _job("Backend Engineer", "Stripe")
    j2 = _job("Backend Engineer", "Plaid")
    assert fingerprint(j1) != fingerprint(j2)


def test_fingerprint_different_title():
    j1 = _job("Backend Engineer", "Stripe")
    j2 = _job("Frontend Engineer", "Stripe")
    assert fingerprint(j1) != fingerprint(j2)


def test_fingerprint_strips_seniority_level():
    # "Senior Backend Engineer" and "Backend Engineer" should produce the same key
    j1 = _job("Senior Backend Engineer", "Stripe")
    j2 = _job("Backend Engineer", "Stripe")
    assert fingerprint(j1) == fingerprint(j2)


def test_fingerprint_strips_junior_level():
    j1 = _job("Junior Backend Engineer", "Stripe")
    j2 = _job("Backend Engineer", "Stripe")
    assert fingerprint(j1) == fingerprint(j2)


def test_fingerprint_case_insensitive():
    j1 = _job("backend engineer", "stripe")
    j2 = _job("BACKEND ENGINEER", "STRIPE")
    assert fingerprint(j1) == fingerprint(j2)


def test_fingerprint_accent_normalisation():
    j1 = _job("Développeur Backend", "Société")
    j2 = _job("Developpeur Backend", "Societe")
    assert fingerprint(j1) == fingerprint(j2)


def test_fingerprint_missing_fields():
    j = {"title": None, "company": None}
    fp = fingerprint(j)
    assert isinstance(fp, str)


# ── deduplicate ───────────────────────────────────────────────────────────────

def test_deduplicate_removes_exact_duplicates():
    jobs = [
        _job("Backend Engineer", "Stripe", "indeed"),
        _job("Backend Engineer", "Stripe", "glassdoor"),  # duplicate
    ]
    result = deduplicate(jobs)
    assert len(result) == 1
    assert result[0]["source"] == "indeed"  # first kept


def test_deduplicate_keeps_different_jobs():
    jobs = [
        _job("Backend Engineer", "Stripe"),
        _job("Frontend Engineer", "Stripe"),
        _job("Backend Engineer", "Plaid"),
    ]
    result = deduplicate(jobs)
    assert len(result) == 3


def test_deduplicate_strips_seniority_across_boards():
    jobs = [
        _job("Senior Backend Engineer", "Stripe", "greenhouse"),
        _job("Backend Engineer", "Stripe", "indeed"),       # same after normalisation
    ]
    result = deduplicate(jobs)
    assert len(result) == 1


def test_deduplicate_preserves_order():
    jobs = [
        _job("Role A", "Co1"),
        _job("Role B", "Co2"),
        _job("Role C", "Co3"),
        _job("Role A", "Co1"),  # duplicate of first
    ]
    result = deduplicate(jobs)
    assert [j["title"] for j in result] == ["Role A", "Role B", "Role C"]


def test_deduplicate_empty_list():
    assert deduplicate([]) == []


def test_deduplicate_does_not_mutate_input():
    jobs = [_job("Backend Engineer", "Stripe"), _job("Backend Engineer", "Stripe")]
    original_len = len(jobs)
    deduplicate(jobs)
    assert len(jobs) == original_len
