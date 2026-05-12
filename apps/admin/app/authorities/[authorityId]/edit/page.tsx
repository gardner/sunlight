import { env } from "cloudflare:workers";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { requireAdmin } from "../../../../lib/access";
import { getAuthority } from "../../../../lib/authorities";
import { updateAuthorityAction } from "./actions";

export default async function EditAuthorityPage({
  params,
}: {
  params: Promise<{ authorityId: string }>;
}) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const { authorityId } = await params;
  const authority = await getAuthority(cloudflareEnv.DB, authorityId);

  if (!authority) {
    notFound();
  }

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Authorities</p>
          <h1>Edit {authority.name}</h1>
        </div>
        <a className="button secondary" href={`/authorities/${authority.id}`}>
          Cancel
        </a>
      </header>

      <form action={updateAuthorityAction} className="panel stack">
        <input type="hidden" name="authorityId" value={authority.id} />
        
        <label>
          Name
          <input name="name" required defaultValue={authority.name} />
        </label>

        <label>
          Slug
          <input name="slug" required defaultValue={authority.slug} />
        </label>

        <label>
          Legal Regime
          <select name="legal_regime" defaultValue={authority.legal_regime}>
            <option value="OIA">OIA</option>
            <option value="LGOIMA">LGOIMA</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label>
          Status
          <select name="status" defaultValue={authority.status}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>

        <label>
          Default Cadence
          <select name="default_cadence" defaultValue={authority.default_cadence}>
            <option value="monthly">Monthly</option>
            <option value="proactive_scraper">Proactive Scraper</option>
            <option value="quarterly">Quarterly</option>
            <option value="yearly">Yearly</option>
            <option value="never">Never</option>
          </select>
        </label>

        <label>
          Proactive Release URL
          <input
            name="proactive_release_url"
            type="url"
            defaultValue={authority.proactive_release_url ?? ""}
            placeholder="https://example.govt.nz/oia-responses"
          />
        </label>

        <label>
          Notes
          <textarea
            name="notes"
            rows={5}
            defaultValue={authority.notes ?? ""}
          />
        </label>

        <button className="button" type="submit">
          Save changes
        </button>
      </form>
    </main>
  );
}
