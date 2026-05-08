export type ContactStatus = "missing" | "needs_review" | "verified" | "invalid";
export type AgencyStatus = "active" | "inactive";

export interface AgencyFilters {
  contactStatus?: ContactStatus;
  search?: string;
  status?: AgencyStatus;
}

export interface AgencyListItem {
  contact_status: ContactStatus;
  id: string;
  legal_regime: "OIA" | "LGOIMA" | "other";
  name: string;
  primary_request_email: string | null;
  slug: string;
  status: AgencyStatus;
}

export interface AgencyDetail extends AgencyListItem {
  default_cadence: string;
  default_template_id: string | null;
  notes: string | null;
  source: string | null;
  source_id: string | null;
  source_metadata_json: string;
  source_updated_at: string | null;
  source_url: string | null;
}

const CONTACT_STATUSES = new Set<ContactStatus>([
  "missing",
  "needs_review",
  "verified",
  "invalid",
]);

const AGENCY_STATUSES = new Set<AgencyStatus>(["active", "inactive"]);

export function normalizeAgencyFilters(input: Record<string, string | undefined>): AgencyFilters {
  const filters: AgencyFilters = {};
  const contactStatus = input.contactStatus;
  const status = input.status;
  const search = input.search?.trim();

  if (contactStatus && CONTACT_STATUSES.has(contactStatus as ContactStatus)) {
    filters.contactStatus = contactStatus as ContactStatus;
  }
  if (status && AGENCY_STATUSES.has(status as AgencyStatus)) {
    filters.status = status as AgencyStatus;
  }
  if (search) {
    filters.search = search;
  }

  return filters;
}

export function buildAgencyListQuery(filters: AgencyFilters = {}) {
  const where = [];
  const bindings: string[] = [];

  if (filters.contactStatus) {
    where.push("contact_status = ?");
    bindings.push(filters.contactStatus);
  }
  if (filters.status) {
    where.push("status = ?");
    bindings.push(filters.status);
  }
  if (filters.search) {
    where.push("(lower(name) LIKE ? OR lower(slug) LIKE ?)");
    const search = `%${filters.search.toLowerCase()}%`;
    bindings.push(search, search);
  }

  const sql = `
    SELECT
      id,
      name,
      slug,
      legal_regime,
      primary_request_email,
      contact_status,
      status
    FROM sunlight_agencies
    ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
    ORDER BY
      CASE contact_status
        WHEN 'verified' THEN 0
        WHEN 'needs_review' THEN 1
        WHEN 'missing' THEN 2
        ELSE 3
      END,
      name
    LIMIT 100
  `;

  return { bindings, sql };
}

export async function listAgencies(
  db: D1Database,
  filters: AgencyFilters = {},
): Promise<AgencyListItem[]> {
  const query = buildAgencyListQuery(filters);
  const result = await db.prepare(query.sql).bind(...query.bindings).all<AgencyListItem>();
  return result.results;
}

export async function getAgency(db: D1Database, agencyId: string): Promise<AgencyDetail | null> {
  return db
    .prepare(
      `
        SELECT
          id,
          name,
          slug,
          legal_regime,
          primary_request_email,
          contact_status,
          status,
          default_cadence,
          default_template_id,
          source,
          source_id,
          source_url,
          source_updated_at,
          source_metadata_json,
          notes
        FROM sunlight_agencies
        WHERE id = ?
        LIMIT 1
      `,
    )
    .bind(agencyId)
    .first<AgencyDetail>();
}

export function buildVerifyContactUpdate(input: { agencyId: string; email: string }) {
  const email = normalizeEmail(input.email);
  if (!email) {
    throw new Error("Contact verification requires a valid email address");
  }

  return {
    bindings: [email, input.agencyId],
    sql: `
      UPDATE sunlight_agencies
      SET primary_request_email = ?,
          contact_status = 'verified',
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
    `,
  };
}

export async function verifyAgencyContact(
  db: D1Database,
  input: { agencyId: string; email: string },
): Promise<void> {
  const query = buildVerifyContactUpdate(input);
  await db.prepare(query.sql).bind(...query.bindings).run();
}

export function buildAssignTemplateUpdate(input: { agencyId: string; templateId: string }) {
  if (!input.agencyId || !input.templateId) {
    throw new Error("Agency and template are required");
  }

  return {
    bindings: [input.templateId, input.agencyId],
    sql: `
      UPDATE sunlight_agencies
      SET default_template_id = ?,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
    `,
  };
}

export async function assignAgencyTemplate(
  db: D1Database,
  input: { agencyId: string; templateId: string },
): Promise<void> {
  const query = buildAssignTemplateUpdate(input);
  await db.prepare(query.sql).bind(...query.bindings).run();
}

function normalizeEmail(value: string): string | null {
  const email = value.trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return null;
  }
  return email;
}
