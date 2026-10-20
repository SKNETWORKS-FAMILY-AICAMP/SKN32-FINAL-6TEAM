import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { streamCandidates, type CandidateList, type CandidateUpdate } from "./intake-review";
import { answeringSession } from "./session-kit";
import { changeLines } from "../../features/plan-check/change-lines";
import { planCandidate } from "../../features/plan-check/from-review";

/**
 * `[2026-10-19 사용자 지시]` 「바꾸기」의 실시간 답 — 저장분이 맞으면 결과만, 아니면 어림 카드(`candidates`) → 줄마다 바뀜(`candidate`) → 최종(`result`).
 * mock 서버 대신 메모리 대역(`fetch`)이다 — 서버 응답은 e2e 시험(`tests/e2e/test_intake_prepared_alternatives.py`)이 본다.
 */
const event = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

function stream(chunks: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}

const leg = (minutes: number, estimated: boolean) => ({ with: "광장시장", minutes, mode: estimated ? "estimate" : "bus", mode_label: estimated ? "직선 어림" : "버스 103", estimated, slack_min: 12 });
const card = (over: Record<string, unknown> = {}) => ({
  rank: 1, place: { name: "덕수궁", latitude: 37.56, longitude: 126.97, source: "tour_api", kind: "activity" }, distance_m: 900, reference: "광장시장",
  rows: [], fits: true, status: "ok", slack: { before: null, after: 12 }, estimated: true, reason: "틀 문장", reason_by: "template",
  legs: { before: null, after: leg(15, true) }, pending: { before: false, after: true, reason: true }, ...over,
});
const list = (candidates: unknown[], prepared: unknown = null) => ({ revision: 2, item: "0-0", current: null, reference: { before: null, after: "광장시장" }, candidates, notes: [], prepared });

describe("the change screen's live alternatives", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: (() => Response)[];
  beforeEach(() => {
    calls = []; replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); const next = replies.shift(); if (!next) throw new TypeError("no answer"); return next(); }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("shows the guessed cards first, then each measured leg and the model's reason, and ends with the final list", async () => {
    replies.push(() => stream([
      event("accepted", { op: "candidates" }),
      event("candidates", list([card()])),
      event("candidate", { rank: 1, rows: [], fits: true, status: "ok", slack: { before: null, after: 9 }, estimated: false, legs: { before: null, after: leg(18, false) }, pending: { before: false, after: false } }),
      event("candidate", { rank: 1, reason: "모델 문장이에요", reason_by: "model", pending: { reason: false } }),
      event("result", list([card({ estimated: false, legs: { before: null, after: leg(18, false) }, pending: undefined, reason: "모델 문장이에요", reason_by: "model" })])),
    ]));
    const first: CandidateList[] = [];
    const updates: CandidateUpdate[] = [];
    const result = await streamCandidates("i1", { source_id: "s1", index: 0 }, 2, "ko", (got) => first.push(got), (got) => updates.push(got));
    expect(calls[0].url).toContain("/v1/web/trip-intakes/i1/candidates?source_id=s1&index=0&revision=2");
    expect(calls[0].init.headers).toMatchObject({ Accept: "text/event-stream" });
    expect(first).toHaveLength(1);
    expect(first[0].candidates[0].pending).toEqual({ before: false, after: true, reason: true });
    expect(updates.map((u) => u.pending)).toEqual([{ before: false, after: false }, { reason: false }]);
    expect(result.candidates[0].reason_by).toBe("model");
    const shown = planCandidate(result.candidates[0], "0-0", "candidate", null);
    expect(shown.legs?.after).toEqual({ with: "광장시장", minutes: 18, modeLabel: "버스 103", estimated: false, slackMin: 12 });
    expect(shown.pending).toBeUndefined();
  });

  it("prepared alternatives come as the result alone — no guessed cards", async () => {
    replies.push(() => stream([event("accepted", { op: "candidates" }), event("result", list([card({ pending: undefined, estimated: false })], { revision: 2, computed_at: "2026-10-19T20:00:00+09:00", stale: [] }))]));
    const first: CandidateList[] = [];
    const result = await streamCandidates("i1", { source_id: "s1", index: 0 }, 2, "ko", (got) => first.push(got), () => undefined);
    expect(first).toEqual([]);
    expect(result.prepared?.stale).toEqual([]);
  });
});

describe("the change screen's map lines", () => {
  it("joins the card being looked at to the stops around it with dashed straight lines, and nothing for the stop as it is", () => {
    const at = (id: string, lat: number) => ({ id, day: 1, coordinates: { lat, lng: 127 } });
    const view = { items: [at("a", 37.50), at("b", 37.51), at("c", 37.52)] } as never;
    const card = { coordinates: { lat: 37.515, lng: 127.01 }, legs: { before: { with: "a" }, after: { with: "c" } } } as never;
    const lines = changeLines(view, at("b", 37.51) as never, [card], 1);
    expect(lines?.shapes.map((shape) => [shape.fromItemId, shape.toItemId, shape.source])).toEqual([["a", "cand-1", "straight_line"], ["cand-1", "c", "straight_line"]]);
    expect(changeLines(view, at("b", 37.51) as never, [card], 0)).toBeNull();
  });
});
