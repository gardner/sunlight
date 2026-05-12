"use client";

import { usePathname } from "next/navigation";
import {
  Building2,
  FileText,
  Home,
  Repeat,
  Send,
  Inbox,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/authorities", label: "Authorities", icon: Building2 },
  { href: "/requests", label: "Requests", icon: Send },
  { href: "/cycles", label: "Cycles", icon: Repeat },
  { href: "/templates", label: "Templates", icon: FileText },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r bg-card flex flex-col min-h-screen sticky top-0 shrink-0">
      <div className="h-16 flex items-center px-6 border-b">
        <span className="font-bold text-lg text-primary tracking-tight">Sunlight Admin</span>
      </div>
      <nav className="p-4 flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <a
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              <Icon className="size-4" aria-hidden="true" />
              {item.label}
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
