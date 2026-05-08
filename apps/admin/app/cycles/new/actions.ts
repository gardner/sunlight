"use server";

import { env } from "cloudflare:workers";
import { redirect } from "next/navigation";
import { createCycle } from "../../../lib/cycles";

export async function createCycleAction(formData: FormData) {
  const cycleMonth = String(formData.get("cycleMonth") ?? "");
  const cycleId = await createCycle((env as unknown as CloudflareEnv).DB, cycleMonth);
  redirect(`/cycles/${cycleId}`);
}
