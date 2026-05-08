import { describe, expect, it } from "vitest";
import {
  buildCycleRange,
  buildSunlightRequestRecord,
  canApproveCycle,
  canSendCycle,
  summarizeSunlightRequestStatuses,
} from "./cycles";

describe("buildCycleRange", () => {
  it("builds calendar month ranges", () => {
    expect(buildCycleRange("2026-02")).toEqual({
      coveredFrom: "2026-02-01",
      coveredUntil: "2026-02-28",
    });
    expect(buildCycleRange("2028-02")).toEqual({
      coveredFrom: "2028-02-01",
      coveredUntil: "2028-02-29",
    });
  });
});

describe("buildSunlightRequestRecord", () => {
  it("builds request token fields and due date", async () => {
    const record = await buildSunlightRequestRecord({
      agency: {
        id: "agy_1",
        legal_regime: "OIA",
        name: "The Treasury",
        template_id: "tpl_1",
      },
      cycle: {
        covered_from: "2026-05-01",
        covered_until: "2026-05-31",
        cycle_month: "2026-05",
        id: "cyc_1",
      },
      token: "abc123",
      today: "2026-05-08",
    });

    expect(record.caseTokenHint).toBe("abc123");
    expect(record.replyEmail).toBe("reply-abc123@sunlight.nz");
    expect(record.responseUrl).toBe("https://requests.sunlight.nz/response/abc123");
    expect(record.expectedDueAt).toBe("2026-06-05");
    expect(record.caseTokenHash).toHaveLength(64);
  });
});

describe("cycle status transitions", () => {
  it("only approves previewed cycles", () => {
    expect(canApproveCycle("previewed")).toBe(true);
    expect(canApproveCycle("draft")).toBe(false);
    expect(canApproveCycle("sent")).toBe(false);
  });

  it("only sends approved cycles", () => {
    expect(canSendCycle("approved")).toBe(true);
    expect(canSendCycle("previewed")).toBe(false);
    expect(canSendCycle("sending")).toBe(false);
  });
});

describe("summarizeSunlightRequestStatuses", () => {
  it("counts request statuses for the cycle preview", () => {
    expect(
      summarizeSunlightRequestStatuses([
        { status: "scheduled" },
        { status: "scheduled" },
        { status: "awaiting_response" },
        { status: "failed" },
      ]),
    ).toEqual({
      awaiting_response: 1,
      failed: 1,
      scheduled: 2,
      total: 4,
    });
  });
});
