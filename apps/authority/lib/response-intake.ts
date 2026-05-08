import { AwsClient } from "aws4fetch";
import { sha256Hex } from "./tokens";

const MAX_SINGLE_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024;
const DEFAULT_UPLOAD_EXPIRES_SECONDS = 60 * 15;
const RESPONSE_CATEGORIES = new Set([
  "acknowledgement",
  "clarification_request",
  "extension_notice",
  "transfer_notice",
  "refusal",
  "partial_response",
  "full_response",
  "no_records_held",
  "follow_up",
  "unknown",
]);

export interface AuthoritySunlightRequest {
  authority_id: string;
  authority_name: string;
  case_token_hint: string;
  closed_at: string | null;
  covered_from: string;
  covered_until: string;
  cycle_month: string;
  id: string;
  reply_email: string;
  status: string;
}

export interface ResponseSubmission {
  authorityReference: string | null;
  category: string;
  notes: string | null;
  submitterEmail: string | null;
  submitterName: string | null;
}

export interface BrowserUploadRequest {
  contentType: string | null;
  originalFilename: string;
  sizeBytes: number;
}

export interface R2PresignConfig {
  accessKeyId: string;
  accountId: string;
  bucketName: string;
  expiresSeconds?: number;
  secretAccessKey: string;
}

export interface CreatedUpload {
  expiresAt: string;
  headers: Record<string, string>;
  method: "PUT";
  r2Key: string;
  uploadId: string;
  uploadUrl: string;
}

export function buildResponseSubmission(input: {
  authorityReference?: FormDataEntryValue | null;
  category?: FormDataEntryValue | null;
  notes?: FormDataEntryValue | null;
  submitterEmail?: FormDataEntryValue | null;
  submitterName?: FormDataEntryValue | null;
}): ResponseSubmission {
  const category = textValue(input.category) || "full_response";
  if (!RESPONSE_CATEGORIES.has(category)) {
    throw new Error("Unsupported response category");
  }

  return {
    authorityReference: nullableText(input.authorityReference),
    category,
    notes: nullableText(input.notes),
    submitterEmail: nullableText(input.submitterEmail),
    submitterName: nullableText(input.submitterName),
  };
}

export function buildUploadRequest(input: {
  contentType?: unknown;
  filename?: unknown;
  sizeBytes?: unknown;
}): BrowserUploadRequest {
  const originalFilename = String(input.filename ?? "").trim();
  const sizeBytes = Number(input.sizeBytes);
  const contentType = String(input.contentType ?? "").trim() || null;

  if (!originalFilename) {
    throw new Error("Upload filename is required");
  }
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) {
    throw new Error("Upload cannot be empty");
  }
  if (sizeBytes > MAX_SINGLE_UPLOAD_BYTES) {
    throw new Error("Upload is larger than the current single-file limit");
  }

  return {
    contentType,
    originalFilename,
    sizeBytes,
  };
}

export function buildR2ObjectKey(input: {
  originalFilename: string;
  requestId: string;
  uploadId: string;
}): string {
  return [
    "sunlight-requests",
    input.requestId,
    "uploads",
    input.uploadId,
    sanitizeFilename(input.originalFilename),
  ].join("/");
}

export function sanitizeFilename(filename: string): string {
  const basename = filename.split(/[\\/]/).at(-1)?.trim().toLowerCase() ?? "";
  const safe = basename
    .replaceAll(/[^a-z0-9._-]+/g, "-")
    .replaceAll(/-+/g, "-")
    .replaceAll(/-\./g, ".")
    .replaceAll(/(^[-.]+|[-.]+$)/g, "");
  return safe || "upload.bin";
}

