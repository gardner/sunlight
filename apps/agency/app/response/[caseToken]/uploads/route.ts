import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import {
  buildUploadRequest,
  createUpload,
  getSunlightRequestByToken,
  type R2PresignConfig,
} from "../../../../lib/response-intake";

interface UploadRouteContext {
  params: Promise<{ caseToken: string }> | { caseToken: string };
}

export async function POST(request: Request, context: UploadRouteContext) {
  const { caseToken } = await context.params;
  const cloudflareEnv = env as unknown as CloudflareEnv;
  const sunlightRequest = await getSunlightRequestByToken(cloudflareEnv.DB, caseToken);

  if (!sunlightRequest) {
    notFound();
  }

  const presignConfig = getR2PresignConfig(cloudflareEnv);
  if (!presignConfig) {
    return new Response("R2 presigned upload credentials are not configured", {
      status: 503,
    });
  }

  try {
    const upload = buildUploadRequest((await request.json()) as Record<string, unknown>);
    const created = await createUpload(
      cloudflareEnv.DB,
      sunlightRequest,
      upload,
      presignConfig,
    );
    return Response.json(created);
  } catch (error) {
    return new Response(error instanceof Error ? error.message : String(error), {
      status: 400,
    });
  }
}

function getR2PresignConfig(env: CloudflareEnv): R2PresignConfig | null {
  if (
    !env.R2_ACCESS_KEY_ID ||
    !env.R2_ACCOUNT_ID ||
    !env.R2_BUCKET_NAME ||
    !env.R2_SECRET_ACCESS_KEY
  ) {
    return null;
  }

  return {
    accessKeyId: env.R2_ACCESS_KEY_ID,
    accountId: env.R2_ACCOUNT_ID,
    bucketName: env.R2_BUCKET_NAME,
    expiresSeconds: Number(env.R2_PRESIGN_EXPIRES_SECONDS || 900),
    secretAccessKey: env.R2_SECRET_ACCESS_KEY,
  };
}
