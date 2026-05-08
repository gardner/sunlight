import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import {
  canApproveCycle,
  canSendCycle,
  getCycle,
  listCycleSunlightRequests,
  summarizeSunlightRequestStatuses,
} from "../../../lib/cycles";
import { approveCycleAction, prepareCycleAction, sendCycleAction } from "./actions";

interface CycleDetailPageProps {
  params: Promise<{ cycleId: string }>;
}

export default async function CycleDetailPage({ params }: CycleDetailPageProps) {
  const { cycleId } = await params;
  const db = (env as unknown as CloudflareEnv).DB;
  const cycle = await getCycle(db, cycleId);

  if (!cycle) {
    notFound();
  }

  const requests = await listCycleSunlightRequests(db, cycle.id);
  const statusSummary = summarizeSunlightRequestStatuses(requests);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Request cycle</p>
          <h1>{cycle.cycle_month}</h1>
        </div>
        <a className="button" href="/cycles">
          Cycles
        </a>
      </header>

      <section className="panel">
        <dl className="facts">
          <div>
            <dt>Status</dt>
            <dd>{cycle.status}</dd>
          </div>
          <div>
            <dt>Covered period</dt>
            <dd>
              {cycle.covered_from} to {cycle.covered_until}
            </dd>
          </div>
        </dl>
        <div className="actions">
          <form action={prepareCycleAction}>
            <input type="hidden" name="cycleId" value={cycle.id} />
            <button className="button" type="submit">
              Prepare SunlightRequests
            </button>
          </form>
          <form action={approveCycleAction}>
            <input type="hidden" name="cycleId" value={cycle.id} />
            <button className="button" disabled={!canApproveCycle(cycle.status)} type="submit">
              Approve cycle
            </button>
          </form>
          <form action={sendCycleAction}>
            <input type="hidden" name="cycleId" value={cycle.id} />
            <button className="button primary" disabled={!canSendCycle(cycle.status)} type="submit">
              Send requests
            </button>
          </form>
        </div>
      </section>

      <section className="panel stack">
        <div>
          <p className="eyebrow">Send preview</p>
          <h2>SunlightRequests</h2>
        </div>
        <div className="grid">
          <div className="metric">
            <span>Total</span>
            <strong>{statusSummary.total}</strong>
          </div>
          {Object.entries(statusSummary)
            .filter(([status]) => status !== "total")
            .map(([status, count]) => (
              <div className="metric" key={status}>
                <span>{status}</span>
                <strong>{count}</strong>
              </div>
            ))}
        </div>
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Agency</th>
                <th>Email</th>
                <th>Status</th>
                <th>Due</th>
                <th>Response URL</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((request) => (
                <tr key={request.id}>
                  <td>{request.agency_name}</td>
                  <td>{request.primary_request_email}</td>
                  <td>
                    <span className="pill">{request.status}</span>
                  </td>
                  <td>{request.expected_due_at}</td>
                  <td>
                    <a href={request.response_url}>{request.response_url}</a>
                  </td>
                </tr>
              ))}
              {requests.length === 0 ? (
                <tr>
                  <td colSpan={5}>No SunlightRequests have been prepared for this cycle.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