export async function getSunlightRequestByToken(
  db: D1Database,
  caseToken: string,
): Promise<AuthoritySunlightRequest | null> {
  const tokenHash = await sha256Hex(caseToken);
  return db
    .prepare(
      `
        SELECT
          sunlight_requests.id,
          sunlight_requests.authority_id,
          sunlight_requests.case_token_hint,
          sunlight_requests.reply_email,
          sunlight_requests.status,
          sunlight_requests.closed_at,
          sunlight_authorities.name AS authority_name,
          sunlight_request_cycles.cycle_month,
          sunlight_request_cycles.covered_from,
          sunlight_request_cycles.covered_until
        FROM sunlight_requests
        JOIN sunlight_authorities ON sunlight_authorities.id = sunlight_requests.authority_id
        JOIN sunlight_request_cycles ON sunlight_request_cycles.id = sunlight_requests.cycle_id
        WHERE sunlight_requests.case_token_hash = ?
        LIMIT 1
      `,
    )
    .bind(tokenHash)
    .first<AuthoritySunlightRequest>();
}

export async function submitSunlightResponse(
  db: D1Database,
  request: AuthoritySunlightRequest,
  submission: ResponseSubmission,
): Promise<string> {
  const existing = await db
    .prepare(
      `
        SELECT id
        FROM sunlight_responses
        WHERE sunlight_request_id = ?
          AND channel = 'upload'
          AND status IN ('received', 'needs_review')
        ORDER BY created_at DESC
        LIMIT 1
      `,
    )
    .bind(request.id)
    .first<{ id: string }>();

  const responseId = existing?.id ?? `rsp_${crypto.randomUUID().replaceAll("-", "")}`;
  if (existing) {
    await updateSunlightResponse(db, responseId, submission);
  } else {
    await insertSunlightResponse(db, responseId, request, submission);
  }

  await db
    .prepare(
      `
        UPDATE sunlight_requests
        SET status = ?,
            last_response_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(requestStatusForCategory(submission.category), request.id)
    .run();

  await insertAuditEvent(db, request.id, "sunlight_response.submitted", {
    category: submission.category,
    response_id: responseId,
  });

  return responseId;
}

export async function createUpload(
  db: D1Database,
  request: AuthoritySunlightRequest,
  upload: BrowserUploadRequest,
  config: R2PresignConfig,
): Promise<CreatedUpload> {
  const uploadSessionId = `ups_${crypto.randomUUID().replaceAll("-", "")}`;
  const uploadId = `upl_${crypto.randomUUID().replaceAll("-", "")}`;
  const r2Key = buildR2ObjectKey({
    originalFilename: upload.originalFilename,
    requestId: request.id,
    uploadId,
  });
  const expiresSeconds = config.expiresSeconds ?? DEFAULT_UPLOAD_EXPIRES_SECONDS;
  const expiresAt = new Date(Date.now() + expiresSeconds * 1000).toISOString();

  await db
    .prepare(
      `
        INSERT INTO sunlight_upload_sessions (
          id,
          sunlight_request_id,
          status,
          expires_at
        ) VALUES (?, ?, 'open', ?)
      `,
    )
    .bind(uploadSessionId, request.id, expiresAt)
    .run();

  await db
    .prepare(
      `
        INSERT INTO sunlight_uploads (
          id,
          sunlight_request_id,
          upload_session_id,
          original_filename,
          safe_filename,
          content_type,
          size_bytes,
          r2_bucket,
          r2_key,
          status,
          validation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'not_checked')
      `,
    )
    .bind(
      uploadId,
      request.id,
      uploadSessionId,
      upload.originalFilename,
      sanitizeFilename(upload.originalFilename),
      upload.contentType,
      upload.sizeBytes,
      config.bucketName,
      r2Key,
    )
    .run();

  await insertAuditEvent(db, request.id, "sunlight_upload.created", {
    r2_key: r2Key,
    upload_id: uploadId,
  });

  const signed = await presignR2PutUrl(config, r2Key, upload.contentType);
  return {
    expiresAt,
    headers: upload.contentType ? { "Content-Type": upload.contentType } : {},
    method: "PUT",
    r2Key,
    uploadId,
    uploadUrl: signed,
  };
}

export async function completeUpload(
  db: D1Database,
  bucket: R2Bucket,
  request: AuthoritySunlightRequest,
  uploadId: string,
): Promise<void> {
  const upload = await db
    .prepare(
      `
        SELECT r2_key
        FROM sunlight_uploads
        WHERE id = ?
          AND sunlight_request_id = ?
        LIMIT 1
      `,
    )
    .bind(uploadId, request.id)
    .first<{ r2_key: string }>();

  if (!upload) {
    throw new Error("Unknown upload");
  }

  const object = await bucket.head(upload.r2_key);
  if (!object) {
    throw new Error("Upload object is not available in R2 yet");
  }

  await db
    .prepare(
      `
        UPDATE sunlight_uploads
        SET status = 'uploaded',
            size_bytes = ?,
            etag = ?,
            completed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(object.size, object.etag, uploadId)
    .run();

  await db
    .prepare(
      `
        UPDATE sunlight_upload_sessions
        SET status = 'completed',
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = (
          SELECT upload_session_id FROM sunlight_uploads WHERE id = ?
        )
      `,
    )
    .bind(uploadId)
    .run();

  await insertAuditEvent(db, request.id, "sunlight_upload.completed", {
    upload_id: uploadId,
  });
}

function textValue(value: FormDataEntryValue | null | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function nullableText(value: FormDataEntryValue | null | undefined): string | null {
  const text = textValue(value);
  return text || null;
}

function requestStatusForCategory(category: string): string {
  return category === "partial_response" ? "partially_received" : "response_received";
}

async function insertSunlightResponse(
  db: D1Database,
  responseId: string,
  request: AuthoritySunlightRequest,
  submission: ResponseSubmission,
): Promise<void> {
  await db
    .prepare(
      `
        INSERT INTO sunlight_responses (
          id,
          sunlight_request_id,
          authority_id,
          channel,
          category,
          status,
          received_at,
          authority_reference,
          submitter_name,
          submitter_email,
          notes
        ) VALUES (?, ?, ?, 'upload', ?, 'needs_review', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?, ?, ?, ?)
      `,
    )
    .bind(
      responseId,
      request.id,
      request.authority_id,
      submission.category,
      submission.authorityReference,
      submission.submitterName,
      submission.submitterEmail,
      submission.notes,
    )
    .run();
}

async function updateSunlightResponse(
  db: D1Database,
  responseId: string,
  submission: ResponseSubmission,
): Promise<void> {
  await db
    .prepare(
      `
        UPDATE sunlight_responses
        SET category = ?,
            received_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            authority_reference = ?,
            submitter_name = ?,
            submitter_email = ?,
            notes = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(
      submission.category,
      submission.authorityReference,
      submission.submitterName,
      submission.submitterEmail,
      submission.notes,
      responseId,
    )
    .run();
}

async function presignR2PutUrl(
  config: R2PresignConfig,
  r2Key: string,
  contentType: string | null,
): Promise<string> {
  const expiresSeconds = config.expiresSeconds ?? DEFAULT_UPLOAD_EXPIRES_SECONDS;
  const url = new URL(
    `https://${config.accountId}.r2.cloudflarestorage.com/${config.bucketName}/${r2Key}`,
  );
  url.searchParams.set("X-Amz-Expires", String(expiresSeconds));

  const client = new AwsClient({
    accessKeyId: config.accessKeyId,
    secretAccessKey: config.secretAccessKey,
    service: "s3",
    region: "auto",
  });
  const signed = await client.sign(url, {
    headers: contentType ? { "Content-Type": contentType } : {},
    method: "PUT",
    aws: {
      signQuery: true,
    },
  });

  return signed.url;
}

async function insertAuditEvent(
  db: D1Database,
  requestId: string,
  eventType: string,
  metadata: Record<string, unknown>,
): Promise<void> {
  await db
    .prepare(
      `
        INSERT INTO sunlight_audit_events (
          id,
          entity_type,
          entity_id,
          event_type,
          actor_type,
          actor_id,
          metadata_json
        ) VALUES (?, 'sunlight_request', ?, ?, 'authority_token', NULL, ?)
      `,
    )
    .bind(
      `aud_${crypto.randomUUID().replaceAll("-", "")}`,
      requestId,
      eventType,
      JSON.stringify(metadata),
    )
    .run();
}
