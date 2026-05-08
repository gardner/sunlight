import {
  addWorkingDays,
  buildReplyEmail,
  buildResponseUrl,
  generateCaseToken,
  sha256Hex,
} from "./request-prep";

export interface RequestCycle {
  covered_from: string;
  covered_until: string;
  cycle_month: string;
  id: string;
  status: "draft" | "previewed" | "approved" | "sending" | "sent" | "closed";
}

export type RequestCycleStatus = RequestCycle["status"];

export interface SendableAgency {
  id: string;
  legal_regime: "OIA" | "LGOIMA" | "other";
  name: string;
  template_id: string;
}

export interface SunlightRequestRecord {
  caseTokenHash: string;
  caseTokenHint: string;
  expectedDueAt: string;
  id: string;
  replyEmail: string;
  responseUrl: string;
}

export interface CycleSunlightRequest {
  agency_name: string;
  expected_due_at: string | null;
  id: string;
  last_sent_at: string | null;
  primary_request_email: string | null;
  reply_email: string;
  response_url: string;
  status: string;
}

export type SunlightRequestStatusSummary = Record<string, number> & { total: number };

export function buildCycleRange(cycleMonth: string) {
  if (!/^\d{4}-\d{2}$/.test(cycleMonth)) {
    throw new Error("Cycle month must use YYYY-MM format");
  }

  const [year, month] = cycleMonth.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return {
    coveredFrom: `${cycleMonth}-01`,
    coveredUntil: `${cycleMonth}-${String(lastDay).padStart(2, "0")}`,
  };
}

export function canApproveCycle(status: RequestCycleStatus): boolean {
  return status === "previewed";
}

export function canSendCycle(status: RequestCycleStatus): boolean {
  return status === "approved";
}

export function summarizeSunlightRequestStatuses(
  requests: Array<Pick<CycleSunlightRequest, "status">>,
): SunlightRequestStatusSummary {
  const summary: SunlightRequestStatusSummary = { total: requests.length };
  for (const request of requests) {
    summary[request.status] = (summary[request.status] ?? 0) + 1;
  }
  return summary;
}

export async function buildSunlightRequestRecord(input: {
  agency: SendableAgency;
  cycle: Pick<RequestCycle, "covered_from" | "covered_until" | "cycle_month" | "id">;
  today: string;
  token?: string;
}): Promise<SunlightRequestRecord> {
  const caseToken = input.token ?? generateCaseToken();
  const caseTokenHash = await sha256Hex(caseToken);
  const caseTokenHint = caseToken.slice(0, 6);
  return {
    caseTokenHash,
    caseTokenHint,
    expectedDueAt: addWorkingDays(input.today, 20),
    id: `srq_${crypto.randomUUID().replaceAll("-", "")}`,
    replyEmail: buildReplyEmail(caseToken),
    responseUrl: buildResponseUrl(caseToken),
  };
}

export async function listCycles(db: D1Database): Promise<RequestCycle[]> {
  const result = await db
    .prepare(
      `
        SELECT id, cycle_month, covered_from, covered_until, status
        FROM sunlight_request_cycles
        ORDER BY cycle_month DESC
      `,
    )
    .all<RequestCycle>();

  return result.results;
}

export async function createCycle(db: D1Database, cycleMonth: string): Promise<string> {
  const range = buildCycleRange(cycleMonth);
  const id = `cyc_${cycleMonth.replace("-", "_")}`;
  await db
    .prepare(
      `
        INSERT INTO sunlight_request_cycles (
          id,
          cycle_month,
          covered_from,
          covered_until,
          status
        ) VALUES (?, ?, ?, ?, 'draft')
        ON CONFLICT(cycle_month) DO NOTHING
      `,
    )
    .bind(id, cycleMonth, range.coveredFrom, range.coveredUntil)
    .run();
  return id;
}

export async function getCycle(db: D1Database, cycleId: string): Promise<RequestCycle | null> {
  return db
    .prepare(
      `
        SELECT id, cycle_month, covered_from, covered_until, status
        FROM sunlight_request_cycles
        WHERE id = ?
        LIMIT 1
      `,
    )
    .bind(cycleId)
    .first<RequestCycle>();
}

export async function listSendableAgencies(db: D1Database): Promise<SendableAgency[]> {
  const result = await db
    .prepare(
      `
        SELECT
          id,
          name,
          legal_regime,
          default_template_id AS template_id
        FROM sunlight_agencies
        WHERE status = 'active'
          AND contact_status = 'verified'
          AND primary_request_email IS NOT NULL
          AND default_template_id IS NOT NULL
        ORDER BY name
      `,
    )
    .all<SendableAgency>();

  return result.results;
}

export async function listCycleSunlightRequests(
  db: D1Database,
  cycleId: string,
): Promise<CycleSunlightRequest[]> {
  const result = await db
    .prepare(
      `
        SELECT
          sunlight_requests.id,
          sunlight_requests.reply_email,
          sunlight_requests.response_url,
          sunlight_requests.status,
          sunlight_requests.expected_due_at,
          sunlight_requests.last_sent_at,
          sunlight_agencies.name AS agency_name,
          sunlight_agencies.primary_request_email
        FROM sunlight_requests
        JOIN sunlight_agencies ON sunlight_agencies.id = sunlight_requests.agency_id
        WHERE sunlight_requests.cycle_id = ?
        ORDER BY sunlight_agencies.name
      `,
    )
    .bind(cycleId)
    .all<CycleSunlightRequest>();

  return result.results;
}

export async function prepareCycleRequests(db: D1Database, cycleId: string): Promise<number> {
  const cycle = await getCycle(db, cycleId);
  if (!cycle) {
    throw new Error("Unknown request cycle");
  }

  const agencies = await listSendableAgencies(db);
  const today = new Date().toISOString().slice(0, 10);
  let created = 0;

  for (const agency of agencies) {
    const record = await buildSunlightRequestRecord({ agency, cycle, today });
    const result = await db
      .prepare(
        `
          INSERT OR IGNORE INTO sunlight_requests (
            id,
            agency_id,
            cycle_id,
            template_id,
            case_token_hash,
            case_token_hint,
            reply_email,
            response_url,
            status,
            expected_due_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)
        `,
      )
      .bind(
        record.id,
        agency.id,
        cycle.id,
        agency.template_id,
        record.caseTokenHash,
        record.caseTokenHint,
        record.replyEmail,
        record.responseUrl,
        record.expectedDueAt,
      )
      .run();

    created += result.meta.changes ?? 0;
  }

  await db
    .prepare(
      `
        UPDATE sunlight_request_cycles
        SET status = 'previewed',
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(cycle.id)
    .run();

  return created;
}

export async function approveCycle(db: D1Database, cycleId: string): Promise<void> {
  const cycle = await getCycle(db, cycleId);
  if (!cycle) {
    throw new Error("Unknown request cycle");
  }
  if (!canApproveCycle(cycle.status)) {
    throw new Error("Only previewed request cycles can be approved");
  }

  await db
    .prepare(
      `
        UPDATE sunlight_request_cycles
        SET status = 'approved',
            approved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(cycle.id)
    .run();
}
