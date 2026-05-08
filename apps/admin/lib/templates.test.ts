import { describe, expect, it } from "vitest";
import { buildCreateTemplateInput } from "./templates";

describe("buildCreateTemplateInput", () => {
  it("normalizes valid template form input", () => {
    const input = buildCreateTemplateInput({
      bodyTemplate: "Reply to {reply_email}",
      name: " Monthly ",
      subjectTemplate: "Request for {authority_name}",
    });

    expect(input.name).toBe("Monthly");
    expect(input.status).toBe("active");
  });

  it("rejects unsupported variables", () => {
    expect(() =>
      buildCreateTemplateInput({
        bodyTemplate: "Hello {unknown}",
        name: "Bad",
        subjectTemplate: "Request",
      }),
    ).toThrow("unknown");
  });
});
