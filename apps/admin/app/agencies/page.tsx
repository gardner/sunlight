import { env } from "cloudflare:workers";
import { Button } from "@admin/components/ui/button";
import { listAgencyPage, normalizeAgencyFilters, type AgencyFilters } from "../../lib/agencies";
import { AgencyFiltersForm } from "./AgencyFilters";

interface AgenciesPageProps {
  searchParams?: Promise<Record<string, string | undefined>>;
}

export default async function AgenciesPage({ searchParams }: AgenciesPageProps) {
  const params = (await searchParams) ?? {};
  const filters = normalizeAgencyFilters(params);
  const agencyPage = await listAgencyPage((env as unknown as CloudflareEnv).DB, filters);
  const firstVisible = agencyPage.total === 0 ? 0 : (agencyPage.page - 1) * agencyPage.pageSize + 1;
  const lastVisible = Math.min(agencyPage.total, firstVisible + agencyPage.items.length - 1);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Agencies</h1>
        </div>
        <Button asChild>
          <a href="/">Dashboard</a>
        </Button>
      </header>

      <AgencyFiltersForm filters={filters} />

      <div className="tableMeta">
        <p>
          Showing {firstVisible.toLocaleString()}-{lastVisible.toLocaleString()} of{" "}
          {agencyPage.total.toLocaleString()} agencies
        </p>
        <p>
          Page {agencyPage.page.toLocaleString()} of {agencyPage.pageCount.toLocaleString()}
        </p>
      </div>

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
            {agencyPage.items.map((agency) => (
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
            {agencyPage.items.length === 0 ? (
              <tr>
                <td colSpan={5}>No agencies match the current filters.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Pagination filters={filters} page={agencyPage.page} pageCount={agencyPage.pageCount} />
    </main>
  );
}

function Pagination({
  filters,
  page,
  pageCount,
}: {
  filters: AgencyFilters;
  page: number;
  pageCount: number;
}) {
  const pages = buildPaginationPages(page, pageCount);

  return (
    <nav className="pagination" aria-label="Agency pagination">
      <Button asChild disabled={page <= 1} variant="outline">
        <a aria-disabled={page <= 1} href={buildAgencyPageHref(filters, page - 1)}>
          Previous
        </a>
      </Button>
      <div className="pageNumbers">
        {pages.map((item, index) =>
          item === "gap" ? (
            <span aria-hidden="true" key={`${item}-${index}`}>
              ...
            </span>
          ) : (
            <a
              aria-current={item === page ? "page" : undefined}
              className={item === page ? "currentPage" : ""}
              href={buildAgencyPageHref(filters, item)}
              key={item}
            >
              {item}
            </a>
          ),
        )}
      </div>
      <Button asChild disabled={page >= pageCount} variant="outline">
        <a aria-disabled={page >= pageCount} href={buildAgencyPageHref(filters, page + 1)}>
          Next
        </a>
      </Button>
    </nav>
  );
}

function buildAgencyPageHref(filters: AgencyFilters, page: number): string {
  const params = new URLSearchParams();
  const boundedPage = Math.max(1, page);

  if (filters.search) {
    params.set("search", filters.search);
  }
  if (filters.contactStatus) {
    params.set("contactStatus", filters.contactStatus);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.pageSize !== 50) {
    params.set("pageSize", String(filters.pageSize));
  }
  if (boundedPage > 1) {
    params.set("page", String(boundedPage));
  }

  return params.toString() ? `/agencies?${params}` : "/agencies";
}

function buildPaginationPages(page: number, pageCount: number): Array<number | "gap"> {
  const pages = new Set([1, page - 1, page, page + 1, pageCount]);
  const sorted = [...pages].filter((item) => item >= 1 && item <= pageCount).sort((a, b) => a - b);
  const output: Array<number | "gap"> = [];

  for (const item of sorted) {
    const previous = output[output.length - 1];
    if (typeof previous === "number" && item - previous > 1) {
      output.push("gap");
    }
    output.push(item);
  }

  return output;
}
