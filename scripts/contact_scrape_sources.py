from __future__ import annotations

from urllib.parse import urljoin

COMMON_CONTACT_PATHS = (
    "/contact-us",
    "/contact",
    "/about/contact-us",
    "/about-us/contact-us",
    "/official-information-act-requests",
    "/official-information",
    "/information-requests",
    "/request-information",
    "/oia",
)


def default_candidate_urls(home_page_url: str | None) -> list[str]:
    if not home_page_url:
        return []
    base = home_page_url.rstrip("/") + "/"
    return [urljoin(base, path.lstrip("/")) for path in COMMON_CONTACT_PATHS]


def contact_seed_urls(
    home_page_url: str | None,
    source_url: str | None,
    disclosure_log_url: str | None,
) -> list[tuple[str, str]]:
    seeds = [(url, "contact probe") for url in default_candidate_urls(home_page_url)]
    seeds.extend((url, "OIA source") for url in (source_url, disclosure_log_url) if url)
    return seeds
