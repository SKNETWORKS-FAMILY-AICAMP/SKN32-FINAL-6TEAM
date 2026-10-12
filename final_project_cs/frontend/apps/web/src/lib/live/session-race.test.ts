import { afterEach, expect, it, vi } from "vitest";
import { currentSession, probeSession, resetSessionState, sessionOf, takeSession } from "./client";

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
