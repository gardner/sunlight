import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { completeUpload, getSunlightRequestByToken } from "../../../../../../lib/response-intake";

interface CompleteUploadRouteContext {
  params:
    | Promise<{
        caseToken: string;
        uploadId: string;
      }>
    | {
        caseToken: string;
        uploadId: string;
      };
}

export async function POST(_request: Request, context: CompleteUploadRouteContext) {
  const { caseToken, uploadId } = await context.params;
  const cloudflareEnv = env as unknown as CloudflareEnv;
  const sunlightRequest = await getSunlightRequestByToken(cloudflareEnv.DB, caseToken);

  if (!sunlightRequest) {
    notFound();
  }

  try {
    await completeUpload(cloudflareEnv.DB, cloudflareEnv.ARTIFACTS, sunlightRequest, uploadId);
    return Response.json({ ok: true });
  } catch (error) {
    return new Response(error instanceof Error ? error.message : String(error), {
      status: 400,
    });
  }
}
