export interface SummaryItem {
  label: string;
  value: number;
}

const SUMMARY_QUERIES = [
  {
    label: "Agencies",
    sql: "SELECT COUNT(*) AS count FROM sunlight_agencies",
  },
  {
    label: "Verified contacts",
    sql: "SELECT COUNT(*) AS count FROM sunlight_agencies WHERE contact_status = 'verified'",
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
  return Promise.all(
    SUMMARY_QUERIES.map(async (query) => {
      const row = await db.prepare(query.sql).first<{ count: number }>();
      return {
        label: query.label,
        value: row?.count ?? 0,
      };
    }),
  );
}
