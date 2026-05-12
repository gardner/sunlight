import { env } from "cloudflare:workers";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { requireAdmin } from "../../../lib/access";
import { getTemplate } from "../../../lib/templates";
import { updateTemplateAction, deleteTemplateAction } from "./actions";

export default async function EditTemplatePage({
  params,
}: {
  params: Promise<{ templateId: string }>;
}) {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  const { templateId } = await params;
  const template = await getTemplate(cloudflareEnv.DB, templateId);

  if (!template) {
    notFound();
  }

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Templates</p>
          <h1>Edit {template.name}</h1>
        </div>
        <a className="button secondary" href="/templates">
          Back to templates
        </a>
      </header>

      <div className="grid gap-6">
        <form action={updateTemplateAction} className="panel stack">
          <input type="hidden" name="templateId" value={template.id} />
          <label>
            Name
            <input name="name" required defaultValue={template.name} />
          </label>
          <label>
            Status
            <select name="status" defaultValue={template.status}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
          <label>
            Subject
            <input
              name="subjectTemplate"
              required
              defaultValue={template.subject_template}
            />
          </label>
          <label>
            Body
            <textarea
              name="bodyTemplate"
              required
              rows={15}
              defaultValue={template.body_template}
              className="font-mono text-sm"
            />
          </label>
          <button className="button" type="submit">
            Save changes
          </button>
        </form>

        <form action={deleteTemplateAction} className="panel stack border-destructive/20">
          <input type="hidden" name="templateId" value={template.id} />
          <div>
            <h2 className="text-destructive">Delete Template</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Once you delete a template, there is no going back. Please be certain.
            </p>
          </div>
          <button className="button bg-destructive text-destructive-foreground hover:bg-destructive/90" type="submit">
            Delete {template.name}
          </button>
        </form>
      </div>
    </main>
  );
}
