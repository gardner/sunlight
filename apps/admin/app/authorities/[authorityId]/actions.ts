"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import {
  acceptContactCandidate,
  markAuthorityContactInvalid,
  rejectContactCandidate,
} from "../../../lib/authority-contact-candidates";
import { assignAuthorityTemplate, verifyAuthorityContact } from "../../../lib/authorities";
import { createCycle, prepareCycleRequests } from "../../../lib/cycles";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";

export async function createOneOffRequestAction(formData: FormData) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  const db = cloudflareEnv.DB;
  await requireAdmin(await headers(), db, cloudflareEnv);
  
  const authorityId = String(formData.get("authorityId") ?? "");
  const today = new Date();
  const cycleMonth = `${today.getUTCFullYear()}-${String(today.getUTCMonth() + 1).padStart(2, "0")}`;
  
  const cycleId = await createCycle(db, cycleMonth);
  await prepareCycleRequests(db, cycleId, authorityId);
  
  redirect(`/cycles/${cycleId}`);
}

export async function verifyContactAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const authorityId = String(formData.get("authorityId") ?? "");
  const email = String(formData.get("email") ?? "");

  await verifyAuthorityContact((env as unknown as CloudflareEnv).DB, {
    authorityId,
    email,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function assignTemplateAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const authorityId = String(formData.get("authorityId") ?? "");
  const templateId = String(formData.get("templateId") ?? "");

  await assignAuthorityTemplate((env as unknown as CloudflareEnv).DB, {
    authorityId,
    templateId,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function acceptPrimaryContactCandidateAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const authorityId = String(formData.get("authorityId") ?? "");
  const email = String(formData.get("email") ?? "");

  await acceptContactCandidate((env as unknown as CloudflareEnv).DB, {
    authorityId,
    decision: "primary",
    email,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function acceptSecondaryContactCandidateAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const authorityId = String(formData.get("authorityId") ?? "");
  const email = String(formData.get("email") ?? "");

  await acceptContactCandidate((env as unknown as CloudflareEnv).DB, {
    authorityId,
    decision: "secondary",
    email,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function rejectContactCandidateAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const authorityId = String(formData.get("authorityId") ?? "");
  const email = String(formData.get("email") ?? "");

  await rejectContactCandidate((env as unknown as CloudflareEnv).DB, {
    authorityId,
    email,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function markAuthorityContactInvalidAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const authorityId = String(formData.get("authorityId") ?? "");

  await markAuthorityContactInvalid((env as unknown as CloudflareEnv).DB, {
    authorityId,
  });

  redirect(`/authorities/${authorityId}`);
}
