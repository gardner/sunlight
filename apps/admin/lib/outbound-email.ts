import { renderTemplate, type TemplateVariables } from "./request-prep";

const DEFAULT_FROM_EMAIL = "requests@sunlight.nz";
const DEFAULT_CONTACT_DETAILS = "Sunlight, sunlight@sunlight.nz";

export interface PreparedSunlightRequest {
  authority_id: string;
  authority_name: string;
  body_template: string;
  case_token_hint: string;
  cycle_id: string;
  cycle_month: string;
  covered_from: string;
  covered_until: string;
  legal_regime: string;
  primary_request_email: string;
  reply_email: string;
  request_status?: string;
  response_url: string;
  subject_template: string;
  sunlight_request_id: string;
  template_id: string;
}

export interface OutboundEmailLog {
  authority_name: string;
  error_message: string | null;
  id: string;
  sent_at: string | null;
  status: string;
  subject: string;
  to_emails_json: string;
}

export type OutboundStatusSummary = Record<string, number> & { total: number };

export interface RenderedSunlightRequestEmail {
  bodyText: string;
  fromEmail: string;
  replyEmail: string;
  responseUrl: string;
  subject: string;
  sunlightRequestId: string;
  toEmails: string[];
}

export interface EmailSendBinding {
  send(message: {
    from: string;
    headers?: Record<string, string>;
    replyTo?: string;
    subject: string;
    text: string;
    to: string[];
  }): Promise<unknown>;
}

export function renderSunlightRequestEmail(
  request: PreparedSunlightRequest,
  options: {
    contactDetails?: string;
    fromEmail?: string;
  } = {},
): RenderedSunlightRequestEmail {
  const variables: TemplateVariables = {
    authority_name: request.authority_name,
    covered_date_range: `${request.covered_from} to ${request.covered_until}`,
    cycle_month: request.cycle_month,
    legal_regime: request.legal_regime,
    reply_email: request.reply_email,
    response_url: request.response_url,
    sunlight_contact_details: options.contactDetails ?? DEFAULT_CONTACT_DETAILS,
  };

  return {
    bodyText: renderTemplate(request.body_template, variables),
    fromEmail: options.fromEmail ?? DEFAULT_FROM_EMAIL,
    replyEmail: request.reply_email,
    responseUrl: request.response_url,
    subject: renderTemplate(request.subject_template, variables),
    sunlightRequestId: request.sunlight_request_id,
    toEmails: [request.primary_request_email],
  };
}

export function buildCloudflareEmailMessage(email: RenderedSunlightRequestEmail) {
  return {
    from: email.fromEmail,
    headers: {
      "X-Sunlight-Request-ID": email.sunlightRequestId,
    },
    replyTo: email.replyEmail,
    subject: email.subject,
    text: email.bodyText,
    to: email.toEmails,
  };
}

export function summarizeOutboundEmailStatuses(
  emails: Array<Pick<OutboundEmailLog, "status">>,
): OutboundStatusSummary {
  const summary: OutboundStatusSummary = { total: emails.length };
  for (const email of emails) {
    summary[email.status] = (summary[email.status] ?? 0) + 1;
  }
  return summary;
}

export function filterFailedPreparedRequests<T extends { request_status?: string }>(
  requests: T[],
): T[] {
  return requests.filter((request) => request.request_status === "failed");
}

