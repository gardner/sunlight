import { env } from "cloudflare:workers";
import { Button } from "@admin/components/ui/button";
import { listAllAgencies } from "../../lib/agencies";
import { AgencyBrowser } from "./AgencyBrowser";

export default async function AgenciesPage() {
  const agencies = await listAllAgencies((env as unknown as CloudflareEnv).DB);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Agencies</h1>
        </div>
        <Button asChild>
          <a href="/">Dashboard</a>
        </Button>
      </header>

      <AgencyBrowser agencies={agencies} />
    </main>
  );
}
