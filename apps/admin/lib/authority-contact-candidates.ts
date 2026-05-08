export type ContactCandidateStatus = "candidate" | "accepted" | "rejected" | "stale";
export type ContactDecision = "primary" | "secondary" | "rejected";

export interface ContactCandidateEvidence {
  confidence: number;
  confidence_reason: string;
  discovery_method: string;
  first_seen_at: string;
  id: string;
  last_seen_at: string;
  source_page_title: string | null;
  source_snippet: string | null;
  source_url: string;
  status: ContactCandidateStatus;
}

export interface ContactCandidateGroup {
  candidate_count: number;
  confidence: number;
  email: string;
  evidence: ContactCandidateEvidence[];
  normalized_email: string;
  status: ContactCandidateStatus;
}

export interface ContactDecisionActor {
  id?: string | null;
  email?: string | null;
}

export interface SqlStatement {
  bindings: Array<number | string | null>;
  sql: string;
}

export function buildContactCandidateListQuery(authorityId: string): SqlStatement {
  return {
    bindings: [authorityId],
    sql: `
      SELECT
        id,
        email,
        normalized_email,
        source_url,
        source_page_title,
        source_snippet,
        discovery_method,
        confidence,
        confidence_reason,
        status,
        first_seen_at,
        last_seen_at
      FROM sunlight_authority_contact_candidates
      WHERE authority_id = ?
      ORDER BY
        normalized_email,
        CASE status
          WHEN 'accepted' THEN 0
          WHEN 'candidate' THEN 1
          WHEN 'rejected' THEN 2
          ELSE 3
        END,
        confidence DESC,
        source_url
    `,
  };
}

export async function listContactCandidateGroups(
  db: D1Database,
  authorityId: string,
): Promise<ContactCandidateGroup[]> {
  const query = buildContactCandidateListQuery(authorityId);
  const result = await db.prepare(query.sql).bind(...query.bindings).all<ContactCandidateRow>();
  return groupContactCandidates(result.results);
}

export function groupContactCandidates(rows: ContactCandidateRow[]): ContactCandidateGroup[] {
  const groups = new Map<string, ContactCandidateGroup>();

  for (const row of rows) {
    const group = groups.get(row.normalized_email) ?? emptyGroup(row);
    group.candidate_count += 1;
    group.confidence = Math.max(group.confidence, row.confidence);
    group.status = mergeStatus(group.status, row.status);
    group.evidence.push({
      confidence: row.confidence,
      confidence_reason: row.confidence_reason,
      discovery_method: row.discovery_method,
      first_seen_at: row.first_seen_at,
      id: row.id,
      last_seen_at: row.last_seen_at,
      source_page_title: row.source_page_title,
      source_snippet: row.source_snippet,
      source_url: row.source_url,
      status: row.status,
    });
    groups.set(row.normalized_email, group);
  }

  return [...groups.values()].sort(compareContactCandidateGroups);
}

export async function acceptContactCandidate(
  db: D1Database,
  input: {
    actor?: ContactDecisionActor;
    auditId?: string;
    authorityId: string;
    decision: Exclude<ContactDecision, "rejected">;
    email: string;
  },
): Promise<void> {
  const statements = buildAcceptContactCandidateStatements({
    ...input,
    auditId: input.auditId ?? auditId(),
  });
  await runStatements(db, statements);
}

export async function rejectContactCandidate(
  db: D1Database,
  input: {
    actor?: ContactDecisionActor;
    auditId?: string;
    authorityId: string;
    email: string;
  },
): Promise<void> {
  const statements = buildRejectContactCandidateStatements({
    ...input,
    auditId: input.auditId ?? auditId(),
  });
  await runStatements(db, statements);
}

export async function markAuthorityContactInvalid(
  db: D1Database,
  input: {
    actor?: ContactDecisionActor;
    auditId?: string;
    authorityId: string;
  },
): Promise<void> {
  const statements = buildMarkAuthorityContactInvalidStatements({
    ...input,
    auditId: input.auditId ?? auditId(),
  });
  await runStatements(db, statements);
}

export function buildAcceptContactCandidateStatements(input: {
  actor?: ContactDecisionActor;
  auditId: string;
  authorityId: string;
  decision: Exclude<ContactDecision, "rejected">;
  email: string;
}): SqlStatement[] {
  const email = requireNormalizedEmail(input.email);
  const statements = [
    buildSetCandidateStatusStatement(input.authorityId, email, "accepted"),
    input.decision === "primary"
      ? buildSetPrimaryContactStatement(input.authorityId, email)
      : buildAddSecondaryContactStatement(input.authorityId, email),
    buildCandidateAuditStatement({
      actor: input.actor,
      auditId: input.auditId,
      authorityId: input.authorityId,
      email,
      eventType: `authority.contact_candidate_accepted_${input.decision}`,
      status: "accepted",
    }),
  ];
  return statements;
}

export function buildRejectContactCandidateStatements(input: {
  actor?: ContactDecisionActor;
  auditId: string;
  authorityId: string;
  email: string;
}): SqlStatement[] {
  const email = requireNormalizedEmail(input.email);
  return [
    buildSetCandidateStatusStatement(input.authorityId, email, "rejected"),
    buildCandidateAuditStatement({
      actor: input.actor,
      auditId: input.auditId,
      authorityId: input.authorityId,
      email,
      eventType: "authority.contact_candidate_rejected",
      status: "rejected",
    }),
  ];
}

