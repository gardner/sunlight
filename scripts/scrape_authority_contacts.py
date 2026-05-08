from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

USER_AGENT = "SunlightRequestsContactScraper/0.1 (+https://sunlight.nz)"
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
LOCAL_PART_RE = re.compile(r"[A-Z0-9._%+-]+", re.I)
TRAILING_EMAIL_PUNCTUATION = ".,;:!?)>]}'\""
LEADING_EMAIL_PUNCTUATION = "([<{\"'"
SKIP_EXTENSIONS = {
    ".7z", ".avi", ".doc", ".docx", ".gif", ".jpeg", ".jpg", ".mov", ".mp3", ".mp4",
    ".pdf", ".png", ".ppt", ".pptx", ".rar", ".rss", ".svg", ".webp", ".xls", ".xlsx", ".zip",
}
AVOID_LINK_TERMS = {
    "%5bfile_link", "[file_link", "careers", "facebook", "information-releases", "instagram",
    "jobs", "linkedin", "login", "oia-responses", "proactive-release", "procurement",
    "rss", "sign-in", "signin", "tenders", "twitter", "x.com", "youtube",
}
LINK_TERMS = ("contact", "information-request", "information-requests", "lgoima", "official-information", "oia", "privacy", "request-information")
CONTEXT_TERMS = {
    "contact us", "information request", "lgoima", "local government official information",
    "make a request", "official information", "oia", "privacy", "request information",
}
STRONG_LOCAL_PARTS = {
    "information", "information.requests", "informationrequests", "lgoinfo", "lgoima",
    "official.information", "officialinformation", "oia", "requests",
}
MEDIUM_LOCAL_PARTS = {"admin", "contact", "enquiries", "info", "records"}
WRONG_LOCAL_TERMS = {"careers", "hr", "jobs", "media", "news", "procurement", "recruitment", "tenders", "webmaster"}
NO_REPLY_LOCAL_PARTS = {"bounce", "donotreply", "do-not-reply", "no-reply", "noreply"}
@dataclass(frozen=True)
class Authority:
    id: str
    name: str
    home_page_url: str | None
    source_url: str | None
    contact_status: str
@dataclass(frozen=True)
class PageLink:
    url: str
    text: str

@dataclass(frozen=True)
class EmailCandidate:
    email: str
    normalized_email: str
    source_url: str
    source_page_title: str | None
    source_snippet: str | None
    discovery_method: str
    confidence: int = 0
    confidence_reason: str = "not scored"

