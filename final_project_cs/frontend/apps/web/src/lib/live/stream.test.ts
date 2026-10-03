import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { translator } from "../i18n";
import { LiveError } from "./client";
import { progressText, streamApi, watchIntake, type IntakeWatchEvent, type OpProgress } from "./stream";

const KEY = "tripilot.web.user-key.v1";
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
    const items = new Map([[KEY, "acop_u_known"]]);
    vi.stubGlobal("window", { localStorage: { getItem: (key: string) => items.get(key) ?? null, setItem: () => {}, removeItem: (key: string) => items.delete(key) }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      const next = replies.shift();
      if (!next) throw new TypeError("no answer");
      return next();
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  const init = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: "web-1", message: "안녕" }) };

  it("asks for the stream with the user key, reports each stage and beat, and resolves with the result body", async () => {
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
    expect(calls[0].init.headers).toMatchObject({ "X-User-Key": "acop_u_known", Accept: "text/event-stream", "Content-Type": "application/json" });
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

  it("stops after the last reconnect with `connection_lost` — the screen offers to send it again", async () => {
    replies.push(() => stream([event("accepted", {})], true), () => stream([event("accepted", {})], true), () => stream([event("accepted", {})], true));
    await expect(streamApi("/v1/web/trips/t1/messages", "ko", init, undefined, fast)).rejects.toMatchObject({ code: "connection_lost" });
    expect(calls).toHaveLength(3);
  });
});

describe("following an intake while the server reads it (GET …/trip-intakes/{id}/events)", () => {
  let replies: (() => Response)[];
  beforeEach(() => {
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => "acop_u_known", setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", async () => { const next = replies.shift(); if (!next) throw new TypeError("no answer"); return next(); });
  });
  afterEach(() => vi.unstubAllGlobals());

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
