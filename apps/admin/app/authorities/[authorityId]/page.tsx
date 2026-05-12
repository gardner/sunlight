import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { listContactCandidateGroups } from "../../../lib/authority-contact-candidates";
import { getAuthority } from "../../../lib/authorities";
import { listTemplates } from "../../../lib/templates";
import {
  acceptPrimaryContactCandidateAction,
  acceptSecondaryContactCandidateAction,
  assignTemplateAction,
  createOneOffRequestAction,
  markAuthorityContactInvalidAction,
  rejectContactCandidateAction,
  verifyContactAction,
} from "./actions";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";

interface AuthorityDetailPageProps {
  params: Promise<{ authorityId: string }>;
}

export default async function AuthorityDetailPage({ params }: AuthorityDetailPageProps) {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const { authorityId } = await params;
  const db = (env as unknown as CloudflareEnv).DB;
  const authority = await getAuthority(db, authorityId);

  if (!authority) {
    notFound();
  }

  const templates = await listTemplates(db);
  const candidateGroups = await listContactCandidateGroups(db, authority.id);

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
        <div className="flex gap-2">
          <a className="button secondary" href={`/authorities/${authority.id}/edit`}>
            Edit Authority
          </a>
          <a className="button" href="/authorities">
            Authorities
          </a>
        </div>
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
          <form action={markAuthorityContactInvalidAction} className="stack">
            <input type="hidden" name="authorityId" value={authority.id} />
            <button className="button secondary" type="submit">
              Mark contact invalid
            </button>
          </form>
          <form action={createOneOffRequestAction} className="stack">
            <input type="hidden" name="authorityId" value={authority.id} />
            <button className="button" type="submit">
              Create one-off request
            </button>
          </form>
        </section>

        <section className="panel">
          <h2>Contact candidates</h2>
          <div className="candidateList">
            {candidateGroups.map((group) => (
              <article className="candidateGroup" key={group.normalized_email}>
                <div className="candidateHeader">
                  <div>
                    <h3>{group.normalized_email}</h3>
                    <p>
                      {group.confidence}% confidence from{" "}
                      {group.candidate_count.toLocaleString()} evidence{" "}
                      {group.candidate_count === 1 ? "row" : "rows"}
                    </p>
                  </div>
                  <span className="pill">{group.status}</span>
                </div>
                <div className="actions">
                  <CandidateActionForm
                    action={acceptPrimaryContactCandidateAction}
                    authorityId={authority.id}
                    email={group.normalized_email}
                    label="Accept primary"
                  />
                  <CandidateActionForm
                    action={acceptSecondaryContactCandidateAction}
                    authorityId={authority.id}
                    email={group.normalized_email}
                    label="Accept secondary"
                    secondary
                  />
                  <CandidateActionForm
                    action={rejectContactCandidateAction}
                    authorityId={authority.id}
                    email={group.normalized_email}
                    label="Reject"
                    secondary
                  />
                </div>
                <div className="candidateEvidenceList">
                  {group.evidence.map((evidence) => (
                    <div className="candidateEvidence" key={evidence.id}>
                      <div className="candidateEvidenceMeta">
                        <strong>{evidence.confidence}%</strong>
                        <span>{evidence.discovery_method}</span>
                        <span>{evidence.status}</span>
                      </div>
                      <a href={evidence.source_url}>{evidence.source_page_title ?? evidence.source_url}</a>
                      <p>{evidence.source_snippet ?? evidence.confidence_reason}</p>
                      <small>{evidence.confidence_reason}</small>
                    </div>
                  ))}
                </div>
              </article>
            ))}
            {candidateGroups.length === 0 ? <p>No scraped candidates yet.</p> : null}
          </div>
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

function CandidateActionForm({
  action,
  authorityId,
  email,
  label,
  secondary = false,
}: {
  action: (formData: FormData) => Promise<void>;
  authorityId: string;
  email: string;
  label: string;
  secondary?: boolean;
}) {
  return (
    <form action={action}>
      <input type="hidden" name="authorityId" value={authorityId} />
      <input type="hidden" name="email" value={email} />
      <button className={secondary ? "button secondary" : "button primary"} type="submit">
        {label}
      </button>
    </form>
  );
}
