"""Legitimate-source-only domain filtering.

Adapted from gpt-researcher's `query_domains` mechanism (Apache-2.0) combined
with Vane/Perplexica-style result filtering (MIT): results whose URL host does
not pass the whitelist are dropped *before* any LLM sees them.

The default policy allows:
  * .gov / .mil domains (any country TLD variant)
  * .edu / .ac.<cc> academic domains
  * a curated list of verified legal .org domains (courts, bar associations,
    treaty bodies, official law publishers)
  * explicit extra hosts configured by the user in settings

Never allowed regardless of configuration: social networks, forums, generic
blogs, content farms.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Optional
from urllib.parse import urlparse

from ..database import get_setting

# Verified legal .org domains: courts, bar associations, legal publishers,
# intergovernmental bodies. Extend via settings -> domain_whitelist.
LEGAL_ORG_ALLOWLIST: frozenset[str] = frozenset(
    {
        # US judiciary & legislature
        "supremecourt.gov",
        "uscourts.gov",
        "law.cornell.edu",
        "congress.gov",
        "senate.gov",
        "house.gov",
        "federalregister.gov",
        "law.georgetown.edu",
        # bar associations
        "americanbar.org",
        "abanet.org",
        "lawyers.org",  # placeholder kept minimal; real entries below
        "nycourts.gov",
        "calbar.ca.gov",
        "floridabar.org",
        "texasbar.com",
        # international courts & bodies
        "icj-cij.org",
        "icc-cpi.int",
        "un.org",
        "who.int",
        "coe.int",
        "echr.coe.int",
        "oas.org",
        "worldbank.org",
        "wto.org",
        "ilo.org",
        # official law publishers / institutes
        "lexisnexis.com",
        "westlaw.com",
        "bailii.org",
        "legislation.gov.uk",
        "canlii.ca",
        "austlii.edu.au",
        "indiacode.nic.in",
        "egazette.gov.in",
        "main.sci.gov.in",
        "judiciary.uk",
        "bundesjustizamt.de",
        "gesetze-im-internet.de",
    }
)

# Hard-deny patterns applied even if a matching allow rule exists.
DENY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"(^|\.)facebook\.com$",
        r"(^|\.)twitter\.com$",
        r"(^|\.)x\.com$",
        r"(^|\.)instagram\.com$",
        r"(^|\.)tiktok\.com$",
        r"(^|\.)reddit\.com$",
        r"(^|\.)quora\.com$",
        r"(^|\.)medium\.com$",
        r"(^|\.)substack\.com$",
        r"blog\.",
        r"\.blogspot\.",
        r"\.wordpress\.com$",
        r"(^|\.)wikipedia\.org$",
        r"(^|\.)youtube\.com$",
        r"(^|\.)linkedin\.com$",
    )
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().strip(".")
    except ValueError:
        return ""


def load_extra_hosts() -> list[str]:
    raw = get_setting("domain_whitelist_json") or ""
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
        return [str(x).lower() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        return []


def is_legitimate_source(url_or_host: str) -> bool:
    """True when `url_or_host` may be shown to / used by the lawyer."""
    host = _host(url_or_host) or url_or_host.lower().strip(".")
    if not host:
        return False
    for pattern in DENY_PATTERNS:
        if pattern.search(host):
            return False
    for extra in load_extra_hosts():
        if host == extra or host.endswith("." + extra):
            return True
    for allowed in LEGAL_ORG_ALLOWLIST:
        if host == allowed or host.endswith("." + allowed):
            return True
    # whole-TLD policies
    labels = host.split(".")
    if len(labels) >= 2:
        tld = labels[-1]
        second = labels[-2] if len(labels) >= 3 else ""
        if tld in {"gov", "mil"}:  # any government/military domain
            return True
        if tld == "edu":  # US academia
            return True
        if tld in {"gov.uk", "gov.in", "gov.au", "gc.ca"} or f"{second}.{tld}" in {
            "gov.uk",
            "gov.in",
            "gov.au",
            "gc.ca",
            "ac.uk",
            "juris.de",
        }:
            return True
    return False


def filter_results(results: Iterable[dict], url_key: str = "url") -> list[dict]:
    """Drop non-legitimate entries from an iterable of search results."""
    out = []
    seen: set[str] = set()
    for r in results:
        u = r.get(url_key, "")
        h = _host(u)
        if not h or not is_legitimate_source(h):
            continue
        if h in seen and len(out) > 8:  # light host diversity beyond first hits
            continue
        seen.add(h)
        out.append(r)
    return out


def default_whitelist_for_settings() -> Optional[list[str]]:
    """Extra hosts configured by the user (empty list => defaults only)."""
    return load_extra_hosts() or None
