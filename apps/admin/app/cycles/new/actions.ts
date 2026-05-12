"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { createCycle } from "../../../lib/cycles";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";

export async function createCycleAction(formData: FormData) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const cycleMonth = String(formData.get("cycleMonth") ?? "");
  const cycleId = await createCycle((env as unknown as CloudflareEnv).DB, cycleMonth);
  redirect(`/cycles/${cycleId}`);
}
