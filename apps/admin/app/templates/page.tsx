import { env } from "cloudflare:workers";
import { listTemplates } from "../../lib/templates";

export default async function TemplatesPage() {
  const templates = await listTemplates((env as unknown as CloudflareEnv).DB);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Templates</h1>
        </div>
        <a className="button" href="/templates/new">
          New template
        </a>
      </header>

      <div className="table">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Subject</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((template) => (
              <tr key={template.id}>
                <td>{template.name}</td>
                <td>{template.status}</td>
                <td>{template.subject_template}</td>
                <td>{template.updated_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
