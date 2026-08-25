"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  LayoutDashboard,
  Palette,
  ShieldCheck,
  Newspaper,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/brief", label: "Бриф", icon: Newspaper },
  { href: "/inbox", label: "Inbox", icon: Bell },
  { href: "/dashboard", label: "Дашборд", icon: LayoutDashboard },
  { href: "/admin", label: "Админ", icon: ShieldCheck },
  { href: "/styleguide", label: "Стайлгайд", icon: Palette },
] as const;

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <nav aria-label="Основная навигация" className="flex flex-col gap-1 p-3">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
            )}
            aria-current={active ? "page" : undefined}
          >
            <Icon className="size-4 shrink-0" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
