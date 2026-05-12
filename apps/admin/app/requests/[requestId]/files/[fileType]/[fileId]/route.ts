import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { requireAdmin } from "../../../../../../lib/access";
import { getUpload, getInboundAttachment } from "../../../../../../lib/responses";

interface FileRouteContext {
  params: Promise<{
    requestId: string;
    fileType: string;
    fileId: string;
  }>;
}

export async function GET(request: Request, context: FileRouteContext) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  // Authenticate the admin using the same token helper
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  
  const { requestId, fileType, fileId } = await context.params;

  let r2Key: string | null = null;
  let filename: string = "download";
  let contentType: string = "application/octet-stream";

  if (fileType === "upload") {
    const upload = await getUpload(cloudflareEnv.DB, fileId, requestId);
    if (!upload) return notFound();
    r2Key = upload.r2_key;
    filename = upload.original_filename;
    contentType = upload.content_type || contentType;
  } else if (fileType === "attachment") {
    const attachment = await getInboundAttachment(cloudflareEnv.DB, fileId, requestId);
    if (!attachment) return notFound();
    r2Key = attachment.r2_key;
    filename = attachment.filename;
    contentType = attachment.content_type || contentType;
  } else {
    return notFound();
  }

  const object = await cloudflareEnv.ARTIFACTS.get(r2Key);
  
  if (!object || !object.body) {
    return new Response("File not found in storage", { status: 404 });
  }

  const resHeaders = new Headers();
  object.writeHttpMetadata(resHeaders as any);
  resHeaders.set("etag", object.httpEtag);
  // Ensure it forces a download (or opens inline for safe types, but for OIA attachments it's safer to download or let browser decide)
  // Let's just set the correct content type and an inline disposition so PDFs can be viewed in browser
  resHeaders.set("Content-Disposition", `inline; filename="${encodeURIComponent(filename)}"`);
  resHeaders.set("Content-Type", contentType);

  return new Response(object.body as any, {
    headers: resHeaders,
  });
}
