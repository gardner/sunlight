"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { buildUpdateTemplateInput, updateTemplate, deleteTemplate } from "../../../lib/templates";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";

export async function updateTemplateAction(formData: FormData) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const templateId = String(formData.get("templateId") ?? "");
  
  const input = buildUpdateTemplateInput({
    bodyTemplate: String(formData.get("bodyTemplate") ?? ""),
    name: String(formData.get("name") ?? ""),
    status: String(formData.get("status") ?? "active") as "active" | "inactive",
    subjectTemplate: String(formData.get("subjectTemplate") ?? ""),
  });

  await updateTemplate(cloudflareEnv.DB, templateId, input);
  redirect("/templates");
}

export async function deleteTemplateAction(formData: FormData) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const templateId = String(formData.get("templateId") ?? "");
  
  await deleteTemplate(cloudflareEnv.DB, templateId);
  redirect("/templates");
}
