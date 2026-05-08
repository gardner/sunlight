import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { getAgency } from "../../../lib/agencies";
import { listTemplates } from "../../../lib/templates";
import { assignTemplateAction, verifyContactAction } from "./actions";

interface AgencyDetailPageProps {
  params: Promise<{ agencyId: string }>;
}

export default async function AgencyDetailPage({ params }: AgencyDetailPageProps) {
  const { agencyId } = await params;
  const db = (env as unknown as CloudflareEnv).DB;
  const agency = await getAgency(db, agencyId);

  if (!agency) {
    notFound();
  }

  const templates = await listTemplates(db);

  const metadata = JSON.parse(agency.source_metadata_json) as {
    disclosure_log?: string | null;
    home_page?: string | null;
    tags?: string[];
  };

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Agency</p>
          <h1>{agency.name}</h1>
        </div>
        <a className="button" href="/agencies">
          Agencies
        </a>
      </header>

      <div className="detailGrid">
        <section className="panel">
          <h2>Contact</h2>
          <dl className="facts">
            <div>
              <dt>Primary request email</dt>
              <dd>{agency.primary_request_email ?? "Missing"}</dd>
            </div>
            <div>
              <dt>Contact status</dt>
              <dd>{agency.contact_status}</dd>
            </div>
            <div>
              <dt>Directory status</dt>
              <dd>{agency.status}</dd>
            </div>
            <div>
              <dt>Legal regime</dt>
              <dd>{agency.legal_regime}</dd>
            </div>
          </dl>
          <form action={verifyContactAction} className="stack">
            <input type="hidden" name="agencyId" value={agency.id} />
            <label>
              Verify request email
              <input
                name="email"
                defaultValue={agency.primary_request_email ?? ""}
                placeholder="oia@example.govt.nz"
                type="email"
              />
            </label>
            <button className="button" type="submit">
              Mark verified
            </button>
          </form>
          <form action={assignTemplateAction} className="stack">
            <input type="hidden" name="agencyId" value={agency.id} />
            <label>
              Default template
              <select name="templateId" defaultValue={agency.default_template_id ?? ""}>
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
              <dd>{agency.source ?? "Manual"}</dd>
            </div>
            <div>
              <dt>Source id</dt>
              <dd>{agency.source_id ?? ""}</dd>
            </div>
            <div>
              <dt>Updated</dt>
              <dd>{agency.source_updated_at ?? ""}</dd>
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
