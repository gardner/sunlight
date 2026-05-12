"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { buildCreateTemplateInput, createTemplate } from "../../../lib/templates";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";

export async function createTemplateAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const input = buildCreateTemplateInput({
    bodyTemplate: String(formData.get("bodyTemplate") ?? ""),
    name: String(formData.get("name") ?? ""),
    subjectTemplate: String(formData.get("subjectTemplate") ?? ""),
  });

  await createTemplate((env as unknown as CloudflareEnv).DB, input);
  redirect("/templates");
}
