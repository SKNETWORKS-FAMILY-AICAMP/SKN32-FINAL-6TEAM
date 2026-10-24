import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { translator } from "../i18n";
import { currentSession, LiveError, resetSessionState, SESSION_CHANGED_EVENT, sessionOf, takeSession } from "./client";
import { answeringSession, CSRF } from "./session-kit";
import { progressText, streamApi, watchIntake, type IntakeWatchEvent, type OpProgress } from "./stream";

const fast = { watchdogMs: 60, reconnectMs: [5, 5] };

/** A server-sent event block, as `op_stream.sse` writes it. */
const event = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

/** A streamed answer. `open` leaves the line open after the chunks (a server gone quiet); cancelling it ends it. */
function stream(chunks: string[], open = false): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      if (!open) controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("a long request with live progress (POST …/messages · …/plan with Accept: text/event-stream)", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: (() => Response)[];

  beforeEach(() => {
    calls = [];
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => {
      calls.push({ url, init });
      const next = replies.shift();
      if (!next) throw new TypeError("no answer");
      return next();
    }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  const init = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: "web-1", message: "안녕" }) };

  it("asks for the stream with the session cookie and the CSRF token (it is a write), reports each stage and beat, and resolves with the result body", async () => {
    replies.push(() => stream([
      event("accepted", { op: "message", at: "2026-10-03T10:00:00+09:00" }),
      event("stage", { stage: "understanding", label: "요청을 이해하는 중이에요", waiting_on: "model", elapsed: 0.4 }),
      event("beat", { elapsed: 9.2, stage: "understanding", label: "요청을 이해하는 중이에요", waiting_on: "model", stage_elapsed: 8.8, slow: true, server_time: "…" }),
      event("result", { status: "answered", answer: "서버 답" }),
    ]));
    const seen: OpProgress[] = [];
    const result = await streamApi<{ answer: string }>("/v1/web/trips/t1/messages", "ko", init, (progress) => seen.push(progress), fast);
    expect(result).toEqual({ status: "answered", answer: "서버 답" });
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toMatch(/\/v1\/web\/trips\/t1\/messages$/);
    expect(calls[0].init.headers).toMatchObject({ "X-CSRF-Token": CSRF, Accept: "text/event-stream", "Content-Type": "application/json" });
    expect(calls[0].init.headers).not.toHaveProperty("X-User-Key");
    expect(calls[0].init.credentials).toBe("include");
    expect(seen).toEqual([
      { stage: null, elapsed: 0, slow: false, lost: false },
      { stage: "understanding", elapsed: 0.4, slow: false, lost: false },
      { stage: "understanding", elapsed: 9.2, slow: true, lost: false },
    ]);
  });

  it("reads a server without streams: the JSON answer comes once, as before", async () => {
    replies.push(() => json({ status: "answered", answer: "JSON 답" }));
    expect(await streamApi("/v1/web/trips/t1/messages", "ko", init, undefined, fast)).toEqual({ status: "answered", answer: "JSON 답" });
  });

  it("turns the server's error event into its code and sentence, keeping `retryable`", async () => {
    replies.push(() => stream([event("accepted", {}), event("error", { code: "timeout", message: "시간이 오래 걸려 기다리기를 멈췄어요", retryable: true })]));
    const error = await streamApi("/v1/web/trips/t1/messages", "ko", init, undefined, fast).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(LiveError);
    expect(error).toMatchObject({ code: "timeout", message: "시간이 오래 걸려 기다리기를 멈췄어요", detail: { retryable: true } });
    expect(calls).toHaveLength(1);
  });

  it("gives a refusal before the stream opens as the usual JSON error (too many open streams)", async () => {
    replies.push(() => json({ error: { code: "too_many_streams", message: "열어 둔 실시간 연결이 너무 많다" } }, 429));
    await expect(streamApi("/v1/web/trips/t1/messages", "ko", init, undefined, fast)).rejects.toMatchObject({ code: "too_many_streams" });
  });

  it("a line gone quiet for two beats is lost: it says so and sends the very same request again", async () => {
    replies.push(() => stream([event("accepted", {}), event("stage", { stage: "understanding", elapsed: 0.1 })], true));
    replies.push(() => stream([event("accepted", {}), event("result", { status: "duplicate", answer: "같은 요청을 이미 받았어요.\n서버 답" })]));
    const seen: OpProgress[] = [];
    const result = await streamApi<{ status: string }>("/v1/web/trips/t1/messages", "ko", init, (progress) => seen.push(progress), fast);
    expect(result.status).toBe("duplicate");
    expect(calls).toHaveLength(2);
    expect(calls[1].init.body).toBe(calls[0].init.body);
    expect(seen.some((progress) => progress.lost)).toBe(true);
    expect(seen.at(-1)?.lost).toBe(false);
  });

  it("a gateway 502/504 before the stream opens (the API was being swapped) sends the very same request again", async () => {
    replies.push(() => new Response("<html>502 Bad Gateway</html>", { status: 502, headers: { "Content-Type": "text/html" } }));
    replies.push(() => new Response("", { status: 504 }));
    replies.push(() => stream([event("accepted", {}), event("result", { status: "answered", answer: "서버 답" })]));
    const seen: OpProgress[] = [];
    const result = await streamApi<{ answer: string }>("/v1/web/trips/t1/messages", "ko", init, (progress) => seen.push(progress), fast);
    expect(result.answer).toBe("서버 답");
    expect(calls).toHaveLength(3);
    expect(calls[2].init.body).toBe(calls[0].init.body);
    expect(seen.some((progress) => progress.lost)).toBe(true);
  });

  it("other refusals before the stream opens are not retried (a 503 from the API itself is its own answer)", async () => {
    replies.push(() => json({ error: { code: "model_unavailable", message: "모델이 잠시 쉬고 있어요" } }, 503));
    await expect(streamApi("/v1/web/trips/t1/messages", "ko", init, undefined, fast)).rejects.toMatchObject({ code: "model_unavailable" });
    expect(calls).toHaveLength(1);
  });

  it("stops after the last reconnect with `connection_lost` — the screen offers to send it again", async () => {
    replies.push(() => stream([event("accepted", {})], true), () => stream([event("accepted", {})], true), () => stream([event("accepted", {})], true));
    await expect(streamApi("/v1/web/trips/t1/messages", "ko", init, undefined, fast)).rejects.toMatchObject({ code: "connection_lost" });
    expect(calls).toHaveLength(3);
  });
});

