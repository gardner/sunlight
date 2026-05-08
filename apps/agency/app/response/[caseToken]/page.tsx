import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { sha256Hex } from "../../../lib/tokens";

interface ResponsePageProps {
  params: Promise<{ caseToken: string }>;
}

export default async function ResponsePage({ params }: ResponsePageProps) {
  const { caseToken } = await params;
  const tokenHash = await sha256Hex(caseToken);
  const request = await (env as unknown as CloudflareEnv).DB.prepare(
    `
      SELECT
        sunlight_requests.id,
        sunlight_requests.case_token_hint,
        sunlight_requests.reply_email,
        sunlight_requests.status,
        sunlight_agencies.name AS agency_name,
        sunlight_request_cycles.cycle_month,
        sunlight_request_cycles.covered_from,
        sunlight_request_cycles.covered_until
      FROM sunlight_requests
      JOIN sunlight_agencies ON sunlight_agencies.id = sunlight_requests.agency_id
      JOIN sunlight_request_cycles ON sunlight_request_cycles.id = sunlight_requests.cycle_id
      WHERE sunlight_requests.case_token_hash = ?
      LIMIT 1
    `,
  )
    .bind(tokenHash)
    .first<{
      agency_name: string;
      case_token_hint: string;
      covered_from: string;
      covered_until: string;
      cycle_month: string;
      reply_email: string;
      status: string;
    }>();

  if (!request) {
    notFound();
  }

  return (
    <main className="shell">
      <p className="eyebrow">Sunlight Request</p>
      <h1>{request.agency_name}</h1>
      <dl>
        <div>
          <dt>Cycle</dt>
          <dd>{request.cycle_month}</dd>
        </div>
        <div>
          <dt>Covered period</dt>
          <dd>
            {request.covered_from} to {request.covered_until}
          </dd>
        </div>
        <div>
          <dt>Reply email</dt>
          <dd>{request.reply_email}</dd>
        </div>
      </dl>
      <p>
        Uploads are not enabled yet. For now, reply to the email address above.
      </p>
    </main>
  );
}
