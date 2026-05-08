import { env } from "cloudflare:workers";
import {
  isOverdueSunlightRequest,
  listSunlightRequests,
  summarizeRequestTimeliness,
} from "../../lib/sunlight-requests";

interface RequestsPageProps {
  searchParams?: Promise<{ status?: string }>;
}

export default async function RequestsPage({ searchParams }: RequestsPageProps) {
  const status = (await searchParams)?.status || undefined;
  const today = new Date().toISOString().slice(0, 10);
  const requests = await listSunlightRequests((env as unknown as CloudflareEnv).DB, {
    status,
  });
  const summary = summarizeRequestTimeliness(requests, today);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>SunlightRequests</h1>
        </div>
        <a className="button" href="/">
          Dashboard
        </a>
      </header>

      <section className="grid">
        <article className="metric">
          <span>Total</span>
          <strong>{summary.total}</strong>
        </article>
        <article className="metric">
          <span>Open</span>
          <strong>{summary.open}</strong>
        </article>
        <article className="metric">
          <span>Overdue</span>
          <strong>{summary.overdue}</strong>
        </article>
      </section>

      <form className="filters">
        <label>
          Status
          <select defaultValue={status ?? ""} name="status">
            <option value="">All</option>
            <option value="scheduled">Scheduled</option>
            <option value="awaiting_response">Awaiting response</option>
            <option value="partially_received">Partially received</option>
            <option value="response_received">Response received</option>
            <option value="failed">Failed</option>
            <option value="closed">Closed</option>
          </select>
        </label>
        <button className="button" type="submit">
          Filter
        </button>
      </form>

      <section className="table">
        <table>
          <thead>
            <tr>
              <th>Authority</th>
              <th>Cycle</th>
              <th>Status</th>
              <th>Due</th>
              <th>Last response</th>
              <th>Reply email</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((request) => (
              <tr
                className={isOverdueSunlightRequest(request, today) ? "dangerRow" : undefined}
                key={request.id}
              >
                <td>{request.authority_name}</td>
                <td>{request.cycle_month}</td>
                <td>
                  <span className="pill">{request.status}</span>
                </td>
                <td>{request.expected_due_at}</td>
                <td>{request.last_response_at}</td>
                <td>{request.reply_email}</td>
              </tr>
            ))}
            {requests.length === 0 ? (
              <tr>
                <td colSpan={6}>No SunlightRequests match this filter.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </main>
  );
}
