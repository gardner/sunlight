import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";
import { SafeHtml } from "../../../components/SafeHtml";
import { getRequestDetail, listRequestResponses, listRequestInboundEmails, listRequestOutboundEmails, listRequestMitigations, listRequestUploads, listRequestInboundAttachments } from "../../../lib/responses";
import { sendMitigationAction } from "./actions";

export default async function RequestDetailPage({ params }: { params: Promise<{ requestId: string }> }) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  
  const { requestId } = await params;
  const request = await getRequestDetail(cloudflareEnv.DB, requestId);

  if (!request) {
    notFound();
  }

  const responses = await listRequestResponses(cloudflareEnv.DB, requestId);
  const inboundEmails = await listRequestInboundEmails(cloudflareEnv.DB, requestId);
  const outboundEmails = await listRequestOutboundEmails(cloudflareEnv.DB, requestId);
  const mitigations = await listRequestMitigations(cloudflareEnv.DB, requestId);
  const uploads = await listRequestUploads(cloudflareEnv.DB, requestId);
  const attachments = await listRequestInboundAttachments(cloudflareEnv.DB, requestId);

  const thread = [
    ...inboundEmails.map(e => ({ ...e, type: "inbound" as const, date: new Date(e.received_at) })),
    ...outboundEmails.map(e => ({ ...e, type: "outbound" as const, date: new Date(e.sent_at || e.created_at) }))
  ].sort((a, b) => b.date.getTime() - a.date.getTime()); // newest first

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Request to {request.authority_name}</p>
          <h1>{request.id}</h1>
        </div>
        <a className="button" href="/requests">
          Back to Requests
        </a>
      </header>

      <div className="detailGrid">
        <section className="panel">
          <h2>Request Details</h2>
          <dl className="facts">
            <div>
              <dt>Status</dt>
              <dd>{request.status}</dd>
            </div>
            <div>
              <dt>Expected Due Date</dt>
              <dd>{request.expected_due_at}</dd>
            </div>
            <div>
              <dt>Response Portal</dt>
              <dd><a href={request.response_url} target="_blank" rel="noreferrer">Open Portal</a></dd>
            </div>
          </dl>
        </section>

        {mitigations.length > 0 && (
          <section className="panel">
            <h2>Refusal Mitigations</h2>
            <div className="stack">
              {mitigations.map((mit) => (
                <div key={mit.id} className="border p-4 rounded-md border-error text-on-surface">
                  <h3 className="text-error font-bold mb-2">Detected Refusal: {mit.refusal_reason}</h3>
                  <p className="mb-4 text-sm text-on-surface-variant">
                    Status: <span className="pill">{mit.status}</span>
                  </p>
                  
                  {mit.status === 'drafted' ? (
                    <form action={sendMitigationAction} className="stack">
                      <input type="hidden" name="mitigationId" value={mit.id} />
                      <input type="hidden" name="requestId" value={request.id} />
                      <label>
                        Drafted Counter-Argument (Based on Ombudsman Guidelines)
                        <textarea 
                          name="responseBody" 
                          rows={6} 
                          defaultValue={mit.drafted_response} 
                          className="w-full font-mono text-sm p-2"
                        />
                      </label>
                      <button className="button" type="submit">
                        Approve & Send Mitigation
                      </button>
                    </form>
                  ) : (
                    <div>
                      <p><strong>Sent Mitigation:</strong></p>
                      <pre className="whitespace-pre-wrap font-mono text-sm bg-surface-container p-2">{mit.drafted_response}</pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {(uploads.length > 0 || attachments.length > 0) && (
          <section className="panel">
            <h2>Received Files</h2>
            <div className="candidateList">
              {uploads.map((upload) => (
                <article key={upload.id} className="candidateGroup flex-col !items-start">
                  <div className="candidateHeader w-full">
                    <div>
                      <h3>{upload.original_filename}</h3>
                      <p>Size: {formatBytes(upload.size_bytes)} | Uploaded via Portal</p>
                    </div>
                    <a href={`/requests/${request.id}/files/upload/${upload.id}`} target="_blank" rel="noreferrer" className="button secondary shrink-0">
                      Download
                    </a>
                  </div>
                  {upload.content_type?.startsWith("image/") && (
                    <div className="mt-4 bg-surface-container-low p-2 rounded border">
                      <img src={`/requests/${request.id}/files/upload/${upload.id}`} alt={upload.original_filename} className="max-w-full md:max-w-[400px] max-h-[400px] object-contain" loading="lazy" />
                    </div>
                  )}
                </article>
              ))}
              {attachments.map((attachment) => (
                <article key={attachment.id} className="candidateGroup flex-col !items-start">
                  <div className="candidateHeader w-full">
                    <div>
                      <h3>{attachment.filename}</h3>
                      <p>Size: {formatBytes(attachment.size_bytes)} | Attached to Email</p>
                    </div>
                    <a href={`/requests/${request.id}/files/attachment/${attachment.id}`} target="_blank" rel="noreferrer" className="button secondary shrink-0">
                      Download
                    </a>
                  </div>
                  {attachment.content_type?.startsWith("image/") && (
                    <div className="mt-4 bg-surface-container-low p-2 rounded border">
                      <img src={`/requests/${request.id}/files/attachment/${attachment.id}`} alt={attachment.filename} className="max-w-full md:max-w-[400px] max-h-[400px] object-contain" loading="lazy" />
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        <section className="panel">
          <h2>Email Thread</h2>
          {thread.length === 0 ? (
            <p>No emails in thread yet.</p>
          ) : (
            <div className="candidateList space-y-6">
              {thread.map((msg) => (
                <article key={msg.id} className="candidateGroup">
                  <div className="candidateHeader bg-surface-container p-4 -m-4 mb-4 rounded-t-lg">
                    <div>
                      <h3>{msg.subject}</h3>
                      <p className="text-sm">
                        {msg.type === "outbound" ? (
                          <><strong>From:</strong> {msg.from_email} <strong>To:</strong> {msg.to_emails_json}</>
                        ) : (
                          <><strong>From:</strong> {msg.from_email} <strong>To:</strong> Sunlight</>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {msg.date.toLocaleString()} | {msg.type === "outbound" ? "Outbound" : "Inbound"}
                      </p>
                    </div>
                  </div>
                  <div className="prose prose-sm max-w-none text-on-surface">
                    {msg.body_html ? (
                      <SafeHtml html={msg.body_html} />
                    ) : (
                      <pre className="whitespace-pre-wrap font-sans bg-transparent p-0 m-0 text-sm">
                        {msg.body_text ?? "No body text available."}
                      </pre>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function formatBytes(bytes: number) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
