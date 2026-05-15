import { describe, expect, it } from "vitest";
import {
  SearchRequestError,
  assertContentLength,
  assertSupportedContentType,
  buildRateLimitBuckets,
  readLimitedSearchJsonBody,
  shouldCleanupRateLimits,
} from "./search-security";

describe("assertSupportedContentType", () => {
  it("accepts JSON requests with parameters", () => {
    expect(() => assertSupportedContentType(new Request("https://example.com", {
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
      method: "POST",
    }))).not.toThrow();
  });

  it("rejects non-JSON requests", () => {
    expect(() => assertSupportedContentType(new Request("https://example.com", {
      headers: {
        "content-type": "text/plain",
      },
      method: "POST",
    }))).toThrow(SearchRequestError);
  });
});

describe("assertContentLength", () => {
  it("rejects bodies over the configured limit", () => {
    expect(() => assertContentLength(new Request("https://example.com", {
      headers: {
        "content-length": "4097",
      },
      method: "POST",
    }), 4096)).toThrow("4 KB");
  });

  it("rejects invalid content-length headers", () => {
    expect(() => assertContentLength(new Request("https://example.com", {
      headers: {
        "content-length": "nope",
      },
      method: "POST",
    }))).toThrow("invalid");
  });
});

describe("readLimitedSearchJsonBody", () => {
  it("parses small JSON bodies", async () => {
    await expect(readLimitedSearchJsonBody(new Request("https://example.com", {
      body: JSON.stringify({ question: "What did Auckland Council release?" }),
      headers: {
        "content-type": "application/json",
      },
      method: "POST",
    }))).resolves.toEqual({ question: "What did Auckland Council release?" });
  });

  it("rejects invalid JSON", async () => {
    await expect(readLimitedSearchJsonBody(new Request("https://example.com", {
      body: "{",
      headers: {
        "content-type": "application/json",
      },
      method: "POST",
    }))).rejects.toThrow("valid JSON");
  });
});

describe("buildRateLimitBuckets", () => {
  it("builds minute and day buckets with retry times", () => {
    expect(buildRateLimitBuckets("abc123", 125)).toEqual([
      {
        bucketKey: "search:minute:120:abc123",
        clientHash: "abc123",
        expiresAt: 180,
        limitName: "minute",
        maxRequests: 12,
        retryAfterSeconds: 55,
        windowSeconds: 60,
        windowStart: 120,
      },
      {
        bucketKey: "search:day:0:abc123",
        clientHash: "abc123",
        expiresAt: 86400,
        limitName: "day",
        maxRequests: 200,
        retryAfterSeconds: 86275,
        windowSeconds: 86400,
        windowStart: 0,
      },
    ]);
  });
});

describe("shouldCleanupRateLimits", () => {
  it("assigns cleanup to a deterministic once-per-minute slot", () => {
    expect(shouldCleanupRateLimits("0fabcdef", 15)).toBe(true);
    expect(shouldCleanupRateLimits("0fabcdef", 16)).toBe(false);
  });
});
