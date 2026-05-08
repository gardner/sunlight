import { describe, expect, it } from "vitest";
import {
  addWorkingDays,
  buildReplyEmail,
  buildResponseUrl,
  renderTemplate,
  validateTemplateVariables,
} from "./request-prep";

describe("addWorkingDays", () => {
  it("skips weekends", () => {
    expect(addWorkingDays("2026-05-08", 1)).toBe("2026-05-11");
    expect(addWorkingDays("2026-05-08", 20)).toBe("2026-06-05");
  });

  it("skips configured holidays", () => {
    expect(addWorkingDays("2026-05-08", 1, new Set(["2026-05-11"]))).toBe("2026-05-12");
  });
});

describe("template rendering", () => {
  it("renders known variables", () => {
    expect(
      renderTemplate("Kia ora {agency_name}: {response_url}", {
        agency_name: "The Treasury",
        response_url: "https://requests.sunlight.nz/response/token",
      }),
    ).toBe("Kia ora The Treasury: https://requests.sunlight.nz/response/token");
  });

  it("rejects unknown variables", () => {
    expect(() => validateTemplateVariables("Hello {not_allowed}")).toThrow("not_allowed");
  });
});

describe("case token helpers", () => {
  it("builds unique reply email local-parts without plus addressing", () => {
    expect(buildReplyEmail("abc123")).toBe("reply-abc123@sunlight.nz");
  });

  it("builds agency response URLs", () => {
    expect(buildResponseUrl("abc123")).toBe("https://requests.sunlight.nz/response/abc123");
  });
});