export async function listPreparedSunlightRequests(
  db: D1Database,
  cycleId: string,
): Promise<PreparedSunlightRequest[]> {
  const result = await db
    .prepare(
      `
        SELECT
          sunlight_requests.id AS sunlight_request_id,
          sunlight_requests.case_token_hint,
          sunlight_requests.reply_email,
          sunlight_requests.status AS request_status,
          sunlight_requests.response_url,
          sunlight_requests.cycle_id,
          sunlight_requests.template_id,
          sunlight_authorities.id AS authority_id,
          sunlight_authorities.name AS authority_name,
          sunlight_authorities.legal_regime,
          sunlight_authorities.primary_request_email,
          sunlight_request_cycles.cycle_month,
          sunlight_request_cycles.covered_from,
          sunlight_request_cycles.covered_until,
          sunlight_request_templates.subject_template,
          sunlight_request_templates.body_template
        FROM sunlight_requests
        JOIN sunlight_authorities ON sunlight_authorities.id = sunlight_requests.authority_id
        JOIN sunlight_request_cycles ON sunlight_request_cycles.id = sunlight_requests.cycle_id
        JOIN sunlight_request_templates ON sunlight_request_templates.id = sunlight_requests.template_id
        WHERE sunlight_requests.cycle_id = ?
          AND sunlight_requests.status IN ('scheduled', 'queued', 'failed')
          AND sunlight_authorities.primary_request_email IS NOT NULL
        ORDER BY sunlight_authorities.name
      `,
    )
    .bind(cycleId)
    .all<PreparedSunlightRequest>();

  return result.results;
}

export async function listCycleOutboundEmails(
  db: D1Database,
  cycleId: string,
): Promise<OutboundEmailLog[]> {
  const result = await db
    .prepare(
      `
        SELECT
          sunlight_outbound_emails.id,
          sunlight_outbound_emails.to_emails_json,
          sunlight_outbound_emails.subject,
          sunlight_outbound_emails.status,
          sunlight_outbound_emails.sent_at,
          sunlight_outbound_emails.error_message,
          sunlight_authorities.name AS authority_name
        FROM sunlight_outbound_emails
        JOIN sunlight_requests
          ON sunlight_requests.id = sunlight_outbound_emails.sunlight_request_id
        JOIN sunlight_authorities
          ON sunlight_authorities.id = sunlight_requests.authority_id
        WHERE sunlight_requests.cycle_id = ?
        ORDER BY sunlight_outbound_emails.created_at DESC
      `,
    )
    .bind(cycleId)
    .all<OutboundEmailLog>();

  return result.results;
}

export async function queueOutboundEmail(
  db: D1Database,
  email: RenderedSunlightRequestEmail,
): Promise<string> {
  const existing = await db
    .prepare(
      `
        SELECT id
        FROM sunlight_outbound_emails
        WHERE sunlight_request_id = ?
          AND status IN ('queued', 'sent', 'delivered')
        ORDER BY created_at DESC
        LIMIT 1
      `,
    )
    .bind(email.sunlightRequestId)
    .first<{ id: string }>();

  if (existing) {
    return existing.id;
  }

  const id = `eml_${crypto.randomUUID().replaceAll("-", "")}`;
  await db
    .prepare(
      `
        INSERT INTO sunlight_outbound_emails (
          id,
          sunlight_request_id,
          to_emails_json,
          from_email,
          reply_email,
          subject,
          body_text,
          response_url,
          provider,
          status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'cloudflare_email', 'queued')
      `,
    )
    .bind(
      id,
      email.sunlightRequestId,
      JSON.stringify(email.toEmails),
      email.fromEmail,
      email.replyEmail,
      email.subject,
      email.bodyText,
      email.responseUrl,
    )
    .run();

  await updateSunlightRequestStatus(db, email.sunlightRequestId, "queued");
  await insertAuditEvent(db, {
    entityId: email.sunlightRequestId,
    eventType: "sunlight_request.email_queued",
    metadata: { outbound_email_id: id },
  });

  return id;
}

