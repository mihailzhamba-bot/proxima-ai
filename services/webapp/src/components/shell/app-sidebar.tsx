"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, LayoutDashboard, Newspaper, Palette, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: typeof Newspaper;
};

const NAV_SECTIONS: readonly { title: string; items: readonly NavItem[] }[] = [
  {
    title: "Ежедневное",
    items: [
      { href: "/brief", label: "Бриф", icon: Newspaper },
      { href: "/inbox", label: "Задачи", icon: Bell },
    ],
  },
  {
    title: "Аналитика",
    items: [{ href: "/dashboard", label: "Дашборд", icon: LayoutDashboard }],
  },
  {
    title: "Система",
    items: [
      { href: "/admin", label: "Админ", icon: ShieldCheck },
      { href: "/styleguide", label: "Стайлгайд", icon: Palette },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** Сайдбар 256px с uppercase-секциями; активный пункт = 8% violet + левый бордер 3px (R04). */
export function AppSidebar() {
  const pathname = usePathname();

  return (
    <nav aria-label="Основная навигация" className="flex flex-1 flex-col overflow-y-auto p-3">
      {NAV_SECTIONS.map((section) => (
        <div key={section.title} className="mb-1 last:mb-0">
          <div className="px-3 pb-1 pt-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground first:pt-1">
            {section.title}
          </div>
          <ul className="flex flex-col gap-0.5">
            {section.items.map((item) => {
              const active = isActive(pathname, item.href);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-9 items-center gap-2.5 rounded-sm border-l-[3px] px-3 text-sm transition-colors",
                      active
                        ? "border-primary bg-primary/[0.08] font-medium text-foreground"
                        : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="size-4 shrink-0" aria-hidden="true" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
