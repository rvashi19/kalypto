# ruff: noqa: E501
"""Official-source domain whitelist for the Country Compliance Checker.

Core product rule: only whitelisted government/regulatory domains are ever
fetched. Blogs, consultants, and aggregators are rejected. This module is the
single choke point for that policy — the retrieval job and scraper both call
`assert_domain_allowed` before any network fetch.

The effective whitelist is the union of:
  1. BUILTIN_OFFICIAL_DOMAINS below (MVP countries),
  2. COMPLIANCE_ALLOWED_DOMAINS env (comma-separated),
  3. allowed_domains_json on active ComplianceSourceRegistry rows (passed in by caller).

A host matches an entry if it equals the entry or is a subdomain of it
(e.g. "www.fda.gov" matches "fda.gov").
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.core.settings import get_settings

# MVP countries: India export side, USA, Canada, UK, EU, UAE.
BUILTIN_OFFICIAL_DOMAINS: dict[str, tuple[str, ...]] = {
    "India": (
        "dgft.gov.in",
        "icegate.gov.in",
        "cbic.gov.in",
        "apeda.gov.in",
        "fssai.gov.in",
        "plantquarantineindia.nic.in",
    ),
    "USA": (
        "fda.gov",
        "aphis.usda.gov",
        "cbp.gov",
    ),
    "Canada": (
        "cbsa-asfc.gc.ca",
        "inspection.canada.ca",
    ),
    "UK": (
        "gov.uk",
    ),
    "Netherlands/EU": (
        "trade.ec.europa.eu",
        "taxation-customs.ec.europa.eu",
        "ec.europa.eu",
    ),
    "United Arab Emirates": (
        "u.ae",
        "moec.gov.ae",
        "fta.gov.ae",
        "adafsa.gov.ae",
        "dm.gov.ae",
    ),
}


class DomainNotWhitelistedError(RuntimeError):
    """Raised when a URL's host is not on the official-source whitelist."""


def _builtin_domains() -> set[str]:
    domains: set[str] = set()
    for entries in BUILTIN_OFFICIAL_DOMAINS.values():
        domains.update(entries)
    return domains


def _env_domains() -> set[str]:
    raw = get_settings().compliance_allowed_domains or ""
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def effective_whitelist(extra_domains: list[str] | None = None) -> set[str]:
    """Union of builtin + env + caller-supplied (e.g. source-registry) domains."""
    domains = _builtin_domains() | _env_domains()
    if extra_domains:
        domains.update(d.strip().lower() for d in extra_domains if d and d.strip())
    return {d.lower().lstrip(".") for d in domains}


def _host_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_domain_allowed(url: str, extra_domains: list[str] | None = None) -> bool:
    host = _host_of(url)
    if not host:
        return False
    whitelist = effective_whitelist(extra_domains)
    for allowed in whitelist:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def assert_domain_allowed(url: str, extra_domains: list[str] | None = None) -> None:
    if not is_domain_allowed(url, extra_domains):
        raise DomainNotWhitelistedError(
            f"Refused to fetch non-whitelisted domain: {_host_of(url) or url!r}. "
            "Only official government/regulatory sources are allowed."
        )
