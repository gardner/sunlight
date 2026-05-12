"use client";

import { useMemo, useState } from "react";
import type { AuthorityListItem, AuthorityStatus, ContactStatus } from "../../lib/authorities";
import { Input } from "@admin/components/ui/input";
import { Label } from "@admin/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@admin/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@admin/components/ui/table";
import { Button } from "@admin/components/ui/button";
import { Badge } from "@admin/components/ui/badge";

interface AuthorityBrowserProps {
  authorities: AuthorityListItem[];
}

const PAGE_SIZES = ["25", "50", "100"];

export function AuthorityBrowser({ authorities }: AuthorityBrowserProps) {
  const [search, setSearch] = useState("");
  const [contactStatus, setContactStatus] = useState<string>("any");
  const [status, setStatus] = useState<string>("any");
  const [pageSize, setPageSize] = useState("50");
  const [page, setPage] = useState(1);

  const filtered = useMemo(
    () =>
      authorities.filter((authority) => {
        if (contactStatus !== "any" && authority.contact_status !== contactStatus) {
          return false;
        }
        if (status !== "any" && authority.status !== status) {
          return false;
        }
        if (!search.trim()) {
          return true;
        }

        const term = search.trim().toLowerCase();
        return [
          authority.name,
          authority.slug,
          authority.legal_regime,
          authority.primary_request_email ?? "",
          authority.contact_status,
          authority.status,
        ].some((value) => value.toLowerCase().includes(term));
      }),
    [authorities, contactStatus, search, status],
  );

  const pageSizeNum = Number(pageSize);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSizeNum));
  const currentPage = Math.min(page, pageCount);
  const firstIndex = (currentPage - 1) * pageSizeNum;
  const visibleAuthorities = filtered.slice(firstIndex, firstIndex + pageSizeNum);
  const firstVisible = filtered.length === 0 ? 0 : firstIndex + 1;
  const lastVisible = Math.min(filtered.length, firstIndex + visibleAuthorities.length);

  function resetToFirstPage() {
    setPage(1);
  }

  return (
    <>
      <form
        className="mb-8 grid gap-4 md:grid-cols-5 items-end"
        onSubmit={(event) => {
          event.preventDefault();
          resetToFirstPage();
        }}
      >
        <div className="md:col-span-2">
          <Label htmlFor="search">Search</Label>
          <Input
            id="search"
            aria-label="Search authorities"
            name="search"
            onChange={(event) => {
              setSearch(event.currentTarget.value);
              resetToFirstPage();
            }}
            placeholder="Type to filter authorities..."
            value={search}
          />
        </div>
        <div>
          <Label>Contact</Label>
          <Select
            name="contactStatus"
            onValueChange={(val) => {
              setContactStatus(val);
              resetToFirstPage();
            }}
            value={contactStatus}
          >
            <SelectTrigger>
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              <SelectItem value="missing">Missing</SelectItem>
              <SelectItem value="needs_review">Needs review</SelectItem>
              <SelectItem value="verified">Verified</SelectItem>
              <SelectItem value="invalid">Invalid</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Status</Label>
          <Select
            name="status"
            onValueChange={(val) => {
              setStatus(val);
              resetToFirstPage();
            }}
            value={status}
          >
            <SelectTrigger>
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setSearch("");
              setContactStatus("any");
              setStatus("any");
              setPageSize("50");
              setPage(1);
            }}
            type="button"
            className="w-full"
          >
            Clear
          </Button>
        </div>
      </form>

      <div className="mb-4 flex items-center justify-between text-sm text-muted-foreground">
        <p>
          Showing <span className="font-medium text-foreground">{firstVisible.toLocaleString()}-{lastVisible.toLocaleString()}</span> of{" "}
          <span className="font-medium text-foreground">{filtered.length.toLocaleString()}</span> authorities
        </p>
        <div className="flex items-center gap-2">
           <span>Rows per page</span>
           <Select
            name="pageSize"
            onValueChange={(val) => {
              setPageSize(val);
              resetToFirstPage();
            }}
            value={pageSize}
          >
            <SelectTrigger className="w-20 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZES.map((size) => (
                <SelectItem key={size} value={size}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Regime</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Email</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleAuthorities.map((authority) => (
              <TableRow key={authority.id}>
                <TableCell className="font-medium">
                  <a href={`/authorities/${authority.id}`} className="hover:underline hover:text-primary">{authority.name}</a>
                </TableCell>
                <TableCell>{authority.legal_regime}</TableCell>
                <TableCell>
                  <Badge variant={authority.contact_status === "verified" ? "default" : "secondary"}>
                    {authority.contact_status}
                  </Badge>
                </TableCell>
                <TableCell>{authority.status}</TableCell>
                <TableCell className="text-muted-foreground">{authority.primary_request_email ?? ""}</TableCell>
              </TableRow>
            ))}
            {visibleAuthorities.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center">No authorities match the current filters.</TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
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
    <nav className="flex items-center justify-center gap-1 mt-6" aria-label="Authority pagination">
      <Button
        variant="outline"
        size="sm"
        disabled={page <= 1}
        onClick={() => setPage(Math.max(1, page - 1))}
        type="button"
      >
        Previous
      </Button>
      <div className="flex gap-1 mx-2">
        {pages.map((item, index) =>
          item === "gap" ? (
            <span aria-hidden="true" key={`${item}-${index}`} className="px-2 py-1">
              ...
            </span>
          ) : (
            <Button
              variant={item === page ? "default" : "ghost"}
              size="sm"
              className={item === page ? "" : "text-muted-foreground"}
              key={item}
              onClick={() => setPage(item)}
              type="button"
            >
              {item}
            </Button>
          ),
        )}
      </div>
      <Button
        variant="outline"
        size="sm"
        disabled={page >= pageCount}
        onClick={() => setPage(Math.min(pageCount, page + 1))}
        type="button"
      >
        Next
      </Button>
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
