from __future__ import annotations

import argparse
import hashlib
import json
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
    ".7z",
    ".avi",
    ".doc",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".rss",
    ".svg",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}
LINK_TERMS = {
    "about",
    "contact",
    "contacts",
    "information-request",
    "information-requests",
    "lgoima",
    "official-information",
    "official_information",
    "oia",
    "privacy",
}
AVOID_LINK_TERMS = {
    "careers",
    "facebook",
    "instagram",
    "jobs",
    "linkedin",
    "login",
    "procurement",
    "rss",
    "tenders",
    "twitter",
    "x.com",
    "youtube",
}
CONTEXT_TERMS = {
    "contact us",
    "information request",
    "lgoima",
    "local government official information",
    "make a request",
    "official information",
    "oia",
    "privacy",
    "request information",
}
STRONG_LOCAL_PARTS = {
    "information",
    "information.requests",
    "informationrequests",
    "lgoinfo",
    "lgoima",
    "official.information",
    "officialinformation",
    "oia",
    "privacy",
    "requests",
}
MEDIUM_LOCAL_PARTS = {"admin", "contact", "enquiries", "info", "records"}
WRONG_LOCAL_TERMS = {"careers", "hr", "jobs", "media", "news", "procurement", "recruitment", "tenders", "webmaster"}
NO_REPLY_LOCAL_PARTS = {"bounce", "donotreply", "do-not-reply", "no-reply", "noreply"}


