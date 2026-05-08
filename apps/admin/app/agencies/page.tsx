import { env } from "cloudflare:workers";
import { listAgencies, normalizeAgencyFilters } from "../../lib/agencies";

interface AgenciesPageProps {
  searchParams?: Promise<Record<string, string | undefined>>;
}

export default async function AgenciesPage({ searchParams }: AgenciesPageProps) {
  const params = (await searchParams) ?? {};
  const filters = normalizeAgencyFilters(params);
  const agencies = await listAgencies((env as unknown as CloudflareEnv).DB, filters);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Agencies</h1>
        </div>
        <a className="button" href="/">
          Dashboard
        </a>
      </header>

      <form className="filters">
        <label>
          Search
          <input name="search" defaultValue={filters.search ?? ""} />
        </label>
        <label>
          Contact
          <select name="contactStatus" defaultValue={filters.contactStatus ?? ""}>
            <option value="">Any</option>
            <option value="missing">Missing</option>
            <option value="needs_review">Needs review</option>
            <option value="verified">Verified</option>
            <option value="invalid">Invalid</option>
          </select>
        </label>
        <label>
          Status
          <select name="status" defaultValue={filters.status ?? ""}>
            <option value="">Any</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
        <button className="button" type="submit">
          Filter
        </button>
      </form>

      <div className="table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Regime</th>
              <th>Contact</th>
              <th>Status</th>
              <th>Email</th>
            </tr>
          </thead>
          <tbody>
            {agencies.map((agency) => (
              <tr key={agency.id}>
                <td>
                  <a href={`/agencies/${agency.id}`}>{agency.name}</a>
                </td>
                <td>{agency.legal_regime}</td>
                <td>
                  <span className="pill">{agency.contact_status}</span>
                </td>
                <td>{agency.status}</td>
                <td>{agency.primary_request_email ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
