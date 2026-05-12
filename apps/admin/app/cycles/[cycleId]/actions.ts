"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { approveCycle, getCycle, prepareCycleRequests, canSendCycle } from "../../../lib/cycles";
import {
  retryFailedCycleEmails,
  sendCycleSunlightRequests,
} from "../../../lib/outbound-email";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";

export async function prepareCycleAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const cycleId = String(formData.get("cycleId") ?? "");
  await prepareCycleRequests((env as unknown as CloudflareEnv).DB, cycleId);
  redirect(`/cycles/${cycleId}`);
}

export async function approveCycleAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const cycleId = String(formData.get("cycleId") ?? "");
  await approveCycle((env as unknown as CloudflareEnv).DB, cycleId);
  redirect(`/cycles/${cycleId}`);
}

export async function sendCycleAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const cycleId = String(formData.get("cycleId") ?? "");
  const cycle = await getCycle(cloudflareEnv.DB, cycleId);
  if (!cycle || !canSendCycle(cycle.status)) {
    throw new Error("Only approved request cycles can be sent");
  }

  await sendCycleSunlightRequests(cloudflareEnv.DB, cloudflareEnv.EMAIL, cycleId, {
    contactDetails: cloudflareEnv.SUNLIGHT_CONTACT_DETAILS,
    fromEmail: cloudflareEnv.SUNLIGHT_FROM_EMAIL,
  });
  redirect(`/cycles/${cycleId}`);
}

export async function retryFailedEmailsAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const cycleId = String(formData.get("cycleId") ?? "");

  await retryFailedCycleEmails(cloudflareEnv.DB, cloudflareEnv.EMAIL, cycleId, {
    contactDetails: cloudflareEnv.SUNLIGHT_CONTACT_DETAILS,
    fromEmail: cloudflareEnv.SUNLIGHT_FROM_EMAIL,
  });
  redirect(`/cycles/${cycleId}`);
}
