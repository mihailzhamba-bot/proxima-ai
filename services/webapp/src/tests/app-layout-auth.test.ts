import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

/*
 * Гард шелла (Codex audit 22.09, P3/P4): при WEBAPP_REQUIRE_AUTH=true решение
 * принимает серверная валидация сессии (auth.api.getSession), а не наличие
 * cookie - произвольное значение cookie раньше проходило guard, а штатная
 * HTTPS-cookie с __Secure-префиксом наоборот не находилась. Асинхронный
 * серверный компонент вызывается как функция; redirect() в тесте бросает,
 * как это делает Next.
 */

const getSession = vi.fn();
vi.mock("@/lib/auth", () => ({
  getAuth: () => ({ api: { getSession: (args: unknown) => getSession(args) } }),
}));

const redirectCalls: string[] = [];
vi.mock("next/navigation", () => ({
  redirect: (path: string): never => {
    redirectCalls.push(path);
    throw new Error(`redirect:${path}`);
  },
}));

vi.mock("next/headers", () => ({
  headers: async () => new Headers({ cookie: "attacker-value=1" }),
}));

async function importLayout() {
  vi.resetModules();
  return (await import("@/app/(app)/layout")).default;
}

describe("app layout auth guard", () => {
  beforeEach(() => {
    getSession.mockReset();
    redirectCalls.length = 0;
  });
  afterEach(() => {
    delete process.env.WEBAPP_REQUIRE_AUTH;
  });

  it("без флага гард выключен и сессия не проверяется (fixtures/локальный режим)", async () => {
    const AppLayout = await importLayout();
    await AppLayout({ children: null });
    expect(getSession).not.toHaveBeenCalled();
    expect(redirectCalls).toEqual([]);
  });

  it("нет серверной сессии -> redirect на /login (P3: произвольная cookie не пропускает)", async () => {
    process.env.WEBAPP_REQUIRE_AUTH = "true";
    getSession.mockResolvedValue(null);
    const AppLayout = await importLayout();
    await expect(AppLayout({ children: null })).rejects.toThrow("redirect:/login");
    expect(getSession).toHaveBeenCalledTimes(1);
  });

  it("валидная сессия рендерит шелл (P4: __Secure-имя разбирает better-auth)", async () => {
    process.env.WEBAPP_REQUIRE_AUTH = "true";
    getSession.mockResolvedValue({ user: { id: "u1" }, session: { id: "s1" } });
    const AppLayout = await importLayout();
    const tree = await AppLayout({ children: null });
    expect(tree).toBeTruthy();
    expect(redirectCalls).toEqual([]);
  });
});
