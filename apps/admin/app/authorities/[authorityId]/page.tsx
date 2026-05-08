import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { getAuthority } from "../../../lib/authorities";
import { listTemplates } from "../../../lib/templates";
import { assignTemplateAction, verifyContactAction } from "./actions";

interface AuthorityDetailPageProps {
  params: Promise<{ authorityId: string }>;
}

export default async function AuthorityDetailPage({ params }: AuthorityDetailPageProps) {
  const { authorityId } = await params;
  const db = (env as unknown as CloudflareEnv).DB;
  const authority = await getAuthority(db, authorityId);

  if (!authority) {
    notFound();
  }

  const templates = await listTemplates(db);

  const metadata = JSON.parse(authority.source_metadata_json) as {
    disclosure_log?: string | null;
    home_page?: string | null;
    tags?: string[];
  };

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Authority</p>
          <h1>{authority.name}</h1>
        </div>
        <a className="button" href="/authorities">
          Authorities
        </a>
      </header>

      <div className="detailGrid">
        <section className="panel">
          <h2>Contact</h2>
          <dl className="facts">
            <div>
              <dt>Primary request email</dt>
              <dd>{authority.primary_request_email ?? "Missing"}</dd>
            </div>
            <div>
              <dt>Contact status</dt>
              <dd>{authority.contact_status}</dd>
            </div>
            <div>
              <dt>Directory status</dt>
              <dd>{authority.status}</dd>
            </div>
            <div>
              <dt>Legal regime</dt>
              <dd>{authority.legal_regime}</dd>
            </div>
          </dl>
          <form action={verifyContactAction} className="stack">
            <input type="hidden" name="authorityId" value={authority.id} />
            <label>
              Verify request email
              <input
                name="email"
                defaultValue={authority.primary_request_email ?? ""}
                placeholder="oia@example.govt.nz"
                type="email"
              />
            </label>
            <button className="button" type="submit">
              Mark verified
            </button>
          </form>
          <form action={assignTemplateAction} className="stack">
            <input type="hidden" name="authorityId" value={authority.id} />
            <label>
              Default template
              <select name="templateId" defaultValue={authority.default_template_id ?? ""}>
                <option value="">Choose template</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
            </label>
            <button className="button" type="submit">
              Save template
            </button>
          </form>
        </section>

        <aside className="panel">
          <h2>Source</h2>
          <dl className="facts">
            <div>
              <dt>Source</dt>
              <dd>{authority.source ?? "Manual"}</dd>
            </div>
            <div>
              <dt>Source id</dt>
              <dd>{authority.source_id ?? ""}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{authority.source_updated_at ?? ""}</dd>
            </div>
            <div>
              <dt>Home page</dt>
              <dd>{metadata.home_page ?? ""}</dd>
            </div>
            <div>
              <dt>Disclosure log</dt>
              <dd>{metadata.disclosure_log ?? ""}</dd>
            </div>
            <div>
              <dt>Tags</dt>
              <dd>{metadata.tags?.join(", ") ?? ""}</dd>
            </div>
          </dl>
        </aside>
      </div>
    </main>
  );
}
