"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import {
  acceptContactCandidate,
  markAuthorityContactInvalid,
  rejectContactCandidate,
} from "../../../lib/authority-contact-candidates";
import { assignAuthorityTemplate, verifyAuthorityContact } from "../../../lib/authorities";

export async function verifyContactAction(formData: FormData) {
  const authorityId = String(formData.get("authorityId") ?? "");
  const email = String(formData.get("email") ?? "");

  await verifyAuthorityContact((env as unknown as CloudflareEnv).DB, {
    authorityId,
    email,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function assignTemplateAction(formData: FormData) {
  const authorityId = String(formData.get("authorityId") ?? "");
  const templateId = String(formData.get("templateId") ?? "");

  await assignAuthorityTemplate((env as unknown as CloudflareEnv).DB, {
    authorityId,
    templateId,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function acceptPrimaryContactCandidateAction(formData: FormData) {
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
  const authorityId = String(formData.get("authorityId") ?? "");
  const email = String(formData.get("email") ?? "");

  await rejectContactCandidate((env as unknown as CloudflareEnv).DB, {
    authorityId,
    email,
  });

  redirect(`/authorities/${authorityId}`);
}

export async function markAuthorityContactInvalidAction(formData: FormData) {
  const authorityId = String(formData.get("authorityId") ?? "");

  await markAuthorityContactInvalid((env as unknown as CloudflareEnv).DB, {
    authorityId,
  });

  redirect(`/authorities/${authorityId}`);
}
