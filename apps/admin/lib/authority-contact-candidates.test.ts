import { describe, expect, it } from "vitest";
import {
  buildAcceptContactCandidateStatements,
  buildContactCandidateListQuery,
  buildMarkAuthorityContactInvalidStatements,
  buildRejectContactCandidateStatements,
  groupContactCandidates,
} from "./authority-contact-candidates";

describe("buildContactCandidateListQuery", () => {
  it("lists candidate evidence for one authority", () => {
    const query = buildContactCandidateListQuery("auth_1");

    expect(query.sql).toContain("FROM sunlight_authority_contact_candidates");
    expect(query.sql).toContain("WHERE authority_id = ?");
    expect(query.bindings).toEqual(["auth_1"]);
  });
});

describe("groupContactCandidates", () => {
  it("groups duplicate evidence rows by normalized email", () => {
    const groups = groupContactCandidates([
      candidateRow({
        confidence: 70,
        normalized_email: "oia@example.govt.nz",
        source_url: "https://example.govt.nz/contact",
      }),
      candidateRow({
        confidence: 90,
        normalized_email: "oia@example.govt.nz",
        source_url: "https://example.govt.nz/oia",
      }),
      candidateRow({
        confidence: 80,
        normalized_email: "info@example.govt.nz",
        source_url: "https://example.govt.nz/contact",
      }),
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0]).toMatchObject({
      candidate_count: 2,
      confidence: 90,
      normalized_email: "oia@example.govt.nz",
      status: "candidate",
    });
    expect(groups[0].evidence.map((item) => item.source_url)).toEqual([
      "https://example.govt.nz/contact",
      "https://example.govt.nz/oia",
    ]);
  });

  it("puts accepted groups before candidate groups", () => {
    const groups = groupContactCandidates([
      candidateRow({ normalized_email: "candidate@example.govt.nz" }),
      candidateRow({ normalized_email: "accepted@example.govt.nz", status: "accepted" }),
    ]);

    expect(groups.map((group) => group.normalized_email)).toEqual([
      "accepted@example.govt.nz",
      "candidate@example.govt.nz",
    ]);
  });
});

describe("buildAcceptContactCandidateStatements", () => {
  it("accepts a grouped candidate as the primary request address", () => {
    const statements = buildAcceptContactCandidateStatements({
      actor: { email: "admin@example.com", id: "adm_1" },
      auditId: "aud_1",
      authorityId: "auth_1",
      decision: "primary",
      email: " OIA@Example.govt.nz ",
    });

    expect(statements).toHaveLength(3);
    expect(statements[0].sql).toContain("SET status = ?");
    expect(statements[0].bindings).toEqual(["accepted", "auth_1", "oia@example.govt.nz"]);
    expect(statements[1].sql).toContain("primary_request_email = ?");
    expect(statements[1].sql).toContain("contact_status = 'verified'");
    expect(statements[2].bindings).toContain("authority.contact_candidate_accepted_primary");
    expect(statements[2].bindings).toContain("adm_1");
    expect(statements[2].bindings).toContain("admin@example.com");
  });

  it("accepts a grouped candidate as a secondary request address", () => {
    const statements = buildAcceptContactCandidateStatements({
      auditId: "aud_1",
      authorityId: "auth_1",
      decision: "secondary",
      email: "info@example.govt.nz",
    });

    expect(statements[1].sql).toContain("secondary_request_emails_json");
    expect(statements[1].sql).toContain("json_insert");
    expect(statements[2].bindings).toContain("authority.contact_candidate_accepted_secondary");
  });

  it("rejects invalid email decisions", () => {
    expect(() =>
      buildAcceptContactCandidateStatements({
        auditId: "aud_1",
        authorityId: "auth_1",
        decision: "primary",
        email: "not an email",
      }),
    ).toThrow("valid email");
  });
});

describe("buildRejectContactCandidateStatements", () => {
  it("rejects every evidence row for a candidate email", () => {
    const statements = buildRejectContactCandidateStatements({
      auditId: "aud_1",
      authorityId: "auth_1",
      email: "info@example.govt.nz",
    });

    expect(statements).toHaveLength(2);
    expect(statements[0].bindings).toEqual(["rejected", "auth_1", "info@example.govt.nz"]);
    expect(statements[1].bindings).toContain("authority.contact_candidate_rejected");
  });
});

describe("buildMarkAuthorityContactInvalidStatements", () => {
  it("audits the invalid decision and blocks sending", () => {
    const statements = buildMarkAuthorityContactInvalidStatements({
      auditId: "aud_1",
      authorityId: "auth_1",
    });

    expect(statements).toHaveLength(3);
    expect(statements[0].sql).toContain("authority.contact_marked_invalid");
    expect(statements[1].sql).toContain("contact_status = 'invalid'");
    expect(statements[2].sql).toContain("status = 'rejected'");
  });
});

function candidateRow(
  overrides: Partial<Parameters<typeof groupContactCandidates>[0][number]> = {},
): Parameters<typeof groupContactCandidates>[0][number] {
  const normalizedEmail = overrides.normalized_email ?? "oia@example.govt.nz";

  return {
    confidence: 75,
    confidence_reason: "strong local part",
    discovery_method: "linked_page",
    email: normalizedEmail,
    first_seen_at: "2026-05-08T00:00:00.000Z",
    id: `acc_${normalizedEmail}`,
    last_seen_at: "2026-05-08T00:00:00.000Z",
    normalized_email: normalizedEmail,
    source_page_title: "Contact",
    source_snippet: normalizedEmail,
    source_url: "https://example.govt.nz/contact",
    status: "candidate",
    ...overrides,
  };
}
