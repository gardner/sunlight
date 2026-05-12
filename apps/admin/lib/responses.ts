export interface ResponseDetail {
  id: string;
  channel: string;
  category: string;
  status: string;
  received_at: string;
  submitter_email: string | null;
  notes: string | null;
}

export interface InboundEmail {
  id: string;
  sunlight_request_id: string;
  from_email: string;
  subject: string;
  received_at: string;
  raw_r2_key: string;
  body_text?: string;
  body_html?: string;
  message_id_header: string | null;
}

export interface OutboundEmail {
  id: string;
  from_email: string;
  to_emails_json: string;
  subject: string;
  body_text: string;
  body_html?: string;
  sent_at: string;
  status: string;
  created_at: string;
}

export interface RefusalMitigation {
  id: string;
  refusal_reason: string;
  status: string;
  drafted_response: string;
  sunlight_response_id: string;
}

export interface SunlightUpload {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  r2_key: string;
  status: string;
  created_at: string;
}

export interface SunlightInboundAttachment {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  r2_key: string;
  status: string;
  created_at: string;
}

export interface InboundEmailInboxItem extends InboundEmail {
  needs_human_review: number;
  human_review_status: string;
  ai_triage_reason: string | null;
  authority_name: string | null;
}

export async function listInboxEmails(db: D1Database): Promise<InboundEmailInboxItem[]> {
  const result = await db.prepare(`
    SELECT e.*, a.name AS authority_name
    FROM sunlight_inbound_emails e
    LEFT JOIN sunlight_requests r ON e.sunlight_request_id = r.id
    LEFT JOIN sunlight_authorities a ON r.authority_id = a.id
    WHERE e.needs_human_review = 1 AND e.human_review_status = 'pending'
    ORDER BY e.received_at ASC
  `).all<InboundEmailInboxItem>();
  return result.results;
}

export async function resolveInboxEmail(db: D1Database, emailId: string): Promise<void> {
  await db.prepare(`
    UPDATE sunlight_inbound_emails
    SET human_review_status = 'resolved', updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    WHERE id = ?
  `).bind(emailId).run();
}

export async function getInboundEmail(db: D1Database, emailId: string): Promise<InboundEmailInboxItem | null> {
  return db.prepare(`
    SELECT e.*, a.name AS authority_name, r.reply_email
    FROM sunlight_inbound_emails e
    LEFT JOIN sunlight_requests r ON e.sunlight_request_id = r.id
    LEFT JOIN sunlight_authorities a ON r.authority_id = a.id
    WHERE e.id = ?
  `).bind(emailId).first<InboundEmailInboxItem & { reply_email: string }>();
}

export async function saveOutboundEmail(
  db: D1Database,
  requestId: string,
  fromEmail: string,
  toEmails: string[],
  subject: string,
  bodyText: string,
  providerMessageId?: string
): Promise<void> {
  const id = `out_${crypto.randomUUID().replaceAll("-", "")}`;
  await db.prepare(`
    INSERT INTO sunlight_outbound_emails (
      id, sunlight_request_id, from_email, to_emails_json, subject, body_text, status, sent_at, provider_message_id
    ) VALUES (?, ?, ?, ?, ?, ?, 'sent', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), ?)
  `).bind(id, requestId, fromEmail, JSON.stringify(toEmails), subject, bodyText, providerMessageId ?? null).run();
}

export async function getRequestDetail(db: D1Database, requestId: string) {
  return db.prepare(`
    SELECT
      sunlight_requests.*,
      sunlight_authorities.name AS authority_name,
      sunlight_request_cycles.cycle_month
    FROM sunlight_requests
    JOIN sunlight_authorities ON sunlight_authorities.id = sunlight_requests.authority_id
    JOIN sunlight_request_cycles ON sunlight_request_cycles.id = sunlight_requests.cycle_id
    WHERE sunlight_requests.id = ?
  `).bind(requestId).first<any>();
}

export async function listRequestResponses(db: D1Database, requestId: string): Promise<ResponseDetail[]> {
  const result = await db.prepare(`
    SELECT * FROM sunlight_responses WHERE sunlight_request_id = ? ORDER BY received_at DESC
  `).bind(requestId).all<ResponseDetail>();
  return result.results;
}

export async function listRequestInboundEmails(db: D1Database, requestId: string): Promise<InboundEmail[]> {
  const result = await db.prepare(`
    SELECT * FROM sunlight_inbound_emails WHERE sunlight_request_id = ? ORDER BY received_at ASC
  `).bind(requestId).all<InboundEmail>();
  return result.results;
}

export async function listRequestOutboundEmails(db: D1Database, requestId: string): Promise<OutboundEmail[]> {
  const result = await db.prepare(`
    SELECT * FROM sunlight_outbound_emails WHERE sunlight_request_id = ? ORDER BY sent_at ASC
  `).bind(requestId).all<OutboundEmail>();
  return result.results;
}

export async function listRequestMitigations(db: D1Database, requestId: string): Promise<RefusalMitigation[]> {
  const result = await db.prepare(`
    SELECT * FROM sunlight_refusal_mitigations WHERE sunlight_request_id = ? ORDER BY created_at DESC
  `).bind(requestId).all<RefusalMitigation>();
  return result.results;
}

export async function listRequestUploads(db: D1Database, requestId: string): Promise<SunlightUpload[]> {
  const result = await db.prepare(`
    SELECT id, original_filename, content_type, size_bytes, r2_key, status, created_at
    FROM sunlight_uploads 
    WHERE sunlight_request_id = ? 
    ORDER BY created_at DESC
  `).bind(requestId).all<SunlightUpload>();
  return result.results;
}

export async function listRequestInboundAttachments(db: D1Database, requestId: string): Promise<SunlightInboundAttachment[]> {
  const result = await db.prepare(`
    SELECT id, filename, content_type, size_bytes, r2_key, status, created_at
    FROM sunlight_inbound_attachments 
    WHERE sunlight_request_id = ? 
    ORDER BY created_at DESC
  `).bind(requestId).all<SunlightInboundAttachment>();
  return result.results;
}

export async function getUpload(db: D1Database, uploadId: string, requestId: string): Promise<SunlightUpload | null> {
  return db.prepare(`
    SELECT id, original_filename, content_type, size_bytes, r2_key, status, created_at
    FROM sunlight_uploads
    WHERE id = ? AND sunlight_request_id = ?
  `).bind(uploadId, requestId).first<SunlightUpload>();
}

export async function getInboundAttachment(db: D1Database, attachmentId: string, requestId: string): Promise<SunlightInboundAttachment | null> {
  return db.prepare(`
    SELECT id, filename, content_type, size_bytes, r2_key, status, created_at
    FROM sunlight_inbound_attachments
    WHERE id = ? AND sunlight_request_id = ?
  `).bind(attachmentId, requestId).first<SunlightInboundAttachment>();
}

export async function updateMitigationStatus(db: D1Database, mitigationId: string, status: string, responseBody: string) {
  await db.prepare(`
    UPDATE sunlight_refusal_mitigations 
    SET status = ?, drafted_response = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') 
    WHERE id = ?
  `).bind(status, responseBody, mitigationId).run();
}
