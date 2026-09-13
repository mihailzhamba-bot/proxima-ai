"use client";
import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { BriefAnomaly } from "@/lib/data/view-model";
import type { TaskItem } from "@/lib/loop/service";
function normalizeTarget(raw: string): string {
  const [whole, fraction = ""] = raw.trim().replace(",", ".").split(".");
  return `${whole}.${fraction.padEnd(2, "0")}`;
}
const control = "min-h-11 w-full rounded-sm border border-input bg-card px-3 py-2 text-base";
const button = "hover:bg-primary-hover active:opacity-80 min-h-11 rounded-sm bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60";
function useCommand() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const attempt = useRef<{ payload: string; key: string } | null>(null);
  async function send(payload: Record<string, unknown>, success: string) {
    const serialized = JSON.stringify(payload);
    if (!attempt.current || attempt.current.payload !== serialized) attempt.current = { payload: serialized, key: crypto.randomUUID() };
    setPending(true); setError(""); setMessage("");
    try {
      const response = await fetch("/api/loop/queue", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, idempotencyKey: attempt.current.key }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Команда не выполнена.");
      setMessage(success); router.refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Нет связи. Повторите ту же команду."); }
    finally { setPending(false); }
  }
  return { send, pending, message, error };
}
function Result({ message, error }: { message: string; error: string }) {
  return <><p role="status" className="text-sm">{message}</p>{error && <p role="alert" className="text-sm text-status-red">{error}</p>}</>;
}
export function DecisionForm({ anomalies, assignees }: { anomalies: readonly BriefAnomaly[]; assignees: { id: string; name: string }[] }) {
  const [selected, setSelected] = useState(anomalies[0]?.id ?? "");
  const request = useCommand();
  const anomaly = anomalies.find(a => a.id === selected);
  const diagnosis = anomaly?.diagnosis;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await request.send({ operation: "accept", signalId: form.get("signal"), snapshotId: anomaly?.snapshotId, assigneeId: form.get("assignee"), action: form.get("action"), dueAt: new Date(String(form.get("due"))).toISOString(), expectedOutcome: form.get("outcome"), expected: { horizon_days: Number(form.get("horizon")), metrics: [{ name: form.get("metric"), value: normalizeTarget(String(form.get("target"))), unit: form.get("metric") === "orders" ? "count" : "RUB", source_ref: form.get("source") }] } }, "Решение сохранено, задача появилась в очереди.");
  }
  if (!anomalies.length) return <p className="text-sm text-muted-foreground">Для назначения задачи нужен свежий сигнал с источниками.</p>;
  if (!assignees.length) return <p className="text-sm text-muted-foreground">В кабинете пока нет сотрудников с выданным доступом. Владелец должен добавить исполнителя.</p>;
  return <section aria-labelledby="decision-heading" className="rounded-md border border-border bg-card p-5">
    <h2 id="decision-heading" className="text-lg font-semibold">Подтвердить действие</h2>
    <form onSubmit={submit} className="mt-4 space-y-4"><fieldset disabled={request.pending} className="space-y-4">
      <label className="grid gap-1 text-sm">Сигнал<select name="signal" className={control} value={selected} onChange={e => setSelected(e.target.value)}>{anomalies.map(a => <option key={a.id} value={a.id}>{a.supplierArticle ?? a.subjectName ?? a.nmId ?? a.scenarioCode}</option>)}</select></label>
      {diagnosis && <div className="space-y-2 border-l-2 border-border pl-4 text-sm"><p className="font-medium">Разбор по данным</p><p>{diagnosis.hypothesis}</p><p className="text-muted-foreground">Альтернативы: {diagnosis.alternatives.join(" ")}</p><p className="text-muted-foreground">Неизвестно: {diagnosis.unknowns.join(" ")}</p><p>{diagnosis.verification}</p></div>}
      <label className="grid gap-1 text-sm">Что сделать<textarea name="action" required maxLength={2000} className={control} rows={2} /></label>
      <div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-1 text-sm">Исполнитель<select name="assignee" required className={control}>{assignees.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label><label className="grid gap-1 text-sm">Срок, ваше местное время<input name="due" type="datetime-local" required className={control} /></label></div>
      <label className="grid gap-1 text-sm">Ожидаемый результат<textarea name="outcome" required maxLength={2000} rows={2} className={control} /></label>
      <div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-1 text-sm">Показатель цели<select name="metric" required className={control}><option value="orders">Заказы за день, шт.</option><option value="revenue">Выручка за день, ₽</option></select></label><label className="grid gap-1 text-sm">Целевое значение<input name="target" type="text" inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" required className={`${control} font-mono`} /></label><label className="grid gap-1 text-sm">Наблюдать дней после выполнения<input name="horizon" type="number" min={1} max={365} required className={`${control} font-mono`} /></label></div>
      <label className="grid gap-1 text-sm">Источник цели, дата решения<input name="source" required maxLength={500} className={control} /></label>
      <p className="text-xs text-muted-foreground">Цель фиксирует ожидание владельца. Достижение цели проверяется по тому же SKU. Причинная связь с действием требует отдельной проверки.</p>
      <button type="submit" className={button}>{request.pending ? "Сохраняем…" : "Подтвердить и назначить"}</button>
    </fieldset><Result {...request} /></form>
  </section>;
}
function TaskCard({ task, role }: { task: TaskItem; role: "owner" | "employee" }) {
  const request = useCommand();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const form = new FormData(e.currentTarget);
    const submitter = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const operation = role === "owner" ? "cancel" : submitter?.value === "block" ? "block" : "complete";
    await request.send({ operation, taskId: task.task_id, evidence: form.get("evidence") }, operation === "cancel" ? "Задача отменена." : operation === "block" ? "Блокер записан." : "Выполнение записано. Проверка эффекта ещё впереди.");
  }
  return <article className="rounded-md border border-border bg-card p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><h2 className="text-base font-semibold">{task.action}</h2><span className="text-sm">{({ open: "Назначена", blocked: "Есть блокер", completed: "Выполнена", cancelled: "Отменена" })[task.status]}</span></div>
    <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-muted-foreground">Исполнитель</dt><dd className="break-all">{task.assignee_name || "Сотрудник"}</dd></div><div><dt className="text-muted-foreground">Срок</dt><dd className="font-mono"><time dateTime={task.due_at}>{new Date(task.due_at).toLocaleString("ru-RU", { timeZone: "Europe/Moscow" })} МСК</time></dd></div></dl>
    <p className="mt-3 text-sm">Ожидаем: {task.expected_outcome}</p><p className="mt-2 text-sm text-muted-foreground">Наблюдение после выполнения: <span className="font-mono">{task.horizon_days}</span> дн.</p>
    {task.orphaned && <p className="mt-3 text-sm text-status-yellow">Исходный прогон удалён. Решение и его snapshot сохранены.</p>}
    {task.evidence && <p className="mt-3 whitespace-pre-wrap break-words text-sm">Подтверждение сотрудника: {task.evidence}</p>}
    {task.blocker && <p className="mt-3 whitespace-pre-wrap break-words text-sm">Блокер: {task.blocker}</p>}
    {task.status === "completed" && <p className="mt-3 text-sm text-muted-foreground">{task.observation?.reason ?? "Проверка ещё не проведена. Восстановление продаж не подтверждено."}</p>}
    {task.status !== "cancelled" && (role === "owner" || ["open", "blocked"].includes(task.status)) && <form onSubmit={submit} className="mt-4 space-y-3"><label className="grid gap-1 text-sm">{role === "owner" ? "Причина отмены" : "Результат или блокер, ссылка на подтверждение"}<textarea name="evidence" required maxLength={5000} rows={2} className={control} disabled={request.pending} /></label><div className="flex flex-wrap gap-3"><button className={role === "owner" ? "min-h-11 rounded-sm border border-border px-4 py-2 text-sm disabled:opacity-60" : button} value="complete" disabled={request.pending}>{request.pending ? "Сохраняем…" : role === "owner" ? "Отменить задачу" : "Подтвердить выполнение"}</button>{role === "employee" && task.status === "open" && <button className="min-h-11 rounded-sm border border-border px-4 py-2 text-sm" value="block" disabled={request.pending}>Сообщить о блокере</button>}</div></form>}
    {role === "owner" && task.status === "completed" && <button className="mt-3 min-h-11 rounded-sm border border-border px-4 py-2 text-sm disabled:opacity-60" disabled={request.pending} onClick={() => request.send({ operation: "observe", taskId: task.task_id }, "Наблюдение записано.")}>Проверить результат по данным</button>}
    <Result {...request} />
  </article>;
}
export function TaskQueue({ tasks, role }: { tasks: TaskItem[]; role: "owner" | "employee" }) {
  return <div className="space-y-4">{tasks.length ? tasks.map(task => <TaskCard key={task.task_id} task={task} role={role} />) : <div className="rounded-md border border-border bg-card p-5"><h2 className="font-semibold">Задач пока нет</h2><p className="mt-2 text-sm text-muted-foreground">{role === "owner" ? "Подтвердите действие по свежему сигналу в брифе." : "Здесь появятся задачи, которые владелец назначит вам."}</p></div>}</div>;
}
