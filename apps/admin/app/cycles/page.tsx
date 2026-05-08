import { env } from "cloudflare:workers";
import { listCycles } from "../../lib/cycles";

export default async function CyclesPage() {
  const cycles = await listCycles((env as unknown as CloudflareEnv).DB);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Request cycles</h1>
        </div>
        <a className="button" href="/cycles/new">
          New cycle
        </a>
      </header>

      <div className="table">
        <table>
          <thead>
            <tr>
              <th>Month</th>
              <th>Status</th>
              <th>Covered from</th>
              <th>Covered until</th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((cycle) => (
              <tr key={cycle.id}>
                <td>
                  <a href={`/cycles/${cycle.id}`}>{cycle.cycle_month}</a>
                </td>
                <td>{cycle.status}</td>
                <td>{cycle.covered_from}</td>
                <td>{cycle.covered_until}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
