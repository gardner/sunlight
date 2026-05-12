export type ContactStatus = "missing" | "needs_review" | "verified" | "invalid";
export type AuthorityStatus = "active" | "inactive";

export interface AuthorityFilters {
  contactStatus?: ContactStatus;
  page: number;
  pageSize: number;
  search?: string;
  status?: AuthorityStatus;
}

export interface AuthorityListPage {
  items: AuthorityListItem[];
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
}

export interface AuthorityListItem {
  contact_status: ContactStatus;
  id: string;
  legal_regime: "OIA" | "LGOIMA" | "other";
  name: string;
  primary_request_email: string | null;
  slug: string;
  status: AuthorityStatus;
}

export interface AuthorityDetail extends AuthorityListItem {
  default_cadence: string;
  default_template_id: string | null;
  notes: string | null;
  proactive_release_url: string | null;
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

const AUTHORITY_STATUSES = new Set<AuthorityStatus>(["active", "inactive"]);
const DEFAULT_PAGE_SIZE = 50;
const PAGE_SIZES = new Set([25, 50, 100]);

export function normalizeAuthorityFilters(input: Record<string, string | undefined>): AuthorityFilters {
  const filters: AuthorityFilters = {
    page: normalizePositiveInteger(input.page, 1),
    pageSize: normalizePageSize(input.pageSize),
  };
  const contactStatus = input.contactStatus;
  const status = input.status;
  const search = input.search?.trim();

  if (contactStatus && CONTACT_STATUSES.has(contactStatus as ContactStatus)) {
    filters.contactStatus = contactStatus as ContactStatus;
  }
  if (status && AUTHORITY_STATUSES.has(status as AuthorityStatus)) {
    filters.status = status as AuthorityStatus;
  }
  if (search) {
    filters.search = search;
  }

  return filters;
}

export function buildAuthorityWhereClause(filters: Partial<AuthorityFilters> = {}) {
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

  return {
    bindings,
    sql: where.length ? `WHERE ${where.join(" AND ")}` : "",
  };
}

export function buildAuthorityCountQuery(filters: Partial<AuthorityFilters> = {}) {
  const where = buildAuthorityWhereClause(filters);
  return {
    bindings: where.bindings,
    sql: `
      SELECT COUNT(*) AS total
      FROM sunlight_authorities
      ${where.sql}
    `,
  };
}

export function buildAuthorityListQuery(filters: Partial<AuthorityFilters> = {}) {
  const where = buildAuthorityWhereClause(filters);
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? DEFAULT_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  const sql = `
    SELECT
      id,
      name,
      slug,
      legal_regime,
      primary_request_email,
      contact_status,
      status
    FROM sunlight_authorities
    ${where.sql}
    ORDER BY
      CASE contact_status
        WHEN 'verified' THEN 0
        WHEN 'needs_review' THEN 1
        WHEN 'missing' THEN 2
        ELSE 3
      END,
      name
    LIMIT ? OFFSET ?
  `;

  return { bindings: [...where.bindings, pageSize, offset], sql };
}

export function buildAllAuthoritiesQuery() {
  return {
    bindings: [],
    sql: `
      SELECT
        id,
        name,
        slug,
        legal_regime,
        primary_request_email,
        contact_status,
        status
      FROM sunlight_authorities
      ORDER BY
        CASE contact_status
          WHEN 'verified' THEN 0
          WHEN 'needs_review' THEN 1
          WHEN 'missing' THEN 2
          ELSE 3
        END,
        name
    `,
  };
}

export async function listAuthorities(
  db: D1Database,
  filters: AuthorityFilters,
): Promise<AuthorityListItem[]> {
  const query = buildAuthorityListQuery(filters);
  const result = await db.prepare(query.sql).bind(...query.bindings).all<AuthorityListItem>();
  return result.results;
}

export async function listAllAuthorities(db: D1Database): Promise<AuthorityListItem[]> {
  const query = buildAllAuthoritiesQuery();
  const result = await db.prepare(query.sql).bind(...query.bindings).all<AuthorityListItem>();
  return result.results;
}

export async function listAuthorityPage(
  db: D1Database,
  filters: AuthorityFilters,
): Promise<AuthorityListPage> {
  const countQuery = buildAuthorityCountQuery(filters);
  const count = await db
    .prepare(countQuery.sql)
    .bind(...countQuery.bindings)
    .first<{ total: number }>();
  const total = count?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / filters.pageSize));
  const page = Math.min(filters.page, pageCount);
  const items = await listAuthorities(db, { ...filters, page });

  return {
    items,
    page,
    pageCount,
    pageSize: filters.pageSize,
    total,
  };
}

