import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { TaskQueue } from "@/components/loop/queue";
import { currentPrincipal } from "@/lib/loop/access";
import { getQueueService, QueueError } from "@/lib/loop/service";
import { resolveDataMode } from "@/lib/data/provider";
export const metadata: Metadata = { title: "Мои задачи" };
export const dynamic = "force-dynamic";
export default async function InboxPage() {
  if (resolveDataMode() !== "postgres") return <div className="mx-auto max-w-3xl space-y-4"><h1 className="text-2xl font-semibold">Мои задачи</h1><p>Очередь доступна после подключения кабинета и личных аккаунтов. Сейчас открыт демонстрационный режим.</p></div>;
  let queue;
  try { queue = await getQueueService().list(await currentPrincipal()); }
  catch (e) {
    if (e instanceof QueueError && e.status === 401) redirect("/login");
    return <div className="mx-auto max-w-3xl space-y-4"><h1 className="text-2xl font-semibold">Мои задачи</h1><p role="alert">{e instanceof QueueError ? e.message : "Очередь временно недоступна. Попробуйте обновить страницу."}</p></div>;
  }
  return <div className="mx-auto max-w-3xl space-y-5"><h1 className="text-2xl font-semibold">{queue.role === "owner" ? "Задачи кабинета" : "Мои задачи"}</h1><p className="text-sm text-muted-foreground">Выполнение подтверждает сотрудник. Результат проверяется отдельно по новым данным.</p><TaskQueue {...queue} /></div>;
}
