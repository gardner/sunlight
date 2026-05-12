"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { buildUpdateAuthorityInput, updateAuthority } from "../../../../lib/authorities";
import { headers } from "next/headers";
import { requireAdmin } from "../../../../lib/access";

export async function updateAuthorityAction(formData: FormData) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const authorityId = String(formData.get("authorityId") ?? "");
  
  const input = buildUpdateAuthorityInput({
    name: String(formData.get("name") ?? ""),
    slug: String(formData.get("slug") ?? ""),
    legal_regime: String(formData.get("legal_regime") ?? "OIA"),
    status: String(formData.get("status") ?? "active"),
    default_cadence: String(formData.get("default_cadence") ?? "monthly"),
    proactive_release_url: String(formData.get("proactive_release_url") ?? ""),
    notes: String(formData.get("notes") ?? ""),
  });

  await updateAuthority(cloudflareEnv.DB, authorityId, input);
  redirect(`/authorities/${authorityId}`);
}
