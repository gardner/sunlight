"use client";

import { useEffect, useRef, useState } from "react";
import type { AgencyFilters } from "../../lib/agencies";

interface AgencyFiltersProps {
  filters: AgencyFilters;
}

export function AgencyFiltersForm({ filters }: AgencyFiltersProps) {
  const [search, setSearch] = useState(filters.search ?? "");
  const [contactStatus, setContactStatus] = useState(filters.contactStatus ?? "");
  const [status, setStatus] = useState(filters.status ?? "");
  const [pageSize, setPageSize] = useState(String(filters.pageSize));
  const didMount = useRef(false);

  useEffect(() => {
    if (!didMount.current) {
      didMount.current = true;
      return;
    }

    const timeout = window.setTimeout(() => {
      applyFilters({ contactStatus, pageSize, search, status });
    }, 300);

    return () => window.clearTimeout(timeout);
  }, [contactStatus, pageSize, search, status]);

  return (
    <form
      className="filters"
      method="get"
      onSubmit={(event) => {
        event.preventDefault();
        applyFilters({ contactStatus, pageSize, search, status });
      }}
    >
      <label>
        Search
        <input
          aria-label="Search agencies"
          name="search"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Type to filter agencies"
          value={search}
        />
      </label>
      <label>
        Contact
        <select
          name="contactStatus"
          onChange={(event) => setContactStatus(event.target.value)}
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
        <select name="status" onChange={(event) => setStatus(event.target.value)} value={status}>
          <option value="">Any</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
      </label>
      <label>
        Rows
        <select
          name="pageSize"
          onChange={(event) => setPageSize(event.target.value)}
          value={pageSize}
        >
          <option value="25">25</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select>
      </label>
      <div className="filterActions">
        <button className="button" type="submit">
          Filter
        </button>
        <button
          className="button secondary"
          onClick={() => {
            window.location.assign("/agencies");
          }}
          type="button"
        >
          Clear
        </button>
      </div>
    </form>
  );
}

function applyFilters(input: {
  contactStatus: string;
  pageSize: string;
  search: string;
  status: string;
}) {
  const params = new URLSearchParams();
  const search = input.search.trim();

  if (search) {
    params.set("search", search);
  }
  if (input.contactStatus) {
    params.set("contactStatus", input.contactStatus);
  }
  if (input.status) {
    params.set("status", input.status);
  }
  if (input.pageSize !== "50") {
    params.set("pageSize", input.pageSize);
  }

  const next = params.toString() ? `/agencies?${params}` : "/agencies";
  if (next !== `${window.location.pathname}${window.location.search}`) {
    window.location.assign(next);
  }
}
