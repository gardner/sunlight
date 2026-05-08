"use client";

import { useMemo, useState } from "react";
import type { AgencyListItem, AgencyStatus, ContactStatus } from "../../lib/agencies";

interface AgencyBrowserProps {
  agencies: AgencyListItem[];
}

const PAGE_SIZES = [25, 50, 100] as const;

export function AgencyBrowser({ agencies }: AgencyBrowserProps) {
  const [search, setSearch] = useState("");
  const [contactStatus, setContactStatus] = useState<ContactStatus | "">("");
  const [status, setStatus] = useState<AgencyStatus | "">("");
  const [pageSize, setPageSize] = useState(50);
  const [page, setPage] = useState(1);

  const filtered = useMemo(
    () =>
      agencies.filter((agency) => {
        if (contactStatus && agency.contact_status !== contactStatus) {
          return false;
        }
        if (status && agency.status !== status) {
          return false;
        }
        if (!search.trim()) {
          return true;
        }

        const term = search.trim().toLowerCase();
        return [
          agency.name,
          agency.slug,
          agency.legal_regime,
          agency.primary_request_email ?? "",
          agency.contact_status,
          agency.status,
        ].some((value) => value.toLowerCase().includes(term));
      }),
    [agencies, contactStatus, search, status],
  );

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const firstIndex = (currentPage - 1) * pageSize;
  const visibleAgencies = filtered.slice(firstIndex, firstIndex + pageSize);
  const firstVisible = filtered.length === 0 ? 0 : firstIndex + 1;
  const lastVisible = Math.min(filtered.length, firstIndex + visibleAgencies.length);

  function resetToFirstPage() {
    setPage(1);
  }

  return (
    <>
      <form
        className="filters"
        onSubmit={(event) => {
          event.preventDefault();
          resetToFirstPage();
        }}
      >
        <label>
          Search
          <input
            aria-label="Search agencies"
            name="search"
            onChange={(event) => {
              setSearch(event.currentTarget.value);
              resetToFirstPage();
            }}
            onKeyUp={(event) => {
              setSearch(event.currentTarget.value);
              resetToFirstPage();
            }}
            placeholder="Type to filter agencies"
            value={search}
          />
        </label>
        <label>
          Contact
          <select
            name="contactStatus"
            onChange={(event) => {
              setContactStatus(event.currentTarget.value as ContactStatus | "");
              resetToFirstPage();
            }}
            value={contactStatus}
          >
            <option value="">Any</option>
            <option value="missing">Missing</option>
            <option value="needs_review">Needs review</option>
            <option value="verified">Verified</option>
            <option value="invalid">Invalid</option>
          </select>
        </label>
        <label>
          Status
          <select
            name="status"
            onChange={(event) => {
              setStatus(event.currentTarget.value as AgencyStatus | "");
              resetToFirstPage();
            }}
            value={status}
          >
            <option value="">Any</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
        <label>
          Rows
          <select
            name="pageSize"
            onChange={(event) => {
              setPageSize(Number(event.currentTarget.value));
              resetToFirstPage();
            }}
            value={pageSize}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <div className="filterActions">
          <button className="button" type="submit">
            Filter
          </button>
          <button
            className="button secondary"
            onClick={() => {
              setSearch("");
              setContactStatus("");
              setStatus("");
              setPageSize(50);
              setPage(1);
            }}
            type="button"
          >
            Clear
          </button>
        </div>
      </form>

      <div className="tableMeta">
        <p>
          Showing {firstVisible.toLocaleString()}-{lastVisible.toLocaleString()} of{" "}
          {filtered.length.toLocaleString()} agencies
        </p>
        <p>
          Page {currentPage.toLocaleString()} of {pageCount.toLocaleString()}
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
            {visibleAgencies.map((agency) => (
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
            {visibleAgencies.length === 0 ? (
              <tr>
                <td colSpan={5}>No agencies match the current filters.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <Pagination page={currentPage} pageCount={pageCount} setPage={setPage} />
    </>
  );
}

function Pagination({
  page,
  pageCount,
  setPage,
}: {
  page: number;
  pageCount: number;
  setPage: (page: number) => void;
}) {
  const pages = buildPaginationPages(page, pageCount);

  return (
    <nav className="pagination" aria-label="Agency pagination">
      <button
        className="button secondary"
        disabled={page <= 1}
        onClick={() => setPage(Math.max(1, page - 1))}
        type="button"
      >
        Previous
      </button>
      <div className="pageNumbers">
        {pages.map((item, index) =>
          item === "gap" ? (
            <span aria-hidden="true" key={`${item}-${index}`}>
              ...
            </span>
          ) : (
            <button
              aria-current={item === page ? "page" : undefined}
              className={item === page ? "currentPage" : ""}
              key={item}
              onClick={() => setPage(item)}
              type="button"
            >
              {item}
            </button>
          ),
        )}
      </div>
      <button
        className="button secondary"
        disabled={page >= pageCount}
        onClick={() => setPage(Math.min(pageCount, page + 1))}
        type="button"
      >
        Next
      </button>
    </nav>
  );
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
