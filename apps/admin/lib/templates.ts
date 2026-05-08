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
        ORDER BY updated_at DESC, name
      `,
    )
    .all<RequestTemplate>();

  return result.results;
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
