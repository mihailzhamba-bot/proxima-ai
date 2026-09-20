import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { MetricStrip } from "@/components/metrics/metric-strip";
import { ThemeToggle } from "@/components/theme-toggle";
import { UnreleasedBanner } from "@/components/shell/unreleased-banner";

/*
 * Шелл приложения. Пока auth-контур подключается на деплой-сессии (PA-49 сессия 2):
 * при WEBAPP_REQUIRE_AUTH=true без сессионной cookie уводим на /login.
 * Полная серверная валидация сессии (auth.api.getSession) - вместе с БД-ролью webapp_auth_writer.
 */
export default async function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  if (process.env.WEBAPP_REQUIRE_AUTH === "true") {
    const cookieStore = await cookies();
    const hasSession = cookieStore.has("better-auth.session_token");
    if (!hasSession) {
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
