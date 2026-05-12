import { env } from "cloudflare:workers";
import { headers } from "next/headers";
import { requireAdmin } from "../../lib/access";
import { listInboxEmails } from "../../lib/responses";
import { resolveInboxItemAction, replyToInboxItemAction } from "./actions";

export default async function InboxPage() {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const inboxItems = await listInboxEmails(cloudflareEnv.DB);

  return (
    <main className="shell flex flex-col h-full overflow-hidden">
      <header className="pageHeader shrink-0">
        <div>
          <p className="eyebrow">Operations</p>
          <h1>Human Review Inbox</h1>
        </div>
      </header>

      {inboxItems.length === 0 ? (
        <section className="panel">
          <p>Inbox is empty! No emails currently require human review.</p>
        </section>
      ) : (
        <div className="grid gap-6 overflow-y-auto pb-8">
          {inboxItems.map((item) => (
            <section key={item.id} className="panel">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-xl font-bold">{item.authority_name ?? "Unknown Authority"}</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    <strong>From:</strong> {item.from_email} | <strong>Subject:</strong> {item.subject}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    <strong>Received:</strong> {new Date(item.received_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2">
                  <a href={`/requests/${item.sunlight_request_id}`} className="button secondary">
                    View Full Request
                  </a>
                  <form action={resolveInboxItemAction}>
                    <input type="hidden" name="emailId" value={item.id} />
                    <button type="submit" className="button">
                      Mark as Resolved
                    </button>
                  </form>
                </div>
              </div>
              
              <div className="bg-primary/10 border border-primary/20 p-3 rounded-md mb-4 text-sm font-medium">
                <span className="font-bold">AI Triage Reason:</span> {item.ai_triage_reason}
              </div>

              <div className="bg-surface-container-low p-4 rounded-md border overflow-auto max-h-96 text-sm whitespace-pre-wrap mb-4">
                {item.body_text ?? "No text body available. View full request to see raw attachments/HTML."}
              </div>

              <form action={replyToInboxItemAction} className="stack border-t pt-4">
                <input type="hidden" name="emailId" value={item.id} />
                <label>
                  <span className="font-bold text-sm block mb-2">Reply to Authority</span>
                  <textarea 
                    name="bodyText" 
                    required 
                    rows={4} 
                    className="w-full font-mono text-sm p-2 border rounded"
                    placeholder="Type your reply here..."
                  />
                </label>
                <div className="flex justify-end">
                  <button type="submit" className="button primary">
                    Send Reply
                  </button>
                </div>
              </form>
            </section>
          ))}
        </div>
      )}
    </main>
  );
}