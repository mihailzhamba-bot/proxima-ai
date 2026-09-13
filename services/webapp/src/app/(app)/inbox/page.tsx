import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { TaskQueue } from "@/components/loop/queue";
import { currentPrincipal } from "@/lib/loop/access";
import { getQueueService, QueueError, type QueuePage } from "@/lib/loop/service";
import { resolveDataMode } from "@/lib/data/provider";
export const metadata: Metadata = { title: "Мои задачи" };
export const dynamic = "force-dynamic";
export default async function InboxPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const filter = (typeof params.filter === "string" ? params.filter : "all") as QueuePage["filter"];
  const cursor = typeof params.cursor === "string" ? params.cursor : undefined;
  if (resolveDataMode() !== "postgres") return <div className="mx-auto max-w-3xl space-y-4"><h1 className="text-2xl font-semibold">Мои задачи</h1><p>Очередь доступна после подключения кабинета и личных аккаунтов. Сейчас открыт демонстрационный режим.</p></div>;
  let queue;
  try { queue = await getQueueService().list(await currentPrincipal(), { filter, cursor }); }
  catch (e) {
    if (e instanceof QueueError && e.status === 401) redirect("/login");
    return <div className="mx-auto max-w-3xl space-y-4"><h1 className="text-2xl font-semibold">Мои задачи</h1><p role="alert">{e instanceof QueueError ? e.message : "Очередь временно недоступна. Попробуйте обновить страницу."}</p></div>;
  }
  return <div className="mx-auto max-w-3xl space-y-5"><h1 className="text-2xl font-semibold">{queue.role === "owner" ? "Задачи кабинета" : "Мои задачи"}</h1><p className="text-sm text-muted-foreground">Выполнение подтверждает сотрудник. Результат проверяется отдельно по новым данным.</p><nav aria-label="Фильтр задач" className="flex flex-wrap gap-4 text-sm"><a className="underline" href="/inbox?filter=all">Все</a><a className="underline" href="/inbox?filter=active">Открытые и блокеры</a><a className="underline" href="/inbox?filter=history">История</a></nav><TaskQueue {...queue} />{queue.nextCursor && <a className="inline-block min-h-11 underline" href={`/inbox?filter=${queue.filter}&cursor=${encodeURIComponent(queue.nextCursor)}`}>Следующая страница</a>}{cursor && <a className="underline" href={`/inbox?filter=${queue.filter}`}>В начало очереди</a>}</div>;
}
