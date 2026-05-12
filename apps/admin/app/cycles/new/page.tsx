import { env } from "cloudflare:workers";
import { headers } from "next/headers";
import { requireAdmin } from "../../../lib/access";
import { createCycleAction } from "./actions";

export default async function NewCyclePage() {
  const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Request cycles</p>
          <h1>New cycle</h1>
        </div>
        <a className="button" href="/cycles">
          Cycles
        </a>
      </header>

      <form action={createCycleAction} className="panel stack">
        <label>
          Cycle month
          <input name="cycleMonth" placeholder="2026-05" required pattern="\d{4}-\d{2}" />
        </label>
        <button className="button" type="submit">
          Create cycle
        </button>
      </form>
    </main>
  );
}
