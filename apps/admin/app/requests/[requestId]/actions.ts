"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { updateMitigationStatus } from "../../../lib/responses";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";

export async function sendMitigationAction(formData: FormData) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  
  const mitigationId = String(formData.get("mitigationId") ?? "");
  const requestId = String(formData.get("requestId") ?? "");
  const responseBody = String(formData.get("responseBody") ?? "");

  await updateMitigationStatus(cloudflareEnv.DB, mitigationId, "sent", responseBody);

  // In a real implementation, we would queue this outgoing email to the Email Sending binding here.
  // We simulate it being sent.
  
  redirect(`/requests/${requestId}`);
}
