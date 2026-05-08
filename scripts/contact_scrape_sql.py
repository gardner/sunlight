from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

AUTO_VERIFY_CONFIDENCE = 80
CLEAR_WIN_CONFIDENCE = 65
CLEAR_WIN_MARGIN = 15
SINGLE_CANDIDATE_CONFIDENCE = 50


class EmailCandidateLike(Protocol):
    email: str
    normalized_email: str
    source_url: str
    source_page_title: str | None
    source_snippet: str | None
    discovery_method: str
    confidence: int
    confidence_reason: str


@dataclass(frozen=True)
class CandidateGroup:
    normalized_email: str
    confidence: int


def build_scrape_sql(candidates_by_authority: dict[str, list[EmailCandidateLike]]) -> str:
    statements: list[str] = []
    for authority_id, candidates in candidates_by_authority.items():
        auto_verified_email = choose_auto_verified_email(candidates)
        for candidate in candidates:
            status = "accepted" if candidate.normalized_email == auto_verified_email else "candidate"
            statements.append(candidate_upsert_statement(authority_id, candidate, status=status))
        if auto_verified_email:
            statements.append(mark_auto_verified_statement(authority_id, auto_verified_email))
            statements.append(auto_verified_audit_statement(authority_id, auto_verified_email))
            statements.append(scrape_attempt_statement(authority_id, "auto_verified", len(candidates), auto_verified_email))
        elif candidates:
            statements.append(mark_needs_review_statement(authority_id))
            statements.append(scrape_attempt_statement(authority_id, "needs_review", len(candidates), None))
        else:
            statements.append(scrape_attempt_statement(authority_id, "no_candidate", 0, None))
    return "\n".join(statements) + ("\n" if statements else "")


def choose_auto_verified_email(candidates: list[EmailCandidateLike]) -> str | None:
    groups = grouped_candidates(candidates)
    if not groups:
        return None

    best = groups[0]
    runner_up = groups[1] if len(groups) > 1 else None
    if len(groups) == 1 and best.confidence >= SINGLE_CANDIDATE_CONFIDENCE:
        return best.normalized_email
    if best.confidence >= AUTO_VERIFY_CONFIDENCE:
        return best.normalized_email
    if runner_up and best.confidence >= CLEAR_WIN_CONFIDENCE:
        if best.confidence - runner_up.confidence >= CLEAR_WIN_MARGIN:
            return best.normalized_email
    return None


def grouped_candidates(candidates: list[EmailCandidateLike]) -> list[CandidateGroup]:
    groups: dict[str, int] = {}
    for candidate in candidates:
        current = groups.get(candidate.normalized_email, 0)
        groups[candidate.normalized_email] = max(current, candidate.confidence)
    return sorted(
        [CandidateGroup(email, confidence) for email, confidence in groups.items()],
        key=lambda group: (-group.confidence, group.normalized_email),
    )


def candidate_upsert_statement(
    authority_id: str,
    candidate: EmailCandidateLike,
    *,
    status: str,
) -> str:
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
  {sql(status)}
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


def mark_auto_verified_statement(authority_id: str, normalized_email: str) -> str:
    return f"""
UPDATE sunlight_authorities
SET
  primary_request_email = {sql(normalized_email)},
  contact_status = 'verified',
  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE id = {sql(authority_id)}
  AND contact_status IN ('missing', 'needs_review', 'invalid')
  AND EXISTS (
    SELECT 1
    FROM sunlight_authority_contact_candidates
    WHERE authority_id = {sql(authority_id)}
      AND normalized_email = {sql(normalized_email)}
      AND status = 'accepted'
  );
""".strip()


def auto_verified_audit_statement(authority_id: str, normalized_email: str) -> str:
    audit_key = audit_id(authority_id, normalized_email)
    return f"""
INSERT OR IGNORE INTO sunlight_audit_events (
  id,
  entity_type,
  entity_id,
  event_type,
  actor_type,
  actor_id,
  metadata_json
)
SELECT
  {sql(audit_key)},
  'authority',
  {sql(authority_id)},
  'authority.contact_auto_verified',
  'automated_worker',
  'contact_scraper',
  json_object(
    'email', normalized_email,
    'evidence_count', evidence_count,
    'best_confidence', best_confidence,
    'source_urls', source_urls
  )
FROM (
  SELECT
    normalized_email,
    COUNT(*) AS evidence_count,
    MAX(confidence) AS best_confidence,
    json_group_array(source_url) AS source_urls
  FROM sunlight_authority_contact_candidates
  WHERE authority_id = {sql(authority_id)}
    AND normalized_email = {sql(normalized_email)}
    AND status = 'accepted'
)
WHERE evidence_count > 0;
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


def scrape_attempt_statement(
    authority_id: str,
    outcome: str,
    candidate_count: int,
    auto_verified_email: str | None,
) -> str:
    return f"""
INSERT INTO sunlight_authority_contact_scrape_attempts (
  id,
  authority_id,
  outcome,
  candidate_count,
  auto_verified_email
) VALUES (
  'sca_' || lower(hex(randomblob(16))),
  {sql(authority_id)},
  {sql(outcome)},
  {candidate_count},
  {sql(auto_verified_email)}
);
""".strip()


def candidate_id(authority_id: str, normalized_email: str, source_url: str) -> str:
    digest = hashlib.sha256(f"{authority_id}\0{normalized_email}\0{source_url}".encode()).hexdigest()[:24]
    return f"acc_{digest}"


def audit_id(authority_id: str, normalized_email: str) -> str:
    digest = hashlib.sha256(f"{authority_id}\0{normalized_email}\0auto_verified".encode()).hexdigest()[:24]
    return f"aud_{digest}"


def sql(value: str | None) -> str:
    return "NULL" if value is None else "'" + value.replace("'", "''") + "'"
