import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { getAuth } from "@/lib/auth";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { MetricStrip } from "@/components/metrics/metric-strip";
import { ThemeToggle } from "@/components/theme-toggle";
import { UnreleasedBanner } from "@/components/shell/unreleased-banner";

/*
 * Шелл приложения. При WEBAPP_REQUIRE_AUTH=true решение принимает серверная
 * валидация сессии (auth.api.getSession), а не наличие cookie: произвольное
 * значение cookie раньше проходило guard (P3), а штатная HTTPS-cookie с
 * __Secure-префиксом наоборот не находилась (P4) - Codex audit 22.09.2026.
 * Имя cookie и проверку подписи ведёт better-auth; БД-роль - webapp_auth_writer
 * (provision-runtime-roles.sh). Без БД guard fail-closed: 500, не пропуск.
 */
export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  if (process.env.WEBAPP_REQUIRE_AUTH === "true") {
    const session = await getAuth().api.getSession({ headers: await headers() });
    if (!session) {
      redirect("/login");
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <UnreleasedBanner />
      <div className="flex flex-1">
        <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card md:flex">
          <div className="flex h-14 items-center gap-2 border-b border-border px-5">
            <span className="text-sm font-bold tracking-tight">PROXIMA</span>
            <span className="ml-auto">
              <ThemeToggle />
            </span>
          </div>
          <AppSidebar />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <MetricStrip />
          <main className="flex-1 p-4 lg:p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