@dataclass(frozen=True)
class Score:
    confidence: int
    reason: str

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape public authority contact email candidates.")
    parser.add_argument("--database", default="sunlight-requests", help="D1 database name.")
    parser.add_argument("--remote", action="store_true", help="Read/apply against the remote D1 database.")
    parser.add_argument("--authority-id", help="Only scrape one authority id.")
    parser.add_argument("--source-file", type=Path, help="JSON file containing authority rows.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum authority rows to scrape.")
    parser.add_argument("--offset", type=int, default=0, help="Skip matching authority rows before scraping.")
    parser.add_argument("--max-pages-per-authority", type=int, default=8, help="Maximum pages to fetch per authority.")
    parser.add_argument("--write-sql", type=Path, help="Write generated SQL to this path.")
    parser.add_argument("--dry-run", action="store_true", help="Print a summary without applying generated SQL.")
    parser.add_argument("--brave-search", action="store_true", help="Seed official same-site URLs from Brave Search.")
    parser.add_argument("--brave-results", type=int, default=8, help="Maximum Brave results per authority.")
    parser.add_argument("--min-confidence", type=int, default=50, help="Minimum confidence to keep.")
    parser.add_argument("--timeout", type=float, default=20, help="Request timeout in seconds.")
    parser.add_argument("--delay-ms", type=int, default=500, help="Maximum delay between authorities.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    authorities = load_authorities(args)
    if not authorities:
        print("No authorities matched.")
        return 0

    candidates_by_authority = scrape_authorities(authorities, args)
    generated_sql = build_scrape_sql(candidates_by_authority)
    total_candidates = sum(len(candidates) for candidates in candidates_by_authority.values())
    print(f"Scraped {len(authorities)} authorities and found {total_candidates} candidate contacts.")

    if args.write_sql:
        args.write_sql.write_text(generated_sql)
        print(f"Wrote SQL to {args.write_sql}.")
        return 0

    if args.remote and not args.dry_run and generated_sql.strip():
        apply_sql(args.database, generated_sql, remote=True)
        return 0

    if generated_sql.strip():
        print(generated_sql)
    return 0


def load_authorities(args: argparse.Namespace) -> list[Authority]:
    if args.source_file:
        rows = json.loads(args.source_file.read_text())
    else:
        rows = fetch_authority_rows(args.database, remote=args.remote, authority_id=args.authority_id, limit=args.limit, offset=args.offset)
    authorities = [authority_from_row(row) for row in rows]
    scrapable = [authority for authority in authorities if should_scrape_authority(authority, args.authority_id)]
    return scrapable[args.offset : args.offset + args.limit] if args.source_file else scrapable


def fetch_authority_rows(database: str, *, remote: bool, authority_id: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
    where = ["status = 'active'", "contact_status IN ('missing', 'needs_review', 'invalid')"]
    if authority_id:
        where.append(f"id = {sql(authority_id)}")
    query = f"""
SELECT id, name, source_url, source_metadata_json, contact_status
FROM sunlight_authorities
WHERE {' AND '.join(where)}
ORDER BY name
LIMIT {int(limit)}
OFFSET {int(offset)}
""".strip()
    command = ["pnpm", "dlx", "wrangler@latest", "d1", "execute", database, "--json", "--command", query]
    if remote:
        command.append("--remote")
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return wrangler_results(json.loads(completed.stdout))


def wrangler_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            rows.extend(wrangler_results(item))
        return rows
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return payload["results"]
        if isinstance(payload.get("result"), list):
            return wrangler_results(payload["result"])
    return []


def authority_from_row(row: dict[str, Any]) -> Authority:
    metadata = parse_metadata(row.get("source_metadata_json"))
    return Authority(
        id=str(row["id"]),
        name=str(row.get("name") or row["id"]),
        home_page_url=clean_url(metadata.get("home_page")),
        source_url=clean_url(row.get("source_url")),
        contact_status=str(row.get("contact_status") or "missing"),
    )


def parse_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def should_scrape_authority(authority: Authority, authority_id: str | None) -> bool:
    if authority_id and authority.id != authority_id:
        return False
    return authority.contact_status in {"missing", "needs_review", "invalid"} and bool(authority.home_page_url)


def scrape_authorities(authorities: list[Authority], args: argparse.Namespace) -> dict[str, list[EmailCandidate]]:
    session = requests.Session()
    results: dict[str, list[EmailCandidate]] = {}
    for authority in authorities:
        results[authority.id] = scrape_authority(
            authority,
            session=session,
            timeout=args.timeout,
            max_pages=args.max_pages_per_authority,
            min_confidence=args.min_confidence,
            brave_api_key=os.environ.get("BRAVE_SEARCH_API_KEY") if args.brave_search else None,
            brave_results=args.brave_results,
        )
        sleep_between_authorities(args.delay_ms)
    return results


def sleep_between_authorities(delay_ms: int) -> None:
    if delay_ms <= 0:
        return
    time.sleep(random.uniform(delay_ms / 2, delay_ms) / 1000)


def scrape_authority(
    authority: Authority,
    *,
    session: requests.Session,
    timeout: float,
    max_pages: int,
    min_confidence: int,
    brave_api_key: str | None = None,
    brave_results: int = 8,
) -> list[EmailCandidate]:
    if not authority.home_page_url:
        return []

    seed_urls = brave_search_urls(authority, session=session, api_key=brave_api_key, limit=brave_results, timeout=timeout)
    pages = fetch_authority_pages(authority, session=session, timeout=timeout, max_pages=max_pages, seed_urls=seed_urls)
    candidates: dict[tuple[str, str], EmailCandidate] = {}
    for html, source_url, method in pages:
        for candidate in discover_page_emails(html, source_url=source_url, discovery_method=method):
            score = score_email(
                candidate.normalized_email,
                source_url=candidate.source_url,
                source_page_title=candidate.source_page_title,
                source_snippet=candidate.source_snippet,
                home_page_url=authority.home_page_url,
                discovery_method=candidate.discovery_method,
            )
            if score.confidence >= min_confidence:
                key = (candidate.normalized_email, candidate.source_url)
                candidates[key] = replace(candidate, confidence=score.confidence, confidence_reason=score.reason)
    return sorted(candidates.values(), key=lambda item: (-item.confidence, item.normalized_email, item.source_url))


def fetch_authority_pages(
    authority: Authority,
    *,
    session: requests.Session,
    timeout: float,
    max_pages: int,
    seed_urls: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    homepage = fetch_html(session, authority.home_page_url, timeout=timeout)
    pages = [(homepage, authority.home_page_url, "homepage")] if homepage else []
    visited = {authority.home_page_url} if homepage else set()
    seeds = [PageLink(url=url, text="Brave Search result") for url in seed_urls or []]
    fallback_links = find_candidate_links(homepage, authority.home_page_url, max_links=max_pages * 20) if homepage else []
    pending = sorted(seeds or fallback_links, key=link_priority)
    while pending and len(pages) < max_pages:
        link = pending.pop(0)
        if link.url in visited:
            continue
        visited.add(link.url)
        print(f"{authority.name}: fetching {len(pages) + 1}/{max_pages} {link.url}", flush=True)
        html = fetch_html(session, link.url, timeout=timeout)
        if html:
            pages.append((html, link.url, "linked_page"))
            for new_link in find_candidate_links(html, link.url, max_links=max_pages * 20):
                if new_link.url not in visited:
                    pending.append(new_link)
            pending = sorted(unique_links(pending).values(), key=link_priority)[: max_pages * 20]
    return pages


def brave_search_urls(
    authority: Authority, *, session: requests.Session, api_key: str | None, limit: int, timeout: float
) -> list[str]:
    if not api_key or not authority.home_page_url:
        return []
    host = urlparse(authority.home_page_url).hostname or ""
    query = f'site:{host} ("oia@" OR "lgoima@" OR "officialinformation@" OR "official.information@" OR "info@" OR "official information" OR OIA OR LGOIMA OR "information request")'
    try:
        response = session.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": limit, "country": "NZ", "search_lang": "en"},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key, "User-Agent": USER_AGENT},
            timeout=timeout,
        )
    except requests.RequestsError as error:
        print(f"Brave search failed for {authority.name}: {error}", flush=True)
        return []
    results = response.json().get("web", {}).get("results", []) if response.status_code < 400 else []
    urls = []
    for result in results:
        url = clean_url(result.get("url"))
        text = f"{result.get('title', '')} {result.get('description', '')}"
        if url and should_follow_link(url, text, authority.home_page_url):
            urls.append(url)
    print(f"{authority.name}: seeded {len(urls)} Brave result URLs", flush=True)
    return list(unique_links([PageLink(url=url, text="Brave Search result") for url in urls]).keys())


def fetch_html(session: requests.Session, url: str, *, timeout: float) -> str | None:
    started = time.monotonic()
    try:
        response = session.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, impersonate="chrome")
        if response.status_code in {403, 406}:
            response = session.get(url, timeout=timeout, impersonate="chrome")
    except requests.RequestsError as error:
        print(f"Fetch failed for {url}: {error}")
        return None
    if time.monotonic() - started > 5:
        print(f"Slow fetch ({time.monotonic() - started:.1f}s): {url}", flush=True)
    content_type = response.headers.get("content-type", "")
    if response.status_code >= 400 or ("html" not in content_type and content_type):
        return None
    return response.text


def discover_page_emails(html: str, *, source_url: str, discovery_method: str) -> list[EmailCandidate]:
    soup = BeautifulSoup(html, "html.parser")
    title = page_title(soup)
    found: dict[str, EmailCandidate] = {}
    for raw, snippet in mailto_addresses(soup) + visible_addresses(soup):
        normalized = normalize_email(raw)
        if not normalized:
            continue
        found.setdefault(
            normalized,
            EmailCandidate(
                email=normalized,
                normalized_email=normalized,
                source_url=source_url,
                source_page_title=title,
                source_snippet=short_snippet(snippet),
                discovery_method=discovery_method,
            ),
        )
    return list(found.values())


def mailto_addresses(soup: BeautifulSoup) -> list[tuple[str, str | None]]:
    addresses = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"]).strip()
        if href.lower().startswith("mailto:"):
            addresses.append((href, link.get_text(" ", strip=True) or None))
    return addresses


def visible_addresses(soup: BeautifulSoup) -> list[tuple[str, str | None]]:
    text = soup.get_text("\n", strip=True)
    candidates = []
    for line in text.splitlines():
        normalized_line = normalize_obfuscated_text(line)
        for match in EMAIL_RE.findall(normalized_line):
            candidates.append((match, line))
    return candidates


def normalize_obfuscated_text(value: str) -> str:
    normalized = re.sub(r"\s*(?:\[|\()?at(?:\]|\))\s*", "@", value, flags=re.I)
    normalized = re.sub(r"\s*(?:\[|\()?dot(?:\]|\))\s*", ".", normalized, flags=re.I)
    return normalized


def normalize_email(value: str) -> str | None:
    value = unquote(value.strip())
    if value.lower().startswith("mailto:"):
        value = value[7:]
    value = value.split("?", 1)[0].split("#", 1)[0]
    value = value.strip().strip(LEADING_EMAIL_PUNCTUATION).rstrip(TRAILING_EMAIL_PUNCTUATION)
    if value.count("@") != 1:
        return None

    local_part, domain = value.rsplit("@", 1)
    if not LOCAL_PART_RE.fullmatch(local_part):
        return None
    local_part = local_part.lower()
    try:
        domain = domain.lower().encode("idna").decode("ascii")
    except UnicodeError:
        return None

    if not is_usable_email(local_part, domain):
        return None
    return f"{local_part}@{domain}"


def is_usable_email(local_part: str, domain: str) -> bool:
    if "." not in domain:
        return False
    labels = domain.split(".")
    if labels[0] == "example" and len(labels) == 2:
        return False
    compact_local = re.sub(r"[^a-z0-9]", "", local_part)
    blocked = {re.sub(r"[^a-z0-9]", "", item) for item in NO_REPLY_LOCAL_PARTS} | {"privacy"}
    return compact_local not in blocked


def find_candidate_links(html: str, base_url: str, *, max_links: int = 500) -> list[PageLink]:
    soup = BeautifulSoup(html, "html.parser")
    links: dict[str, PageLink] = {}
    base = urlparse(base_url)
    for anchor in soup.find_all("a", href=True):
        absolute = clean_url(urljoin(base_url, str(anchor["href"])))
        if absolute and urlparse(absolute).netloc.lower() == base.netloc.lower():
            absolute = urlparse(absolute)._replace(scheme=base.scheme).geturl()
        text = anchor.get_text(" ", strip=True)
        if absolute and should_follow_link(absolute, text, base_url):
            links.setdefault(absolute, PageLink(url=absolute, text=text))
    return sorted(links.values(), key=link_priority)[:max_links]


def should_follow_link(url: str, text: str, base_url: str) -> bool:
    parsed = urlparse(url)
    base = urlparse(base_url)
    if parsed.netloc.lower() != base.netloc.lower():
        return False
    lowered = f"{url} {text}".lower()
    if any(term in lowered for term in AVOID_LINK_TERMS):
        return False
    if "||" in url or (parsed.query and any(term in parsed.query.lower() for term in ("filter", "page=", "pageurl", "start="))):
        return False
    if Path(parsed.path.lower()).suffix in SKIP_EXTENSIONS:
        return False
    return any(term in lowered for term in LINK_TERMS)


def unique_links(links: list[PageLink]) -> dict[str, PageLink]:
    unique: dict[str, PageLink] = {}
    for link in links:
        unique.setdefault(link.url, link)
    return unique


def link_priority(link: PageLink) -> tuple[int, int, str]:
    lowered = f"{link.url} {link.text}".lower()
    if any(term in lowered for term in ("official-information", "information-request", "lgoima", "oia")):
        return (0, len(link.url), link.url)
    if "contact" in lowered or "privacy" in lowered:
        return (1, len(link.url), link.url)
    if "about" in lowered:
        return (2, len(link.url), link.url)
    return (3, len(link.url), link.url)


def score_email(
    email: str,
    *,
    source_url: str,
    source_page_title: str | None,
    source_snippet: str | None,
    home_page_url: str | None,
    discovery_method: str,
) -> Score:
    local_part = email.split("@", 1)[0]
    score = 0
    reasons: list[str] = []
    score, reasons = score_local_part(local_part, score, reasons)
    score, reasons = score_context(source_url, source_page_title, source_snippet, score, reasons)
    score, reasons = score_source(email, home_page_url, discovery_method, score, reasons)
    score = max(0, min(100, score))
    return Score(confidence=score, reason="; ".join(reasons) or "no positive signals")


def score_local_part(local_part: str, score: int, reasons: list[str]) -> tuple[int, list[str]]:
    compact_local = re.sub(r"[^a-z0-9]", "", local_part)
    if local_part in STRONG_LOCAL_PARTS or compact_local in {part.replace(".", "") for part in STRONG_LOCAL_PARTS}:
        score += 35
        reasons.append("strong local part")
    elif local_part in MEDIUM_LOCAL_PARTS:
        score += 20
        reasons.append("medium local part")
    if local_part not in STRONG_LOCAL_PARTS and looks_personal(local_part):
        score -= 30
        reasons.append("personal-looking local part")
    if compact_local in {re.sub(r"[^a-z0-9]", "", item) for item in WRONG_LOCAL_TERMS}:
        score -= 25
        reasons.append("usually wrong local part")
    if compact_local in {re.sub(r"[^a-z0-9]", "", item) for item in NO_REPLY_LOCAL_PARTS}:
        score -= 40
        reasons.append("no-reply local part")
    return score, reasons


def score_context(
    source_url: str,
    source_page_title: str | None,
    source_snippet: str | None,
    score: int,
    reasons: list[str],
) -> tuple[int, list[str]]:
    lowered_url = source_url.lower()
    context = f"{source_page_title or ''} {source_snippet or ''}".lower()
    if any(term in lowered_url for term in ("official-information", "information-request", "oia", "lgoima")):
        score += 20
        reasons.append("source URL has request terms")
    if any(term in context for term in CONTEXT_TERMS):
        score += 15
        reasons.append("page text has request terms")
    return score, reasons


def score_source(
    email: str,
    home_page_url: str | None,
    discovery_method: str,
    score: int,
    reasons: list[str],
) -> tuple[int, list[str]]:
    if home_page_url:
        if domains_match(email.rsplit("@", 1)[1], urlparse(home_page_url).hostname or ""):
            score += 10
            reasons.append("email domain matches authority site")
        elif re.sub(r"[^a-z0-9]", "", email.split("@", 1)[0]) not in {part.replace(".", "") for part in STRONG_LOCAL_PARTS}:
            score -= 30
            reasons.append("email domain differs from authority site")
    if discovery_method in {"homepage", "linked_page"}:
        score += 5
        reasons.append("official authority source")
    return score, reasons


def looks_personal(local_part: str) -> bool:
    parts = re.split(r"[._-]+", local_part)
    return len(parts) == 2 and all(re.fullmatch(r"[a-z]{2,}", part) for part in parts)


def domains_match(email_domain: str, host: str) -> bool:
    host = host.lower().removeprefix("www.")
    email_domain = email_domain.lower()
    return email_domain == host or email_domain.endswith(f".{host}") or host.endswith(f".{email_domain}")


def build_scrape_sql(candidates_by_authority: dict[str, list[EmailCandidate]]) -> str:
    statements: list[str] = []
    for authority_id, candidates in candidates_by_authority.items():
        for candidate in candidates:
            statements.append(candidate_upsert_statement(authority_id, candidate))
        if candidates:
            statements.append(mark_needs_review_statement(authority_id))
    return "\n".join(statements) + ("\n" if statements else "")


def candidate_upsert_statement(authority_id: str, candidate: EmailCandidate) -> str:
    candidate_key = candidate_id(authority_id, candidate.normalized_email, candidate.source_url)
    return f"""
INSERT INTO sunlight_authority_contact_candidates (
  id,
  authority_id,
  email,
  normalized_email,
  source_url,
  source_page_title,
  source_snippet,
  discovery_method,
  confidence,
  confidence_reason,
  status
) VALUES (
  {sql(candidate_key)},
  {sql(authority_id)},
  {sql(candidate.email)},
  {sql(candidate.normalized_email)},
  {sql(candidate.source_url)},
  {sql(candidate.source_page_title)},
  {sql(candidate.source_snippet)},
  {sql(candidate.discovery_method)},
  {candidate.confidence},
  {sql(candidate.confidence_reason)},
  'candidate'
)
ON CONFLICT(authority_id, normalized_email, source_url) DO UPDATE SET
  email = excluded.email,
  source_page_title = excluded.source_page_title,
  source_snippet = excluded.source_snippet,
  discovery_method = excluded.discovery_method,
  confidence = excluded.confidence,
  confidence_reason = excluded.confidence_reason,
  status = CASE
    WHEN sunlight_authority_contact_candidates.status IN ('accepted', 'rejected')
    THEN sunlight_authority_contact_candidates.status
    ELSE excluded.status
  END,
  last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now');
""".strip()


def mark_needs_review_statement(authority_id: str) -> str:
    return f"""
UPDATE sunlight_authorities
SET
  contact_status = 'needs_review',
  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE id = {sql(authority_id)}
  AND contact_status IN ('missing', 'invalid');
""".strip()


def candidate_id(authority_id: str, normalized_email: str, source_url: str) -> str:
    digest = hashlib.sha256(f"{authority_id}\0{normalized_email}\0{source_url}".encode()).hexdigest()[:24]
    return f"acc_{digest}"


def apply_sql(database: str, generated_sql: str, *, remote: bool) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as file:
        file.write(generated_sql)
        sql_path = Path(file.name)

    command = ["pnpm", "dlx", "wrangler@latest", "d1", "execute", database, "--file", str(sql_path)]
    if remote:
        command.append("--remote")

    try:
        subprocess.run(command, check=True)
    finally:
        sql_path.unlink(missing_ok=True)


def clean_url(value: Any) -> str | None:
    if not value:
        return None
    parsed = urlparse(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return parsed._replace(fragment="").geturl()


def page_title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return " ".join(soup.title.string.split())[:160]
    return None


def short_snippet(value: str | None, *, limit: int = 240) -> str | None:
    if not value:
        return None
    collapsed = " ".join(value.split())
    return collapsed[:limit]


def sql(value: str | None) -> str:
    return "NULL" if value is None else "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
