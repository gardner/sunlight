import { env } from "cloudflare:workers";
import { listTemplates } from "../../lib/templates";
import { headers } from "next/headers";
import { requireAdmin } from "../../lib/access";

export default async function TemplatesPage() {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
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
                <td>
                  <a href={`/templates/${template.id}`} className="text-primary hover:underline font-medium">
                    {template.name}
                  </a>
                </td>
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
