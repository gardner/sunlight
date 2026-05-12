import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { completeUpload, getSunlightRequestByToken, getR2PresignConfig } from "../../../../../../lib/response-intake";

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

export async function POST(request: Request, context: CompleteUploadRouteContext) {
  const { caseToken, uploadId } = await context.params;
  const cloudflareEnv = env as unknown as CloudflareEnv;
  const sunlightRequest = await getSunlightRequestByToken(cloudflareEnv.DB, caseToken);

  if (!sunlightRequest) {
    notFound();
  }

  let body: any = null;
  const contentType = request.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    body = await request.json();
  }

  const config = getR2PresignConfig(cloudflareEnv);
  if (config && body?.multipartUploadId) {
    (config as any).multipartUploadId = body.multipartUploadId;
  }

  try {
    await completeUpload(cloudflareEnv.DB, cloudflareEnv.ARTIFACTS, sunlightRequest, uploadId, body?.parts, config);
    return Response.json({ ok: true });
  } catch (error) {
    return new Response(error instanceof Error ? error.message : String(error), {
      status: 400,
    });
  }
}
