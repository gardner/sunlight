const OPEN_REQUEST_STATUSES = new Set([
  "sent",
  "delivered",
  "awaiting_response",
  "partially_received",
]);

export interface SunlightRequestListItem {
  authority_name: string;
  cycle_month: string;
  expected_due_at: string | null;
  id: string;
  last_response_at: string | null;
  last_sent_at: string | null;
  legal_regime: string;
  reply_email: string;
  response_url: string;
  status: string;
}

export interface RequestTimelinessSummary {
  open: number;
  overdue: number;
  total: number;
}

export function isOverdueSunlightRequest(
  request: Pick<SunlightRequestListItem, "expected_due_at" | "status">,
  today: string,
): boolean {
  return (
    request.expected_due_at !== null &&
    request.expected_due_at < today &&
    OPEN_REQUEST_STATUSES.has(request.status)
  );
}

export function summarizeRequestTimeliness(
  requests: Array<Pick<SunlightRequestListItem, "expected_due_at" | "status">>,
  today: string,
): RequestTimelinessSummary {
  return {
    open: requests.filter((request) => OPEN_REQUEST_STATUSES.has(request.status)).length,
    overdue: requests.filter((request) => isOverdueSunlightRequest(request, today)).length,
    total: requests.length,
  };
}

export async function listSunlightRequests(
  db: D1Database,
  filters: { status?: string } = {},
): Promise<SunlightRequestListItem[]> {
  const statusClause = filters.status ? "WHERE sunlight_requests.status = ?" : "";
  const statement = db.prepare(
    `
      SELECT
        sunlight_requests.id,
        sunlight_requests.reply_email,
        sunlight_requests.response_url,
        sunlight_requests.status,
        sunlight_requests.expected_due_at,
        sunlight_requests.last_sent_at,
        sunlight_requests.last_response_at,
        sunlight_authorities.name AS authority_name,
        sunlight_authorities.legal_regime,
        sunlight_request_cycles.cycle_month
      FROM sunlight_requests
      JOIN sunlight_authorities ON sunlight_authorities.id = sunlight_requests.authority_id
      JOIN sunlight_request_cycles ON sunlight_request_cycles.id = sunlight_requests.cycle_id
      ${statusClause}
      ORDER BY sunlight_requests.expected_due_at ASC, sunlight_authorities.name
      LIMIT 250
    `,
  );

  const result = filters.status
    ? await statement.bind(filters.status).all<SunlightRequestListItem>()
    : await statement.all<SunlightRequestListItem>();

  return result.results;
}

export async function countOverdueSunlightRequests(
  db: D1Database,
  today: string,
): Promise<number> {
  const result = await db
    .prepare(
      `
        SELECT COUNT(*) AS count
        FROM sunlight_requests
        WHERE expected_due_at < ?
          AND status IN ('sent', 'delivered', 'awaiting_response', 'partially_received')
      `,
    )
    .bind(today)
    .first<{ count: number }>();

  return result?.count ?? 0;
}
