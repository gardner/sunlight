import { validateTemplateVariables } from "./request-prep";

export interface RequestTemplate {
  body_template: string;
  id: string;
  name: string;
  status: "active" | "inactive";
  subject_template: string;
  updated_at: string;
}

export interface CreateTemplateInput {
  bodyTemplate: string;
  name: string;
  status: "active";
  subjectTemplate: string;
}

export function buildCreateTemplateInput(input: {
  bodyTemplate: string;
  name: string;
  subjectTemplate: string;
}): CreateTemplateInput {
  const name = input.name.trim();
  const subjectTemplate = input.subjectTemplate.trim();
  const bodyTemplate = input.bodyTemplate.trim();

  if (!name || !subjectTemplate || !bodyTemplate) {
    throw new Error("Template name, subject, and body are required");
  }

  validateTemplateVariables(subjectTemplate);
  validateTemplateVariables(bodyTemplate);

  return {
    bodyTemplate,
    name,
    status: "active",
    subjectTemplate,
  };
}

export async function listTemplates(db: D1Database): Promise<RequestTemplate[]> {
  const result = await db
    .prepare(
      `
        SELECT id, name, subject_template, body_template, status, updated_at
        FROM sunlight_request_templates
        WHERE deleted_at IS NULL
        ORDER BY updated_at DESC, name
      `,
    )
    .all<RequestTemplate>();

  return result.results;
}

export async function getTemplate(db: D1Database, id: string): Promise<RequestTemplate | null> {
  return db
    .prepare(
      `
        SELECT id, name, subject_template, body_template, status, updated_at
        FROM sunlight_request_templates
        WHERE id = ? AND deleted_at IS NULL
      `,
    )
    .bind(id)
    .first<RequestTemplate>();
}

export interface UpdateTemplateInput {
  bodyTemplate: string;
  name: string;
  status: "active" | "inactive";
  subjectTemplate: string;
}

export function buildUpdateTemplateInput(input: {
  bodyTemplate: string;
  name: string;
  status: "active" | "inactive";
  subjectTemplate: string;
}): UpdateTemplateInput {
  const name = input.name.trim();
  const subjectTemplate = input.subjectTemplate.trim();
  const bodyTemplate = input.bodyTemplate.trim();

  if (!name || !subjectTemplate || !bodyTemplate) {
    throw new Error("Template name, subject, and body are required");
  }

  validateTemplateVariables(subjectTemplate);
  validateTemplateVariables(bodyTemplate);

  return {
    bodyTemplate,
    name,
    status: input.status,
    subjectTemplate,
  };
}

export async function updateTemplate(
  db: D1Database,
  id: string,
  input: UpdateTemplateInput,
): Promise<void> {
  await db
    .prepare(
      `
        UPDATE sunlight_request_templates
        SET name = ?,
            subject_template = ?,
            body_template = ?,
            status = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND deleted_at IS NULL
      `,
    )
    .bind(input.name, input.subjectTemplate, input.bodyTemplate, input.status, id)
    .run();
}

export async function createTemplate(
  db: D1Database,
  input: CreateTemplateInput,
): Promise<string> {
  const id = `tpl_${crypto.randomUUID().replaceAll("-", "")}`;
  await db
    .prepare(
      `
        INSERT INTO sunlight_request_templates (
          id,
          name,
          subject_template,
          body_template,
          status
        ) VALUES (?, ?, ?, ?, ?)
      `,
    )
    .bind(id, input.name, input.subjectTemplate, input.bodyTemplate, input.status)
    .run();
  return id;
}

export async function deleteTemplate(db: D1Database, id: string): Promise<void> {
  // Check if template is used by any authorities
  const authorityCheck = await db.prepare("SELECT id FROM sunlight_authorities WHERE default_template_id = ? LIMIT 1").bind(id).first();
  if (authorityCheck) {
    throw new Error("Cannot delete template: it is currently assigned as the default for one or more authorities.");
  }

  await db
    .prepare("UPDATE sunlight_request_templates SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?")
    .bind(id)
    .run();
}