export function buildMarkAuthorityContactInvalidStatements(input: {
  actor?: ContactDecisionActor;
  auditId: string;
  authorityId: string;
}): SqlStatement[] {
  return [
    {
      bindings: [
        input.auditId,
        actorId(input.actor),
        actorEmail(input.actor),
        input.authorityId,
      ],
      sql: `
        INSERT INTO sunlight_audit_events (
          id,
          entity_type,
          entity_id,
          event_type,
          actor_type,
          actor_id,
          actor_email,
          metadata_json
        )
        SELECT
          ?,
          'authority',
          id,
          'authority.contact_marked_invalid',
          'admin',
          ?,
          ?,
          json_object(
            'previous_contact_status', contact_status,
            'primary_request_email', primary_request_email
          )
        FROM sunlight_authorities
        WHERE id = ?
      `,
    },
    {
      bindings: [input.authorityId],
      sql: `
        UPDATE sunlight_authorities
        SET contact_status = 'invalid',
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    },
    {
      bindings: [input.authorityId],
      sql: `
        UPDATE sunlight_authority_contact_candidates
        SET status = 'rejected',
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE authority_id = ?
          AND status = 'candidate'
      `,
    },
  ];
}

function buildSetCandidateStatusStatement(
  authorityId: string,
  email: string,
  status: Extract<ContactCandidateStatus, "accepted" | "rejected">,
): SqlStatement {
  return {
    bindings: [status, authorityId, email],
    sql: `
      UPDATE sunlight_authority_contact_candidates
      SET status = ?,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE authority_id = ?
        AND normalized_email = ?
        AND status != 'stale'
    `,
  };
}

function buildSetPrimaryContactStatement(authorityId: string, email: string): SqlStatement {
  return {
    bindings: [email, authorityId, authorityId, email],
    sql: `
      UPDATE sunlight_authorities
      SET primary_request_email = ?,
          contact_status = 'verified',
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
        AND EXISTS (
          SELECT 1
          FROM sunlight_authority_contact_candidates
          WHERE authority_id = ?
            AND normalized_email = ?
            AND status = 'accepted'
        )
    `,
  };
}

function buildAddSecondaryContactStatement(authorityId: string, email: string): SqlStatement {
  return {
    bindings: [email, email, email, authorityId, authorityId, email],
    sql: `
      UPDATE sunlight_authorities
      SET secondary_request_emails_json = CASE
            WHEN json_valid(secondary_request_emails_json)
              AND EXISTS (
                SELECT 1
                FROM json_each(secondary_request_emails_json)
                WHERE value = ?
              )
            THEN secondary_request_emails_json
            WHEN json_valid(secondary_request_emails_json)
            THEN json_insert(secondary_request_emails_json, '$[#]', ?)
            ELSE json_array(?)
          END,
          contact_status = CASE
            WHEN primary_request_email IS NOT NULL THEN 'verified'
            ELSE contact_status
          END,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
        AND EXISTS (
          SELECT 1
          FROM sunlight_authority_contact_candidates
          WHERE authority_id = ?
            AND normalized_email = ?
            AND status = 'accepted'
        )
    `,
  };
}

function buildCandidateAuditStatement(input: {
  actor?: ContactDecisionActor;
  auditId: string;
  authorityId: string;
  email: string;
  eventType: string;
  status: ContactCandidateStatus;
}): SqlStatement {
  return {
    bindings: [
      input.auditId,
      input.authorityId,
      input.eventType,
      actorId(input.actor),
      actorEmail(input.actor),
      input.authorityId,
      input.email,
      input.status,
    ],
    sql: `
      INSERT INTO sunlight_audit_events (
        id,
        entity_type,
        entity_id,
        event_type,
        actor_type,
        actor_id,
        actor_email,
        metadata_json
      )
      SELECT
        ?,
        'authority',
        ?,
        ?,
        'admin',
        ?,
        ?,
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
        WHERE authority_id = ?
          AND normalized_email = ?
          AND status = ?
      )
      WHERE evidence_count > 0
    `,
  };
}

function emptyGroup(row: ContactCandidateRow): ContactCandidateGroup {
  return {
    candidate_count: 0,
    confidence: 0,
    email: row.email,
    evidence: [],
    normalized_email: row.normalized_email,
    status: row.status,
  };
}

function compareContactCandidateGroups(
  left: ContactCandidateGroup,
  right: ContactCandidateGroup,
): number {
  return (
    statusRank(left.status) - statusRank(right.status) ||
    right.confidence - left.confidence ||
    left.normalized_email.localeCompare(right.normalized_email)
  );
}

function mergeStatus(
  current: ContactCandidateStatus,
  next: ContactCandidateStatus,
): ContactCandidateStatus {
  return statusRank(next) < statusRank(current) ? next : current;
}

function statusRank(status: ContactCandidateStatus): number {
  return { accepted: 0, candidate: 1, rejected: 2, stale: 3 }[status];
}

async function runStatements(db: D1Database, statements: SqlStatement[]): Promise<void> {
  for (const statement of statements) {
    await db.prepare(statement.sql).bind(...statement.bindings).run();
  }
}

function requireNormalizedEmail(value: string): string {
  const normalized = normalizeEmail(value);
  if (!normalized) {
    throw new Error("Contact decision requires a valid email address");
  }
  return normalized;
}

function normalizeEmail(value: string): string | null {
  const email = value.trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return null;
  }
  return email;
}

function actorId(actor: ContactDecisionActor | undefined): string | null {
  return actor?.id ?? null;
}

function actorEmail(actor: ContactDecisionActor | undefined): string | null {
  return actor?.email ?? null;
}

function auditId(): string {
  return `aud_${crypto.randomUUID().replaceAll("-", "")}`;
}

interface ContactCandidateRow extends ContactCandidateEvidence {
  email: string;
  normalized_email: string;
}
