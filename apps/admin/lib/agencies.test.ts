import { describe, expect, it } from "vitest";
import {
  buildAllAgenciesQuery,
  buildAgencyListQuery,
  buildAgencyWhereClause,
  buildAssignTemplateUpdate,
  buildVerifyContactUpdate,
  normalizeAgencyFilters,
} from "./agencies";

describe("normalizeAgencyFilters", () => {
  it("keeps only known contact statuses", () => {
    expect(normalizeAgencyFilters({ contactStatus: "verified" })).toEqual({
      contactStatus: "verified",
      page: 1,
      pageSize: 50,
    });
    expect(normalizeAgencyFilters({ contactStatus: "bogus" })).toEqual({
      page: 1,
      pageSize: 50,
    });
  });

  it("trims search text", () => {
    expect(normalizeAgencyFilters({ search: "  treasury  " })).toEqual({
      page: 1,
      pageSize: 50,
      search: "treasury",
    });
  });

  it("normalizes pagination bounds", () => {
    expect(normalizeAgencyFilters({ page: "3", pageSize: "100" })).toMatchObject({
      page: 3,
      pageSize: 100,
    });
    expect(normalizeAgencyFilters({ page: "-1", pageSize: "999" })).toMatchObject({
      page: 1,
      pageSize: 50,
    });
  });
});

describe("buildAgencyListQuery", () => {
  it("filters by contact status and active state", () => {
    const query = buildAgencyListQuery({
      contactStatus: "missing",
      status: "active",
    });

    expect(query.sql).toContain("contact_status = ?");
    expect(query.sql).toContain("status = ?");
    expect(query.sql).toContain("LIMIT ? OFFSET ?");
    expect(query.bindings).toEqual(["missing", "active", 50, 0]);
  });

  it("searches name and slug", () => {
    const query = buildAgencyListQuery({ page: 2, pageSize: 25, search: "health" });

    expect(query.sql).toContain("lower(name) LIKE ?");
    expect(query.sql).toContain("lower(slug) LIKE ?");
    expect(query.bindings).toEqual(["%health%", "%health%", 25, 25]);
  });
});

describe("buildAllAgenciesQuery", () => {
  it("returns the browser list without pagination", () => {
    const query = buildAllAgenciesQuery();

    expect(query.sql).toContain("FROM sunlight_agencies");
    expect(query.sql).not.toContain("LIMIT");
    expect(query.bindings).toEqual([]);
  });
});

describe("buildAgencyWhereClause", () => {
  it("builds a reusable count/list predicate", () => {
    const clause = buildAgencyWhereClause({
      contactStatus: "verified",
      search: "council",
      status: "active",
    });

    expect(clause.sql).toContain("WHERE");
    expect(clause.sql).toContain("contact_status = ?");
    expect(clause.sql).toContain("status = ?");
    expect(clause.sql).toContain("lower(name) LIKE ?");
    expect(clause.bindings).toEqual(["verified", "active", "%council%", "%council%"]);
  });
});

describe("buildVerifyContactUpdate", () => {
  it("sets a verified primary email", () => {
    const query = buildVerifyContactUpdate({
      agencyId: "agy_1",
      email: " OIA@Example.govt.nz ",
    });

    expect(query.sql).toContain("contact_status = 'verified'");
    expect(query.bindings).toEqual(["oia@example.govt.nz", "agy_1"]);
  });

  it("rejects invalid email values", () => {
    expect(() =>
      buildVerifyContactUpdate({
        agencyId: "agy_1",
        email: "not-an-email",
      }),
    ).toThrow("valid email");
  });
});

describe("buildAssignTemplateUpdate", () => {
  it("sets an agency default template", () => {
    const query = buildAssignTemplateUpdate({
      agencyId: "agy_1",
      templateId: "tpl_1",
    });

    expect(query.sql).toContain("default_template_id = ?");
    expect(query.bindings).toEqual(["tpl_1", "agy_1"]);
  });
});
