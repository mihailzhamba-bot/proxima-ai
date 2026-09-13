import { redirect } from "next/navigation";
import { currentMember, requiresSession } from "@/lib/loop/access";
import { QueueError } from "@/lib/loop/service";
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
  if (requiresSession()) {
    try { await currentMember(); }
    catch (e) {
      if (e instanceof QueueError && e.status === 401) redirect("/login");
      return <main className="mx-auto max-w-xl p-6"><h1 className="text-xl font-semibold">Кабинет недоступен</h1><p className="mt-3">Владелец должен выдать доступ к кабинету. Если доступ уже выдан, проверьте подключение сервиса.</p><a className="mt-4 inline-block underline" href="/login">Войти другим аккаунтом</a></main>;
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <a className="sr-only focus:not-sr-only focus:p-3" href="#main-content">К содержимому</a>
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
          <nav aria-label="Навигация на телефоне" className="flex items-center gap-5 border-b border-border p-3 md:hidden"><a href="/brief" className="p-2 underline">Бриф</a><a href="/inbox" className="p-2 underline">Мои задачи</a><ThemeToggle /></nav>
          <main id="main-content" className="flex-1 p-4 lg:p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
