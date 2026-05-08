import { describe, expect, it } from "vitest";
import { isOverdueSunlightRequest, summarizeRequestTimeliness } from "./sunlight-requests";

describe("isOverdueSunlightRequest", () => {
  it("marks awaiting responses overdue after their due date", () => {
    expect(
      isOverdueSunlightRequest({
        expected_due_at: "2026-05-07",
        status: "awaiting_response",
      }, "2026-05-08"),
    ).toBe(true);
  });

  it("does not mark completed or undated requests overdue", () => {
    expect(
      isOverdueSunlightRequest({
        expected_due_at: "2026-05-01",
        status: "response_received",
      }, "2026-05-08"),
    ).toBe(false);
    expect(
      isOverdueSunlightRequest({
        expected_due_at: null,
        status: "awaiting_response",
      }, "2026-05-08"),
    ).toBe(false);
  });
});

describe("summarizeRequestTimeliness", () => {
  it("counts overdue and open requests", () => {
    expect(
      summarizeRequestTimeliness(
        [
          { expected_due_at: "2026-05-07", status: "awaiting_response" },
          { expected_due_at: "2026-05-10", status: "awaiting_response" },
          { expected_due_at: "2026-05-01", status: "response_received" },
        ],
        "2026-05-08",
      ),
    ).toEqual({
      open: 2,
      overdue: 1,
      total: 3,
    });
  });
});
