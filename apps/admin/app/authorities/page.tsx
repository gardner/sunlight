import { env } from "cloudflare:workers";
import { Button } from "@admin/components/ui/button";
import { listAllAuthorities } from "../../lib/authorities";
import { AuthorityBrowser } from "./AuthorityBrowser";
import { headers } from "next/headers";
import { requireAdmin } from "../../lib/access";

export default async function AuthoritiesPage() {
    const cloudflareEnv = env as unknown as CloudflareEnv;
  await requireAdmin(await headers(), cloudflareEnv.DB, cloudflareEnv);
  const authorities = await listAllAuthorities((env as unknown as CloudflareEnv).DB);

  return (
    <main className="shell">
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Admin</p>
          <h1>Authorities</h1>
        </div>
      </header>

      <AuthorityBrowser authorities={authorities} />
    </main>
  );
}
