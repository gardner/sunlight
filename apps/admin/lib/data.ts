import { countOverdueSunlightRequests } from "./sunlight-requests";

export interface SummaryItem {
  label: string;
  value: number;
}

const STATIC_SUMMARY_QUERIES = [
  {
    label: "Authorities",
    sql: "SELECT COUNT(*) AS count FROM sunlight_authorities",
  },
  {
    label: "Verified contacts",
    sql: "SELECT COUNT(*) AS count FROM sunlight_authorities WHERE contact_status = 'verified'",
  },
  {
    label: "Request cycles",
    sql: "SELECT COUNT(*) AS count FROM sunlight_request_cycles",
  },
  {
    label: "Sunlight requests",
    sql: "SELECT COUNT(*) AS count FROM sunlight_requests",
  },
  {
    label: "Responses",
    sql: "SELECT COUNT(*) AS count FROM sunlight_responses",
  },
  {
    label: "Uploads",
    sql: "SELECT COUNT(*) AS count FROM sunlight_uploads",
  },
] as const;

export async function getAdminSummary(db: D1Database): Promise<SummaryItem[]> {
  const items = await Promise.all(
    STATIC_SUMMARY_QUERIES.map(async (query) => {
      const row = await db.prepare(query.sql).first<{ count: number }>();
      return {
        label: query.label,
        value: row?.count ?? 0,
      };
    }),
  );
  const overdue = await countOverdueRequests(db);
  return [...items, { label: "Overdue requests", value: overdue }];
}

async function countOverdueRequests(db: D1Database): Promise<number> {
  const today = new Date().toISOString().slice(0, 10);
  return countOverdueSunlightRequests(db, today);
}
