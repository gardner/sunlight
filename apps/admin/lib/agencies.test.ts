import { describe, expect, it } from "vitest";
import {
  buildAgencyListQuery,
  buildAssignTemplateUpdate,
  buildVerifyContactUpdate,
  normalizeAgencyFilters,
} from "./agencies";

describe("normalizeAgencyFilters", () => {
  it("keeps only known contact statuses", () => {
    expect(normalizeAgencyFilters({ contactStatus: "verified" })).toEqual({
      contactStatus: "verified",
    });
    expect(normalizeAgencyFilters({ contactStatus: "bogus" })).toEqual({});
  });

  it("trims search text", () => {
    expect(normalizeAgencyFilters({ search: "  treasury  " })).toEqual({
      search: "treasury",
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
    expect(query.bindings).toEqual(["missing", "active"]);
  });

  it("searches name and slug", () => {
    const query = buildAgencyListQuery({ search: "health" });

    expect(query.sql).toContain("lower(name) LIKE ?");
    expect(query.sql).toContain("lower(slug) LIKE ?");
    expect(query.bindings).toEqual(["%health%", "%health%"]);
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
