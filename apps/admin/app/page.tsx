import { env } from "cloudflare:workers";
import { getAdminSummary } from "../lib/data";

export default async function AdminDashboard() {
  const summary = await getAdminSummary((env as unknown as CloudflareEnv).DB);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Sunlight Requests</p>
          <h1>Admin</h1>
        </div>
        <nav className="actions">
          <a className="button" href="/agencies">
            Agencies
          </a>
          <a className="button" href="/templates">
            Templates
          </a>
          <a className="button" href="/cycles">
            Cycles
          </a>
          <a className="button" href="/requests">
            Requests
          </a>
        </nav>
      </header>

      <section className="grid" aria-label="Operational summary">
        {summary.map((item) => (
          <article className="metric" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>
    </main>
  );
}
