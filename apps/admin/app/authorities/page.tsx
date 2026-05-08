import { env } from "cloudflare:workers";
import { Button } from "@admin/components/ui/button";
import { listAllAuthorities } from "../../lib/authorities";
import { AuthorityBrowser } from "./AuthorityBrowser";

export default async function AuthoritiesPage() {
  const authorities = await listAllAuthorities((env as unknown as CloudflareEnv).DB);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Authorities</h1>
        </div>
        <Button asChild>
          <a href="/">Dashboard</a>
        </Button>
      </header>

      <AuthorityBrowser authorities={authorities} />
    </main>
  );
}
