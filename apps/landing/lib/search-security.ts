const MAX_SEARCH_BODY_BYTES = 4096;
const HASH_PREFIX_LENGTH = 32;
const RATE_LIMITS = [
  {
    maxRequests: 12,
    name: "minute",
    windowSeconds: 60,
  },
  {
    maxRequests: 200,
    name: "day",
    windowSeconds: 86_400,
  },
] as const;

interface D1PreparedStatementLike {
  bind(...values: unknown[]): {
    first<T = Record<string, unknown>>(): Promise<T | null>;
    run(): Promise<unknown>;
  };
}

export interface RateLimitDatabase {
  prepare(query: string): D1PreparedStatementLike;
}

export interface RateLimitBucket {
  bucketKey: string;
  clientHash: string;
  expiresAt: number;
  limitName: string;
  maxRequests: number;
  retryAfterSeconds: number;
  windowSeconds: number;
  windowStart: number;
}

export interface RateLimitResult {
  allowed: boolean;
  limitName?: string;
  retryAfterSeconds?: number;
}

export class SearchRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SearchRequestError";
    this.status = status;
  }
}

export async function readLimitedSearchJsonBody(
  request: Request,
  maxBytes = MAX_SEARCH_BODY_BYTES,
): Promise<Record<string, unknown>> {
  assertSupportedContentType(request);
  assertContentLength(request, maxBytes);

  const bodyText = await request.text();
  if (encodedByteLength(bodyText) > maxBytes) {
    throw new SearchRequestError("Search requests must be 4 KB or smaller.", 413);
  }
  if (!bodyText.trim()) {
    return {};
  }

  try {
    const value = JSON.parse(bodyText);
    return isRecord(value) ? value : {};
  } catch {
    throw new SearchRequestError("Search requests must contain valid JSON.", 400);
  }
}

export async function checkSearchRateLimit(
  database: RateLimitDatabase,
  request: Request,
  nowMs = Date.now(),
): Promise<RateLimitResult> {
  const clientHash = await clientHashForRequest(request);
  const nowSeconds = Math.floor(nowMs / 1000);
  const buckets = buildRateLimitBuckets(clientHash, nowSeconds);

  try {
    for (const bucket of buckets) {
      const requestCount = await incrementRateLimitBucket(database, bucket);
      if (requestCount > bucket.maxRequests) {
        return {
          allowed: false,
          limitName: bucket.limitName,
          retryAfterSeconds: bucket.retryAfterSeconds,
        };
      }
    }

    if (shouldCleanupRateLimits(clientHash, nowSeconds)) {
      await database
        .prepare("DELETE FROM search_rate_limits WHERE expires_at < ?")
        .bind(nowSeconds)
        .run();
    }

    return { allowed: true };
  } catch (error) {
    console.warn("Sunlight search rate-limit check failed; allowing request", error);
    return { allowed: true };
  }
}

export function assertSupportedContentType(request: Request): void {
  const contentType = request.headers.get("content-type");
  if (!contentType) {
    return;
  }

  const mediaType = contentType.split(";")[0]?.trim().toLowerCase();
  if (mediaType !== "application/json") {
    throw new SearchRequestError("Search requests must use application/json.", 415);
  }
}

export function assertContentLength(request: Request, maxBytes = MAX_SEARCH_BODY_BYTES): void {
  const contentLength = request.headers.get("content-length");
  if (!contentLength) {
    return;
  }

  const byteLength = Number(contentLength);
  if (!Number.isFinite(byteLength) || byteLength < 0) {
    throw new SearchRequestError("Search request content-length is invalid.", 400);
  }
  if (byteLength > maxBytes) {
    throw new SearchRequestError("Search requests must be 4 KB or smaller.", 413);
  }
}

export function buildRateLimitBuckets(clientHash: string, nowSeconds: number): RateLimitBucket[] {
  return RATE_LIMITS.map((limit) => {
    const windowStart = Math.floor(nowSeconds / limit.windowSeconds) * limit.windowSeconds;
    const expiresAt = windowStart + limit.windowSeconds;

    return {
      bucketKey: `search:${limit.name}:${windowStart}:${clientHash}`,
      clientHash,
      expiresAt,
      limitName: limit.name,
      maxRequests: limit.maxRequests,
      retryAfterSeconds: Math.max(1, expiresAt - nowSeconds),
      windowSeconds: limit.windowSeconds,
      windowStart,
    };
  });
}

export function shouldCleanupRateLimits(clientHash: string, nowSeconds: number): boolean {
  const cleanupSlot = Number.parseInt(clientHash.slice(0, 2), 16) % 60;
  return nowSeconds % 60 === cleanupSlot;
}

async function incrementRateLimitBucket(
  database: RateLimitDatabase,
  bucket: RateLimitBucket,
): Promise<number> {
  await database.prepare(`
    INSERT INTO search_rate_limits (
      bucket_key,
      client_hash,
      limit_name,
      window_start,
      window_seconds,
      expires_at,
      request_count
    )
    VALUES (?, ?, ?, ?, ?, ?, 1)
    ON CONFLICT(bucket_key) DO UPDATE SET
      request_count = request_count + 1,
      updated_at = CURRENT_TIMESTAMP
  `).bind(
    bucket.bucketKey,
    bucket.clientHash,
    bucket.limitName,
    bucket.windowStart,
    bucket.windowSeconds,
    bucket.expiresAt,
  ).run();

  const row = await database
    .prepare("SELECT request_count FROM search_rate_limits WHERE bucket_key = ?")
    .bind(bucket.bucketKey)
    .first<{ request_count?: number | string }>();

  return readRequestCount(row);
}

async function clientHashForRequest(request: Request): Promise<string> {
  const clientIp = readClientIp(request);
  const userAgent = (request.headers.get("user-agent") ?? "unknown").slice(0, 160);
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(`${clientIp}|${userAgent}`),
  );

  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, HASH_PREFIX_LENGTH);
}

function readClientIp(request: Request): string {
  const connectingIp = request.headers.get("cf-connecting-ip");
  if (connectingIp) {
    return connectingIp;
  }

  const forwardedFor = request.headers.get("x-forwarded-for");
  return forwardedFor?.split(",")[0]?.trim() || "unknown";
}

function readRequestCount(row: { request_count?: number | string } | null): number {
  if (!row) {
    return 1;
  }
  if (typeof row.request_count === "number") {
    return row.request_count;
  }
  if (typeof row.request_count === "string") {
    const parsed = Number(row.request_count);
    return Number.isFinite(parsed) ? parsed : 1;
  }
  return 1;
}

function encodedByteLength(value: string): number {
  return new TextEncoder().encode(value).byteLength;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