describe("session boundaries before a streamed write opens", () => {
  let calls: { url: string; init: RequestInit }[];
  let dispatched: string[];
  const path = "/v1/web/trips/t1/messages";
  const init = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: "session-boundary-1", message: "안녕" }) };

  beforeEach(() => {
    resetSessionState();
    calls = [];
    dispatched = [];
    vi.useFakeTimers();
    vi.stubGlobal("window", {
      localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
      dispatchEvent: (seen: Event) => { dispatched.push(seen.type); return true; },
    });
  });
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); resetSessionState(); });

  it("keeps the replacement session and the original late 401 refusal from a stream started with the previous session (F-06)", async () => {
    const previous = sessionOf({ kind: "member", csrf_token: "csrf-a" })!;
    const member = sessionOf({ kind: "member", csrf_token: "csrf-b" })!;
    takeSession(previous);
    dispatched.length = 0;
    let answer!: (response: Response) => void;
    let started!: () => void;
    const pending = new Promise<void>((resolve) => { started = resolve; });
    vi.stubGlobal("fetch", (url: string, sent: RequestInit) => {
      calls.push({ url, init: sent });
      started();
      return new Promise<Response>((resolve) => { answer = resolve; });
    });
    const result = streamApi(path, "ko", init, undefined, fast).catch((caught: unknown) => caught);
    await pending;
    takeSession(member);
    const detail = { code: "unauthenticated", message: "이전 요청의 로그인 상태가 끝났어요.", request: "session-a" };
    answer(json({ error: detail }, 401));

    expect(await result).toMatchObject({ code: "unauthenticated", message: detail.message, detail, status: 401 });
    expect(currentSession()).toBe(member);
    await vi.advanceTimersByTimeAsync(100);
    expect(calls).toHaveLength(1);
    expect(calls[0].init.headers).toMatchObject({ "X-CSRF-Token": "csrf-a" });
    expect(dispatched).toEqual([SESSION_CHANGED_EVENT]);
  });

  it("refreshes the token once after csrf_failed and reports session_changed without resending or reconnecting the stream (F-18)", async () => {
    takeSession(sessionOf({ kind: "member", csrf_token: "csrf-a" })!);
    dispatched.length = 0;
    vi.stubGlobal("fetch", async (url: string, sent: RequestInit) => {
      calls.push({ url, init: sent });
      if (url.endsWith("/v1/web/auth/me")) return json({ kind: "member", csrf_token: "csrf-b" });
      return json({ error: { code: "csrf_failed", message: "토큰이 바뀌었어요." } }, 403);
    });
    const seen: OpProgress[] = [];

    await expect(streamApi(path, "ko", init, (progress) => seen.push(progress), fast)).rejects.toMatchObject({
      code: "session_changed", message: "로그인 상태가 바뀌어 요청을 보내지 않았어요. 화면을 확인하고 다시 시도해 주세요.",
    });
    expect(currentSession()?.csrf).toBe("csrf-b");
    expect(dispatched).toEqual([SESSION_CHANGED_EVENT]);
    await vi.advanceTimersByTimeAsync(100);
    expect(calls).toHaveLength(2);
    expect(calls.filter((call) => call.url.endsWith("/v1/web/auth/me"))).toHaveLength(1);
    const writes = calls.filter((call) => call.init.method === "POST");
    expect(writes).toHaveLength(1);
    expect(writes[0].init).toMatchObject({ body: init.body, headers: { "X-CSRF-Token": "csrf-a", Accept: "text/event-stream" } });
    expect(seen.some((progress) => progress.lost)).toBe(false);
  });

  it("does not reconnect a lost stream once the session has changed meanwhile — the body stays with the account that sent it (F-02 보강)", async () => {
    const previous = sessionOf({ kind: "member", csrf_token: "csrf-a" })!;
    const member = sessionOf({ kind: "member", csrf_token: "csrf-b" })!;
    takeSession(previous);
    dispatched.length = 0;
    vi.stubGlobal("fetch", async (url: string, sent: RequestInit) => {
      calls.push({ url, init: sent });
      return new Response("", { status: 504 });                     // the gateway dropped the line: normally sent again after the wait
    });
    const seen: OpProgress[] = [];
    const result = streamApi(path, "ko", init, (progress) => seen.push(progress), fast).catch((caught: unknown) => caught);
    await vi.advanceTimersByTimeAsync(0);                             // the first attempt has been answered 504 and the reconnect wait is on
    expect(calls).toHaveLength(1);
    takeSession(member);                                              // another tab signed in while this request was waiting to reconnect
    await vi.advanceTimersByTimeAsync(100);

    expect(await result).toMatchObject({ code: "session_changed" });
    expect(currentSession()).toBe(member);
    expect(calls).toHaveLength(1);                                    // no second POST with the new account's token
    expect(calls[0].init.headers).toMatchObject({ "X-CSRF-Token": "csrf-a" });
    expect(seen.some((progress) => progress.lost)).toBe(true);
  });

  it("reconnects a lost stream as before when the session is unchanged (the F-02 보강 guard does not get in the way)", async () => {
    takeSession(sessionOf({ kind: "member", csrf_token: "csrf-a" })!);
    let first = true;
    vi.stubGlobal("fetch", async (url: string, sent: RequestInit) => {
      calls.push({ url, init: sent });
      if (first) { first = false; return new Response("", { status: 504 }); }
      return json({ status: "answered", answer: "서버 답" });
    });
    const result = streamApi<{ answer: string }>(path, "ko", init, undefined, fast);
    await vi.advanceTimersByTimeAsync(100);
    expect((await result).answer).toBe("서버 답");
    expect(calls).toHaveLength(2);
    expect(calls[1].init.body).toBe(calls[0].init.body);
    expect(calls[1].init.headers).toMatchObject({ "X-CSRF-Token": "csrf-a" });
  });

  it("passes on a failed csrf token refresh without resending or reconnecting the stream (F-18)", async () => {
    takeSession(sessionOf({ kind: "member", csrf_token: "csrf-a" })!);
    const detail = { code: "internal_error", message: "서버에서 로그인 상태를 확인하지 못했어요.", request: "session-probe" };
    vi.stubGlobal("fetch", async (url: string, sent: RequestInit) => {
      calls.push({ url, init: sent });
      if (url.endsWith("/v1/web/auth/me")) return json({ error: detail }, 500);
      return json({ error: { code: "csrf_failed" } }, 403);
    });
    const seen: OpProgress[] = [];

    await expect(streamApi(path, "ko", init, (progress) => seen.push(progress), fast)).rejects.toMatchObject({
      code: "internal_error", message: detail.message, detail, status: 500,
    });
    await vi.advanceTimersByTimeAsync(100);
    expect(calls).toHaveLength(2);
    expect(calls.filter((call) => call.url.endsWith("/v1/web/auth/me"))).toHaveLength(1);
    expect(calls.filter((call) => call.init.method === "POST")).toHaveLength(1);
    expect(seen.some((progress) => progress.lost)).toBe(false);
  });
});

