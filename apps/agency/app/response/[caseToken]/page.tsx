import { env } from "cloudflare:workers";
import { notFound } from "next/navigation";
import { getSunlightRequestByToken } from "../../../lib/response-intake";
import { submitResponseAction } from "./actions";
import { UploadPanel } from "./UploadPanel";

interface ResponsePageProps {
  params: Promise<{ caseToken: string }>;
  searchParams?: Promise<{ submitted?: string }>;
}

export default async function ResponsePage({ params, searchParams }: ResponsePageProps) {
  const { caseToken } = await params;
  const request = await getSunlightRequestByToken((env as unknown as CloudflareEnv).DB, caseToken);
  const submitted = (await searchParams)?.submitted === "1";

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
      {submitted ? (
        <div className="notice">Response details saved. Sunlight will review the submission.</div>
      ) : null}
      <UploadPanel caseToken={caseToken} />
      <section className="panel stack">
        <div>
          <p className="eyebrow">Final details</p>
          <h2>Submit response metadata</h2>
        </div>
        <form action={submitResponseAction} className="stack">
          <input name="caseToken" type="hidden" value={caseToken} />
          <label>
            Response type
            <select defaultValue="full_response" name="category">
              <option value="full_response">Complete response</option>
              <option value="partial_response">Partial response</option>
              <option value="no_records_held">No records held</option>
              <option value="follow_up">Will respond separately by email</option>
            </select>
          </label>
          <label>
            Agency reference
            <input name="agencyReference" />
          </label>
          <label>
            Contact name
            <input name="submitterName" />
          </label>
          <label>
            Contact email
            <input name="submitterEmail" type="email" />
          </label>
          <label>
            Notes
            <textarea name="notes" rows={5} />
          </label>
          <button className="button" type="submit">
            Submit response details
          </button>
        </form>
      </section>
    </main>
  );
}