export async function getAuthority(db: D1Database, authorityId: string): Promise<AuthorityDetail | null> {
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
          proactive_release_url,
          notes
        FROM sunlight_authorities
        WHERE id = ?
        LIMIT 1
      `,
    )
    .bind(authorityId)
    .first<AuthorityDetail>();
}

export function buildVerifyContactUpdate(input: { authorityId: string; email: string }) {
  const email = normalizeEmail(input.email);
  if (!email) {
    throw new Error("Contact verification requires a valid email address");
  }

  return {
    bindings: [email, input.authorityId],
    sql: `
      UPDATE sunlight_authorities
      SET primary_request_email = ?,
          contact_status = 'verified',
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
    `,
  };
}

export async function verifyAuthorityContact(
  db: D1Database,
  input: { authorityId: string; email: string },
): Promise<void> {
  const query = buildVerifyContactUpdate(input);
  await db.prepare(query.sql).bind(...query.bindings).run();
}

export function buildAssignTemplateUpdate(input: { authorityId: string; templateId: string }) {
  if (!input.authorityId || !input.templateId) {
    throw new Error("Authority and template are required");
  }

  return {
    bindings: [input.templateId, input.authorityId],
    sql: `
      UPDATE sunlight_authorities
      SET default_template_id = ?,
          updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
    `,
  };
}

export async function assignAuthorityTemplate(
  db: D1Database,
  input: { authorityId: string; templateId: string },
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

function normalizePageSize(value: string | undefined): number {
  const pageSize = normalizePositiveInteger(value, DEFAULT_PAGE_SIZE);
  return PAGE_SIZES.has(pageSize) ? pageSize : DEFAULT_PAGE_SIZE;
}

function normalizePositiveInteger(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export interface UpdateAuthorityInput {
  name: string;
  slug: string;
  legal_regime: "OIA" | "LGOIMA" | "other";
  status: AuthorityStatus;
  default_cadence: string;
  proactive_release_url: string | null;
  notes: string | null;
}

export function buildUpdateAuthorityInput(input: Record<string, string>): UpdateAuthorityInput {
  const name = input.name?.trim();
  const slug = input.slug?.trim();
  const legal_regime = input.legal_regime as "OIA" | "LGOIMA" | "other";
  const status = input.status as AuthorityStatus;
  const default_cadence = input.default_cadence?.trim();
  const proactive_release_url = input.proactive_release_url?.trim() || null;
  const notes = input.notes?.trim() || null;

  if (!name || !slug || !legal_regime || !status || !default_cadence) {
    throw new Error("Missing required authority fields");
  }

  return {
    name,
    slug,
    legal_regime,
    status,
    default_cadence,
    proactive_release_url,
    notes,
  };
}

export async function updateAuthority(
  db: D1Database,
  id: string,
  input: UpdateAuthorityInput,
): Promise<void> {
  await db
    .prepare(
      `
        UPDATE sunlight_authorities
        SET name = ?,
            slug = ?,
            legal_regime = ?,
            status = ?,
            default_cadence = ?,
            proactive_release_url = ?,
            notes = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(
      input.name,
      input.slug,
      input.legal_regime,
      input.status,
      input.default_cadence,
      input.proactive_release_url,
      input.notes,
      id,
    )
    .run();
}