describe("following an intake while the server reads it (GET …/trip-intakes/{id}/events)", () => {
  let replies: (() => Response)[];
  beforeEach(() => {
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", answeringSession(async () => { const next = replies.shift(); if (!next) throw new TypeError("no answer"); return next(); }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  const follow = async () => {
    const events: IntakeWatchEvent[] = [];
    const end = await watchIntake("i-1", "ko", (seen) => events.push(seen), new AbortController().signal, fast);
    return { end, events };
  };

  it("passes on each stage and beat, then ends when the server says the reading is done", async () => {
    const state = { status: "reading", stage: "reading", stage_label: "읽는 중", revision: 1, fatal_code: null, quiet_seconds: 0.2 };
    replies.push(() => stream([event("accepted", { op: "intake", state }), event("beat", { elapsed: 3, stage: "reading", slow: false }), event("result", { state: { ...state, status: "review" } })]));
    expect(await follow()).toEqual({ end: "done", events: [
      { type: "progress", stage: "reading", elapsed: 0, slow: false }, { type: "progress", stage: "reading", elapsed: 3, slow: false }, { type: "done" }] });
  });

  it("tells a stopped reading (`stalled`), a missing intake, a server without the stream and a silent line apart", async () => {
    replies.push(() => stream([event("accepted", {}), event("error", { code: "stalled", retryable: true })]));
    expect((await follow()).end).toBe("stalled");
    replies.push(() => stream([event("error", { code: "not_found", retryable: false })]));
    expect((await follow()).end).toBe("gone");
    replies.push(() => json({ error: { code: "not_found" } }, 404));
    expect((await follow()).end).toBe("unsupported");
    replies.push(() => stream([event("accepted", {})], true));
    expect((await follow()).end).toBe("lost");
  });
});

describe("the waiting line", () => {
  const ko = translator("ko"), en = translator("en");
  const waiting: [string, string] = ["답변을 준비하고 있어요…", "Preparing a reply…"];

  it("shows the server's stage in the customer's language with how long it has taken, or that it is reconnecting", () => {
    expect(progressText(null, ko, waiting)).toBe("답변을 준비하고 있어요…");
    expect(progressText({ stage: "understanding", elapsed: 0.4, slow: false, lost: false }, ko, waiting)).toBe("요청을 이해하는 중이에요…");
    expect(progressText({ stage: "planning", elapsed: 12.6, slow: false, lost: false }, en, waiting)).toBe("Planning your days… (13 s)");
    expect(progressText({ stage: "looking_up", elapsed: 12, slow: true, lost: false }, ko, waiting)).toBe("장소 정보를 확인하는 중이에요 · 응답이 느려요 (12초째)");
    expect(progressText({ stage: "new_stage", elapsed: 2, slow: false, lost: false }, ko, waiting)).toBe("new_stage… (2초)");
    expect(progressText({ stage: "planning", elapsed: 2, slow: false, lost: true }, ko, waiting)).toBe("서버와 연결이 끊겼어요 — 다시 연결하는 중이에요…");
  });
});
