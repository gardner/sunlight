const ALLOWED_TEMPLATE_VARIABLES = new Set([
  "authority_name",
  "covered_date_range",
  "cycle_month",
  "legal_regime",
  "reply_email",
  "response_url",
  "sunlight_contact_details",
]);

export interface TemplateVariables {
  authority_name: string;
  covered_date_range: string;
  cycle_month: string;
  legal_regime: string;
  reply_email: string;
  response_url: string;
  sunlight_contact_details: string;
}

export function addWorkingDays(
  startDate: string,
  workingDays: number,
  holidays: Set<string> = new Set(),
): string {
  const date = parseDate(startDate);
  let remaining = workingDays;

  while (remaining > 0) {
    date.setUTCDate(date.getUTCDate() + 1);
    const iso = formatDate(date);
    if (!isWeekend(date) && !holidays.has(iso)) {
      remaining -= 1;
    }
  }

  return formatDate(date);
}

export function renderTemplate(
  template: string,
  variables: Partial<TemplateVariables>,
): string {
  validateTemplateVariables(template);
  return template.replaceAll(/\{([a-z_]+)\}/g, (_, key: string) => {
    const value = variables[key as keyof TemplateVariables];
    if (value === undefined) {
      throw new Error(`Missing template variable: ${key}`);
    }
    return value;
  });
}

export function validateTemplateVariables(template: string): void {
  const unknown = Array.from(template.matchAll(/\{([a-z_]+)\}/g))
    .map((match) => match[1])
    .filter((key) => !ALLOWED_TEMPLATE_VARIABLES.has(key));

  if (unknown.length > 0) {
    throw new Error(`Unsupported template variable(s): ${unknown.join(", ")}`);
  }
}

export function buildReplyEmail(caseToken: string): string {
  return `reply-${caseToken}@sunlight.nz`;
}

export function buildResponseUrl(caseToken: string): string {
  return `https://requests.sunlight.nz/response/${caseToken}`;
}

export async function sha256Hex(value: string): Promise<string> {
  const data = new TextEncoder().encode(value);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function generateCaseToken(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

function base64Url(bytes: Uint8Array): string {
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00.000Z`);
}

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function isWeekend(date: Date): boolean {
  const day = date.getUTCDay();
  return day === 0 || day === 6;
}
