"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
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
