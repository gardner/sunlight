import { env } from "cloudflare:workers";
import { Building2, FileText, MailWarning, Repeat, Send } from "lucide-react";
import { Badge } from "@admin/components/ui/badge";
import { Button } from "@admin/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@admin/components/ui/card";
import { getAdminSummary } from "../lib/data";

const navItems = [
  { href: "/agencies", label: "Agencies", icon: Building2 },
  { href: "/templates", label: "Templates", icon: FileText },
  { href: "/cycles", label: "Cycles", icon: Repeat },
  { href: "/requests", label: "Requests", icon: Send },
];

export default async function AdminDashboard() {
  const summary = await getAdminSummary((env as unknown as CloudflareEnv).DB);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <p className="eyebrow">Sunlight Requests</p>
            <Badge variant="secondary">Admin</Badge>
          </div>
          <h1>Operations dashboard</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            Track agency coverage, request cycles, outbound email state, and
            overdue SunlightRequests from one operational surface.
          </p>
        </div>
        <nav className="flex flex-wrap gap-2" aria-label="Admin sections">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Button asChild key={item.href} variant="outline">
                <a href={item.href}>
                  <Icon aria-hidden="true" />
                  {item.label}
                </a>
              </Button>
            );
          })}
        </nav>
      </header>

      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4" aria-label="Operational summary">
        {summary.map((item) => (
          <Card key={item.label}>
            <CardHeader>
              <CardDescription>{item.label}</CardDescription>
              <CardTitle className="text-4xl">{item.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </section>

      <section className="mt-8 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>Next operator actions</CardTitle>
            <CardDescription>
              The admin dashboard is the control point for preparing, approving,
              and sending SunlightRequests.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3">
            <Button asChild>
              <a href="/cycles/new">
                <Repeat aria-hidden="true" />
                New cycle
              </a>
            </Button>
            <Button asChild variant="secondary">
              <a href="/agencies">Review agencies</a>
            </Button>
            <Button asChild variant="secondary">
              <a href="/requests">Check overdue</a>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MailWarning aria-hidden="true" className="size-5" />
              Email safety
            </CardTitle>
            <CardDescription>
              Run a controlled live Email Sending test before sending a full
              agency cycle.
            </CardDescription>
          </CardHeader>
        </Card>
      </section>
    </main>
  );
}
