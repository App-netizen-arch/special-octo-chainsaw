"""Legitimate-source-only domain filtering.

Adapted from gpt-researcher's ``query_domains`` mechanism (Apache-2.0) with
Perplexica/Vane-style result filtering (MIT): results whose URL host does not
pass the whitelist are dropped *before* any LLM sees them.

The default policy allows:

* ``.gov`` / ``.mil`` domains (any country TLD variant)
* ``.edu`` / ``ac.<cc>`` academic domains
* a curated list of verified legal ``.org``/official domains (courts, bar
  associations, treaty bodies, official law publishers)
* firm-allowed extra hosts configured by admins in Settings > Admin

Never allowed regardless of configuration: social networks, forums, generic
blogs, content farms, wikis.
"""

from __future__ import annotations

import json
import re
from typing import Iterable
from urllib.parse import urlparse

# Verified legal .org domains: courts, bar associations, legal publishers,
# intergovernmental bodies. Extend via Admin > allowed domains.
LEGAL_ORG_ALLOWLIST: frozenset[str] = frozenset(
    {
        # US judiciary & legislature
        "supremecourt.gov", "uscourts.gov", "law.cornell.edu", "congress.gov",
        "senate.gov", "house.gov", "federalregister.gov", "law.georgetown.edu",
        "nycourts.gov",
        # bar associations
        "americanbar.org", "abanet.org", "calbar.ca.gov", "floridabar.org",
        "texasbar.com", "lawsociety.org.uk", "barcouncil.org.uk",
        # international courts & bodies
        "icj-cij.org", "icc-cpi.int", "un.org", "who.int", "coe.int",
        "echr.coe.int", "oas.org", "worldbank.org", "wto.org", "ilo.org",
        # official law publishers / institutes
        "lexisnexis.com", "westlaw.com", "bailii.org", "legislation.gov.uk",
        "canlii.ca", "austlii.edu.au", "indiacode.nic.in", "egazette.gov.in",
        "main.sci.gov.in", "judiciary.uk", "bundesjustizamt.de",
        "gesetze-im-internet.de", "vlex.com", "justia.com",
    }
)

# Hard-deny patterns applied even if a matching allow rule exists.
DENY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"(^|\.)facebook\.com$", r"(^|\.)twitter\.com$", r"(^|\.)x\.com$",
        r"(^|\.)instagram\.com$", r"(^|\.)tiktok\.com$", r"(^|\.)reddit\.com$",
        r"(^|\.)quora\.com$", r"(^|\.)medium\.com$", r"(^|\.)substack\.com$",
        r"blog\.", r"\.blogspot\.", r"\.wordpress\.com$", r"(^|\.)wikipedia\.org$",
        r"(^|\.)youtube\.com$", r"(^|\.)linkedin\.com$",
    )
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().strip(".")
    except ValueError:
        return ""


def load_firm_allowed_hosts() -> list[str]:
    """Admin-configured extra hosts (firm-wide policy)."""
    import os

    raw = os.environ.get("COUNSEL_EXTRA_DOMAINS", "")
    if not raw.strip():
        try:
            from ..database import firm_settings

            data = json.loads(firm_settings().get("allowed_domains_json") or "[]")
            return [str(x).lower().strip(".") for x in data if str(x).strip()]
        except Exception:  # noqa: BLE001 — DB may not be initialized yet
            return []
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def is_legitimate_source(url_or_host: str) -> bool:
    """True when `url_or_host` may be shown to / used by the lawyer."""
    host = _host(url_or_host) or url_or_host.lower().strip(".")
    if not host:
        return False
    for pattern in DENY_PATTERNS:
        if pattern.search(host):
            return False
    for extra in load_firm_allowed_hosts():
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
        if f"{second}.{tld}" in {
            "gov.uk", "gov.in", "gov.au", "gc.ca", "ac.uk", "juris.de", "nic.in"
        }:
            return True
    return False


def filter_results(results: Iterable[dict], url_key: str = "url") -> list[dict]:
    """Drop non-legitimate entries from an iterable of search results."""
    out = []
    seen_host_count: dict[str, int] = {}
    for r in results:
        u = r.get(url_key, "")
        h = _host(u)
        if not h or not is_legitimate_source(h):
            continue
        count = seen_host_count.get(h, 0)
        if count >= 3:  # host diversity beyond the first hits
            continue
        seen_host_count[h] = count + 1
        out.append(r)
    return out
