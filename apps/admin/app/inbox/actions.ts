"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { headers } from "next/headers";
import { requireAdmin } from "../../lib/access";
import { resolveInboxEmail, getInboundEmail, saveOutboundEmail } from "../../lib/responses";

export async function resolveInboxItemAction(formData: FormData) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const emailId = String(formData.get("emailId") ?? "");
  await resolveInboxEmail(cloudflareEnv.DB, emailId);

  redirect("/inbox");
}

export async function replyToInboxItemAction(formData: FormData) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const emailId = String(formData.get("emailId") ?? "");
  const bodyText = String(formData.get("bodyText") ?? "");
  
  const inboundEmail = await getInboundEmail(cloudflareEnv.DB, emailId);
  if (!inboundEmail) {
    throw new Error("Email not found");
  }

  const toEmail = inboundEmail.from_email;
  const replyTo = (inboundEmail as any).reply_email ?? "requests@sunlight.nz";
  let subject = inboundEmail.subject;
  if (!subject.toLowerCase().startsWith("re:")) {
    subject = `Re: ${subject}`;
  }

  const emailHeaders: Record<string, string> = {
    "X-Sunlight-Request-ID": inboundEmail.sunlight_request_id,
  };
  
  if (inboundEmail.message_id_header) {
    emailHeaders["In-Reply-To"] = inboundEmail.message_id_header;
    emailHeaders["References"] = inboundEmail.message_id_header;
  }

  const generatedMessageId = `<${crypto.randomUUID()}@sunlight.nz>`;
  emailHeaders["Message-ID"] = generatedMessageId;

  // Send the email via Cloudflare Email binding
  const message = {
    from: "requests@sunlight.nz",
    to: [toEmail],
    replyTo: replyTo,
    subject: subject,
    text: bodyText,
    headers: emailHeaders
  };

  try {
    await cloudflareEnv.EMAIL.send(message);
  } catch (e) {
    console.error("Failed to send email via Cloudflare:", e);
    throw new Error(`Failed to send email: ${e instanceof Error ? e.message : String(e)}`);
  }

  // Save to outbound emails
  await saveOutboundEmail(
    cloudflareEnv.DB,
    inboundEmail.sunlight_request_id,
    "requests@sunlight.nz",
    [toEmail],
    subject,
    bodyText,
    generatedMessageId
  );

  // Auto-resolve since we replied
  await resolveInboxEmail(cloudflareEnv.DB, emailId);

  redirect("/inbox");
}