@dataclass(frozen=True)
class Agency:
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
    parser = argparse.ArgumentParser(description="Scrape public agency contact email candidates.")
    parser.add_argument("--database", default="sunlight-requests", help="D1 database name.")
    parser.add_argument("--remote", action="store_true", help="Read/apply against the remote D1 database.")
    parser.add_argument("--agency-id", help="Only scrape one agency id.")
    parser.add_argument("--source-file", type=Path, help="JSON file containing agency rows.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum agency rows to scrape.")
    parser.add_argument("--max-pages-per-agency", type=int, default=8, help="Maximum pages to fetch per agency.")
    parser.add_argument("--write-sql", type=Path, help="Write generated SQL to this path.")
    parser.add_argument("--dry-run", action="store_true", help="Print a summary without applying generated SQL.")
    parser.add_argument("--min-confidence", type=int, default=50, help="Minimum confidence to keep.")
    parser.add_argument("--timeout", type=float, default=20, help="Request timeout in seconds.")
    parser.add_argument("--delay-ms", type=int, default=500, help="Maximum delay between agencies.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    agencies = load_agencies(args)
    if not agencies:
        print("No agencies matched.")
        return 0

    candidates_by_agency = scrape_agencies(agencies, args)
    generated_sql = build_scrape_sql(candidates_by_agency)
    total_candidates = sum(len(candidates) for candidates in candidates_by_agency.values())
    print(f"Scraped {len(agencies)} agencies and found {total_candidates} candidate contacts.")

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


def load_agencies(args: argparse.Namespace) -> list[Agency]:
    if args.source_file:
        rows = json.loads(args.source_file.read_text())
    else:
        rows = fetch_agency_rows(args.database, remote=args.remote, agency_id=args.agency_id, limit=args.limit)
    agencies = [agency_from_row(row) for row in rows]
    return [agency for agency in agencies if should_scrape_agency(agency, args.agency_id)][: args.limit]


def fetch_agency_rows(database: str, *, remote: bool, agency_id: str | None, limit: int) -> list[dict[str, Any]]:
    where = ["status = 'active'", "contact_status IN ('missing', 'needs_review', 'invalid')"]
    if agency_id:
        where.append(f"id = {sql(agency_id)}")
    query = f"""
SELECT id, name, source_url, source_metadata_json, contact_status
FROM sunlight_agencies
WHERE {' AND '.join(where)}
ORDER BY name
LIMIT {int(limit)}
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


def agency_from_row(row: dict[str, Any]) -> Agency:
    metadata = parse_metadata(row.get("source_metadata_json"))
    return Agency(
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


def should_scrape_agency(agency: Agency, agency_id: str | None) -> bool:
    if agency_id and agency.id != agency_id:
        return False
    return agency.contact_status in {"missing", "needs_review", "invalid"} and bool(agency.home_page_url)


def scrape_agencies(agencies: list[Agency], args: argparse.Namespace) -> dict[str, list[EmailCandidate]]:
    session = requests.Session()
    results: dict[str, list[EmailCandidate]] = {}
    for agency in agencies:
        results[agency.id] = scrape_agency(
            agency,
            session=session,
            timeout=args.timeout,
            max_pages=args.max_pages_per_agency,
            min_confidence=args.min_confidence,
        )
        sleep_between_agencies(args.delay_ms)
    return results


def sleep_between_agencies(delay_ms: int) -> None:
    if delay_ms <= 0:
        return
    time.sleep(random.uniform(delay_ms / 2, delay_ms) / 1000)


def scrape_agency(
    agency: Agency,
    *,
    session: requests.Session,
    timeout: float,
    max_pages: int,
    min_confidence: int,
) -> list[EmailCandidate]:
    if not agency.home_page_url:
        return []

    pages = fetch_agency_pages(agency, session=session, timeout=timeout, max_pages=max_pages)
    candidates: dict[tuple[str, str], EmailCandidate] = {}
    for html, source_url, method in pages:
        for candidate in discover_page_emails(html, source_url=source_url, discovery_method=method):
            score = score_email(
                candidate.normalized_email,
                source_url=candidate.source_url,
                source_page_title=candidate.source_page_title,
                source_snippet=candidate.source_snippet,
                home_page_url=agency.home_page_url,
                discovery_method=candidate.discovery_method,
            )
            if score.confidence >= min_confidence:
                key = (candidate.normalized_email, candidate.source_url)
                candidates[key] = replace(candidate, confidence=score.confidence, confidence_reason=score.reason)
    return sorted(candidates.values(), key=lambda item: (-item.confidence, item.normalized_email, item.source_url))


def fetch_agency_pages(
    agency: Agency,
    *,
    session: requests.Session,
    timeout: float,
    max_pages: int,
) -> list[tuple[str, str, str]]:
    homepage = fetch_html(session, agency.home_page_url, timeout=timeout)
    if not homepage:
        return []

    pages = [(homepage, agency.home_page_url, "homepage")]
    links = find_candidate_links(homepage, agency.home_page_url)
    for link in links[: max(0, max_pages - 1)]:
        html = fetch_html(session, link.url, timeout=timeout)
        if html:
            pages.append((html, link.url, "linked_page"))
    return pages


def fetch_html(session: requests.Session, url: str, *, timeout: float) -> str | None:
    try:
        response = session.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, impersonate="chrome")
    except requests.RequestsError as error:
        print(f"Fetch failed for {url}: {error}")
        return None
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
    return compact_local not in {re.sub(r"[^a-z0-9]", "", item) for item in NO_REPLY_LOCAL_PARTS}


def find_candidate_links(html: str, base_url: str, *, max_links: int = 24) -> list[PageLink]:
    soup = BeautifulSoup(html, "html.parser")
    links: dict[str, PageLink] = {}
    for anchor in soup.find_all("a", href=True):
        absolute = clean_url(urljoin(base_url, str(anchor["href"])))
        text = anchor.get_text(" ", strip=True)
        if absolute and should_follow_link(absolute, text, base_url):
            links.setdefault(absolute, PageLink(url=absolute, text=text))
    return list(links.values())[:max_links]


def should_follow_link(url: str, text: str, base_url: str) -> bool:
    parsed = urlparse(url)
    base = urlparse(base_url)
    if parsed.netloc.lower() != base.netloc.lower():
        return False
    lowered = f"{url} {text}".lower()
    if any(term in lowered for term in AVOID_LINK_TERMS):
        return False
    if Path(parsed.path.lower()).suffix in SKIP_EXTENSIONS:
        return False
    return any(term in lowered for term in LINK_TERMS)


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
    if looks_personal(local_part):
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
    if home_page_url and domains_match(email.rsplit("@", 1)[1], urlparse(home_page_url).hostname or ""):
        score += 10
        reasons.append("email domain matches agency site")
    if discovery_method in {"homepage", "linked_page"}:
        score += 5
        reasons.append("official agency source")
    return score, reasons


def looks_personal(local_part: str) -> bool:
    parts = re.split(r"[._-]+", local_part)
    return len(parts) == 2 and all(re.fullmatch(r"[a-z]{2,}", part) for part in parts)


def domains_match(email_domain: str, host: str) -> bool:
    host = host.lower().removeprefix("www.")
    email_domain = email_domain.lower()
    return email_domain == host or email_domain.endswith(f".{host}") or host.endswith(f".{email_domain}")


def build_scrape_sql(candidates_by_agency: dict[str, list[EmailCandidate]]) -> str:
    statements: list[str] = []
    for agency_id, candidates in candidates_by_agency.items():
        for candidate in candidates:
            statements.append(candidate_upsert_statement(agency_id, candidate))
        if candidates:
            statements.append(mark_needs_review_statement(agency_id))
    return "\n".join(statements) + ("\n" if statements else "")


def candidate_upsert_statement(agency_id: str, candidate: EmailCandidate) -> str:
    candidate_key = candidate_id(agency_id, candidate.normalized_email, candidate.source_url)
    return f"""
INSERT INTO sunlight_agency_contact_candidates (
  id,
  agency_id,
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
  {sql(agency_id)},
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
ON CONFLICT(agency_id, normalized_email, source_url) DO UPDATE SET
  email = excluded.email,
  source_page_title = excluded.source_page_title,
  source_snippet = excluded.source_snippet,
  discovery_method = excluded.discovery_method,
  confidence = excluded.confidence,
  confidence_reason = excluded.confidence_reason,
  status = CASE
    WHEN sunlight_agency_contact_candidates.status IN ('accepted', 'rejected')
    THEN sunlight_agency_contact_candidates.status
    ELSE excluded.status
  END,
  last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now');
""".strip()


def mark_needs_review_statement(agency_id: str) -> str:
    return f"""
UPDATE sunlight_agencies
SET
  contact_status = 'needs_review',
  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE id = {sql(agency_id)}
  AND contact_status IN ('missing', 'invalid');
""".strip()


def candidate_id(agency_id: str, normalized_email: str, source_url: str) -> str:
    digest = hashlib.sha256(f"{agency_id}\0{normalized_email}\0{source_url}".encode()).hexdigest()[:24]
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
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