export async function sendPreparedSunlightRequest(
  db: D1Database,
  binding: EmailSendBinding,
  request: PreparedSunlightRequest,
  options: { contactDetails?: string; fromEmail?: string } = {},
): Promise<"sent" | "failed"> {
  const rendered = renderSunlightRequestEmail(request, options);
  const emailId = await queueOutboundEmail(db, rendered);

  try {
    await binding.send(buildCloudflareEmailMessage(rendered));
  } catch (error) {
    await markOutboundFailed(db, emailId, request.sunlight_request_id, error);
    return "failed";
  }

  await db
    .prepare(
      `
        UPDATE sunlight_outbound_emails
        SET status = 'sent',
            sent_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(emailId)
    .run();

  await db
    .prepare(
      `
        UPDATE sunlight_requests
        SET status = 'awaiting_response',
            last_sent_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(request.sunlight_request_id)
    .run();

  await insertAuditEvent(db, {
    entityId: request.sunlight_request_id,
    eventType: "sunlight_request.email_sent",
    metadata: { outbound_email_id: emailId },
  });

  return "sent";
}

export async function sendCycleSunlightRequests(
  db: D1Database,
  binding: EmailSendBinding,
  cycleId: string,
  options: { contactDetails?: string; fromEmail?: string } = {},
): Promise<{ failed: number; sent: number; total: number }> {
  const requests = await listPreparedSunlightRequests(db, cycleId);
  let failed = 0;
  let sent = 0;

  await updateCycleStatus(db, cycleId, "sending");

  for (const request of requests) {
    const status = await sendPreparedSunlightRequest(db, binding, request, options);
    if (status === "sent") {
      sent += 1;
    } else {
      failed += 1;
    }
  }

  await updateCycleStatus(db, cycleId, failed > 0 ? "previewed" : "sent");
  return { failed, sent, total: requests.length };
}

export async function retryFailedCycleEmails(
  db: D1Database,
  binding: EmailSendBinding,
  cycleId: string,
  options: { contactDetails?: string; fromEmail?: string } = {},
): Promise<{ failed: number; sent: number; total: number }> {
  const requests = filterFailedPreparedRequests(await listPreparedSunlightRequests(db, cycleId));
  let failed = 0;
  let sent = 0;

  await updateCycleStatus(db, cycleId, "sending");

  for (const request of requests) {
    const status = await sendPreparedSunlightRequest(db, binding, request, options);
    if (status === "sent") {
      sent += 1;
    } else {
      failed += 1;
    }
  }

  await updateCycleStatus(db, cycleId, failed > 0 ? "previewed" : "sent");
  return { failed, sent, total: requests.length };
}

async function markOutboundFailed(
  db: D1Database,
  emailId: string,
  sunlightRequestId: string,
  error: unknown,
): Promise<void> {
  const message = error instanceof Error ? error.message : String(error);
  await db
    .prepare(
      `
        UPDATE sunlight_outbound_emails
        SET status = 'failed',
            error_message = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(message, emailId)
    .run();

  await updateSunlightRequestStatus(db, sunlightRequestId, "failed");
  await insertAuditEvent(db, {
    entityId: sunlightRequestId,
    eventType: "sunlight_request.email_failed",
    metadata: { error_message: message, outbound_email_id: emailId },
  });
}

async function updateSunlightRequestStatus(
  db: D1Database,
  sunlightRequestId: string,
  status: "queued" | "failed",
): Promise<void> {
  await db
    .prepare(
      `
        UPDATE sunlight_requests
        SET status = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(status, sunlightRequestId)
    .run();
}

async function updateCycleStatus(
  db: D1Database,
  cycleId: string,
  status: "sending" | "sent" | "previewed",
): Promise<void> {
  await db
    .prepare(
      `
        UPDATE sunlight_request_cycles
        SET status = ?,
            sent_at = CASE WHEN ? = 'sent' THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now') ELSE sent_at END,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
      `,
    )
    .bind(status, status, cycleId)
    .run();
}

async function insertAuditEvent(
  db: D1Database,
  input: {
    entityId: string;
    eventType: string;
    metadata: Record<string, unknown>;
  },
): Promise<void> {
  const id = `aud_${crypto.randomUUID().replaceAll("-", "")}`;
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
        ) VALUES (?, 'sunlight_request', ?, ?, 'system', 'admin_worker', ?)
      `,
    )
    .bind(id, input.entityId, input.eventType, JSON.stringify(input.metadata))
    .run();
}
