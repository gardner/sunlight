import { env } from "cloudflare:workers";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";
import { createTemplateAction } from "./actions";

export default async function NewTemplatePage() {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Templates</p>
          <h1>New template</h1>
        </div>
        <a className="button" href="/templates">
          Templates
        </a>
      </header>

      <form action={createTemplateAction} className="panel stack">
        <label>
          Name
          <input name="name" required />
        </label>
        <label>
          Subject
          <input
            name="subjectTemplate"
            required
            defaultValue="OIA/LGOIMA disclosure request for {authority_name} - {cycle_month}"
          />
        </label>
        <label>
          Body
          <textarea
            name="bodyTemplate"
            required
            rows={12}
            defaultValue={`Kia ora {authority_name},

Sunlight is requesting copies of OIA/LGOIMA requests received by your authority for {covered_date_range}, and the corresponding responses.

Please reply to {reply_email}. If attachments are too large for email, use {response_url}.

{sunlight_contact_details}`}
          />
        </label>
        <button className="button" type="submit">
          Create template
        </button>
      </form>
    </main>
  );
}
