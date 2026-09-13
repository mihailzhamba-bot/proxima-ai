import { currentPrincipal } from "./access";
import { getQueueService, QueueError } from "./service";

export function assertSameOrigin(request: Request) {
  const configured = process.env.BETTER_AUTH_URL;
  if (!configured || request.headers.get("origin") !== new URL(configured).origin) throw new QueueError(403, "Источник запроса не разрешён.");
}
export async function queueRequest(request: Request, method: "GET" | "POST") {
  try {
    if (method === "POST") assertSameOrigin(request);
    const p = await currentPrincipal(request.headers);
    const queue = getQueueService();
    if (method === "GET") return Response.json(await queue.list(p), { headers: { "Cache-Control": "no-store" } });
    const text = await request.text();
    if (text.length > 20_000) throw new QueueError(413, "Запрос слишком большой.");
    let body: Record<string, unknown>;
    try { body = JSON.parse(text); } catch { throw new QueueError(400, "Неверный формат запроса."); }
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new QueueError(400, "Неверный формат запроса.");
    let result;
    if (body.operation === "accept") result = await queue.accept(p, body);
    else if (typeof body.taskId === "string" && typeof body.idempotencyKey === "string") {
      if (body.operation === "block") result = await queue.event(p, body.taskId, "blocked", body.evidence, body.idempotencyKey);
      else if (body.operation === "complete") result = await queue.event(p, body.taskId, "completed", body.evidence, body.idempotencyKey);
      else if (body.operation === "cancel") result = await queue.event(p, body.taskId, "cancelled", body.evidence, body.idempotencyKey);
      else if (body.operation === "observe") result = await queue.observe(p, body.taskId, body.idempotencyKey);
      else throw new QueueError(400, "Неизвестная команда.");
    } else throw new QueueError(400, "Неизвестная команда.");
    return Response.json(result, { headers: { "Cache-Control": "no-store" } });
  } catch (e) {
    return Response.json({ error: e instanceof QueueError ? e.message : "Сервис очереди временно недоступен." }, { status: e instanceof QueueError ? e.status : 503, headers: { "Cache-Control": "no-store" } });
  }
}
