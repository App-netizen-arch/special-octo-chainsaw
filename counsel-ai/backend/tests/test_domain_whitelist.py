"""Unit tests — legitimate-source-only domain whitelist."""

from __future__ import annotations

import pytest

from app.utils.domain_whitelist import (
    LEGAL_ORG_ALLOWLIST,
    filter_results,
    is_legitimate_source,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.supremecourt.gov/opinions/22pdf/21-1333_d18f.pdf",
        "https://law.cornell.edu/uscode/text/42/1983",
        "https://www.federalregister.gov/documents/2026/01/02/x",
        "https://www.legislation.gov.uk/ukpga/2010/15",
        "https://canlii.ca/t/jxxxx",
        "https://georgia.gov/some-page",           # whole-TLD .gov policy
        "https://sub.law.georgetown.edu/page",
        "https://icj-cij.org/case/180",
    ],
)
def test_allowed(url):
    assert is_legitimate_source(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://facebook.com/legalpage",
        "https://en.wikipedia.org/wiki/Contract",
        "https://medium.com/@someone/law-things",
        "https://reddit.com/r/LegalAdvice",
        "https://myblog.wordpress.com/post",
        "https://totally-not-law.geo cities.example.com",  # malformed host
    ],
)
def test_denied(url):
    assert is_legitimate_source(url) is False


def test_malformed_url_rejected():
    assert is_legitimate_source("") is False
    assert is_legitimate_source("not a url") is False


def test_filter_results_drops_and_keeps():
    results = [
        {"url": "https://www.supremecourt.gov/a", "title": "A"},
        {"url": "https://facebook.com/b", "title": "B"},
        {"url": "https://law.cornell.edu/c", "title": "C"},
    ]
    kept = filter_results(results)
    hosts = {r["url"] for r in kept}
    assert "https://facebook.com/b" not in hosts
    assert len(kept) == 2


def test_host_diversity_cap():
    many = [{"url": f"https://blog.sub.{h}.gov/p{i}", "title": str(i)}
            for i, h in enumerate(["a", "b", "c", "d"])]
    # same host repeated >3 times gets capped
    same_host = [{"url": f"https://supremecourt.gov/page{i}", "title": str(i)} for i in range(8)]
    kept = filter_results(same_host + many)
    supremes = [k for k in kept if "supremecourt.gov" in k["url"]]
    assert len(supremes) == 3


def test_allowlist_contains_core_sources():
    for host in ("supremecourt.gov", "bailii.org", "canlii.ca"):
        assert host in LEGAL_ORG_ALLOWLIST
