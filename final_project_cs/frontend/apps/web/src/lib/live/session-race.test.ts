import { afterEach, expect, it, vi } from "vitest";
import { api, currentSession, ensureSession, probeSession, resetSessionState, sessionOf, takeSession } from "./client";

afterEach(() => { resetSessionState(); vi.unstubAllGlobals(); });

it.each([200, 401, 500])("로그인 전 조회의 늦은 응답(%i)이 새 회원 세션을 덮지 않는다", async (status) => {
  resetSessionState();
  vi.stubGlobal("window", { localStorage: { getItem: () => null, removeItem: () => undefined }, dispatchEvent: () => true });
  let answer!: (response: Response) => void;
  vi.stubGlobal("fetch", () => new Promise<Response>((resolve) => { answer = resolve; }));
  const previous = probeSession("ko");
  const member = sessionOf({ kind: "member", csrf_token: "member-csrf" })!;
  takeSession(member);
  answer(new Response(JSON.stringify(status === 200
    ? { kind: "guest", csrf_token: "old-guest-csrf", guest_idle_hours: 168 }
    : { error: { code: status === 401 ? "unauthenticated" : "internal_error", message: "이전 조회 응답" } }), { status }));
  await previous;
  expect(currentSession()).toEqual(member);
});

it("이전 세션 API의 늦은 401은 새 회원 세션과 원문 오류 정보를 유지한다", async () => {
  resetSessionState();
  vi.stubGlobal("window", { localStorage: { getItem: () => null, removeItem: () => undefined }, dispatchEvent: () => true });
  const previousSession = sessionOf({ kind: "member", csrf_token: "csrf-a" })!;
  const member = sessionOf({ kind: "member", csrf_token: "csrf-b" })!;
  takeSession(previousSession);
  let answer!: (response: Response) => void;
  let began!: () => void;
  const started = new Promise<void>((resolve) => { began = resolve; });
  const fetcher = vi.fn(() => new Promise<Response>((resolve) => { answer = resolve; began(); }));
  vi.stubGlobal("fetch", fetcher);
  const previous = api("/v1/web/trips/t1/delete", "ko", { method: "POST" });
  await started;
  takeSession(member);
  const detail = { code: "unauthenticated", message: "이전 요청의 로그인 상태를 확인할 수 없어요.", request_id: "previous-request" };
  answer(new Response(JSON.stringify({ error: detail }), { status: 401 }));
  await expect(previous).rejects.toMatchObject({ code: "unauthenticated", message: detail.message, detail, status: 401 });
  expect(currentSession()).toBe(member);
  expect(fetcher).toHaveBeenCalledOnce();
});

it("게스트 생성 POST의 늦은 응답은 새 회원 세션 객체를 반환하고 메모리에 유지한다", async () => {
  resetSessionState();
  vi.stubGlobal("window", { localStorage: { getItem: () => null, removeItem: () => undefined }, dispatchEvent: () => true });
  let answer!: (response: Response) => void;
  let began!: () => void;
  const started = new Promise<void>((resolve) => { began = resolve; });
  const fetcher = vi.fn((url: string) => {
    if (new URL(url).pathname === "/v1/web/auth/me") return Promise.resolve(new Response(JSON.stringify({ error: { code: "unauthenticated", message: "로그인이 필요해요." } }), { status: 401 }));
    return new Promise<Response>((resolve) => { answer = resolve; began(); });
  });
  vi.stubGlobal("fetch", fetcher);
  const previous = ensureSession("ko");
  await started;
  const member = sessionOf({ kind: "member", csrf_token: "member-csrf" })!;
  takeSession(member);
  answer(new Response(JSON.stringify({ kind: "guest", csrf_token: "old-guest-csrf", guest_idle_hours: 168 })));
  await expect(previous).resolves.toBe(member);
  expect(currentSession()).toBe(member);
  expect(fetcher.mock.calls.map(([url]) => new URL(url).pathname)).toEqual(["/v1/web/auth/me", "/v1/web/auth/session"]);
});
