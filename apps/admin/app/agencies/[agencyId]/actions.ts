"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { assignAgencyTemplate, verifyAgencyContact } from "../../../lib/agencies";

export async function verifyContactAction(formData: FormData) {
  const agencyId = String(formData.get("agencyId") ?? "");
  const email = String(formData.get("email") ?? "");

  await verifyAgencyContact((env as unknown as CloudflareEnv).DB, {
    agencyId,
    email,
  });

  redirect(`/agencies/${agencyId}`);
}

export async function assignTemplateAction(formData: FormData) {
  const agencyId = String(formData.get("agencyId") ?? "");
  const templateId = String(formData.get("templateId") ?? "");

  await assignAgencyTemplate((env as unknown as CloudflareEnv).DB, {
    agencyId,
    templateId,
  });

  redirect(`/agencies/${agencyId}`);
}
