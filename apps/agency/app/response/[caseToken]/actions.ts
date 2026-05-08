"use server";

import { env } from "cloudflare:workers";
import { notFound, redirect } from "next/navigation";
import {
  buildResponseSubmission,
  getSunlightRequestByToken,
  submitSunlightResponse,
} from "../../../lib/response-intake";

export async function submitResponseAction(formData: FormData) {
  const caseToken = String(formData.get("caseToken") ?? "");
  const cloudflareEnv = env as unknown as CloudflareEnv;
  const request = await getSunlightRequestByToken(cloudflareEnv.DB, caseToken);

  if (!request) {
    notFound();
  }

  await submitSunlightResponse(
    cloudflareEnv.DB,
    request,
    buildResponseSubmission({
      agencyReference: formData.get("agencyReference"),
      category: formData.get("category"),
      notes: formData.get("notes"),
      submitterEmail: formData.get("submitterEmail"),
      submitterName: formData.get("submitterName"),
    }),
  );

  redirect(`/response/${caseToken}?submitted=1`);
}
