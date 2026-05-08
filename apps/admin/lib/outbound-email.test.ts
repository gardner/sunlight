import { describe, expect, it } from "vitest";
import {
  buildCloudflareEmailMessage,
  filterFailedPreparedRequests,
  renderSunlightRequestEmail,
  summarizeOutboundEmailStatuses,
  type PreparedSunlightRequest,
} from "./outbound-email";

const preparedRequest: PreparedSunlightRequest = {
  authority_id: "agy_1",
  authority_name: "The Treasury",
  body_template:
    "Tena koe {authority_name},\n\nPlease provide requests and responses for {covered_date_range}.\n\nUpload large files at {response_url}.",
  case_token_hint: "abc123",
  cycle_id: "cyc_2026_05",
  cycle_month: "2026-05",
  covered_from: "2026-05-01",
  covered_until: "2026-05-31",
  legal_regime: "OIA",
  primary_request_email: "oia@example.govt.nz",
  reply_email: "reply-abc123@sunlight.nz",
  response_url: "https://requests.sunlight.nz/response/abc123",
  subject_template: "OIA request for {authority_name} - {cycle_month}",
  sunlight_request_id: "srq_1",
  template_id: "tpl_1",
};

describe("renderSunlightRequestEmail", () => {
  it("renders the subject and body with request variables", () => {
    expect(renderSunlightRequestEmail(preparedRequest)).toEqual({
      bodyText:
        "Tena koe The Treasury,\n\nPlease provide requests and responses for 2026-05-01 to 2026-05-31.\n\nUpload large files at https://requests.sunlight.nz/response/abc123.",
      fromEmail: "requests@sunlight.nz",
      replyEmail: "reply-abc123@sunlight.nz",
      responseUrl: "https://requests.sunlight.nz/response/abc123",
      subject: "OIA request for The Treasury - 2026-05",
      sunlightRequestId: "srq_1",
      toEmails: ["oia@example.govt.nz"],
    });
  });

  it("supports an explicit sender address", () => {
    const rendered = renderSunlightRequestEmail(preparedRequest, {
      fromEmail: "sunlight@sunlight.nz",
    });

    expect(rendered.fromEmail).toBe("sunlight@sunlight.nz");
  });
});

describe("buildCloudflareEmailMessage", () => {
  it("uses the Sunlight reply address as Reply-To", () => {
    const rendered = renderSunlightRequestEmail(preparedRequest);

    expect(buildCloudflareEmailMessage(rendered)).toEqual({
      from: "requests@sunlight.nz",
      headers: {
        "X-Sunlight-Request-ID": "srq_1",
      },
      replyTo: "reply-abc123@sunlight.nz",
      subject: "OIA request for The Treasury - 2026-05",
      text:
        "Tena koe The Treasury,\n\nPlease provide requests and responses for 2026-05-01 to 2026-05-31.\n\nUpload large files at https://requests.sunlight.nz/response/abc123.",
      to: ["oia@example.govt.nz"],
    });
  });
});

describe("outbound send results", () => {
  it("summarizes outbound email statuses", () => {
    expect(
      summarizeOutboundEmailStatuses([
        { status: "sent" },
        { status: "sent" },
        { status: "failed" },
      ]),
    ).toEqual({
      failed: 1,
      sent: 2,
      total: 3,
    });
  });

  it("filters failed prepared requests for retry", () => {
    expect(
      filterFailedPreparedRequests([
        { ...preparedRequest, request_status: "failed" },
        { ...preparedRequest, sunlight_request_id: "srq_2", request_status: "scheduled" },
      ]),
    ).toEqual([{ ...preparedRequest, request_status: "failed" }]);
  });
});
