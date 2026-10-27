import { describe, expect, it } from "vitest";
import type { IntakeView } from "@/lib/live/intake";
import { emptyStream, reduceStream, toIntakeEvent, type StreamState } from "@/lib/live/intake-events";
import type { IntakeWatchEvent } from "@/lib/live/stream";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { planSteps } from "@/features/plan-check/server-steps";
import { readingScreenOf } from "@/features/plan-check/from-review";
import { BEAT_REREAD_MS, followPolls, rereadGate } from "./follow";

// `[2026-10-27 웹 전수검사]` 읽기 화면의 진행 표시 · 접수 다시 읽기 신호.
function intake(status: IntakeView["status"], stage: string, extra: Partial<ReviewedIntakeView> = {}): ReviewedIntakeView {
  return {
    intake_id: "i1", status, stage, stage_label: "", revision: 3, fatal: null, trip_id: null, needs_review: [], check: null,
    sources: [{ source_id: "s1", kind: "text", filename: null, transcribed: false, items: [], trip: {}, reading: null,
      lines: [{ no: 1, text: "10/1 09:00 경복궁 관람", read: true }, { no: 2, text: "점심은 광장시장", read: true }] }],
    ...extra,
  } as ReviewedIntakeView;
}

const fold = (events: [string, unknown][]): StreamState => events.reduce((state, [name, body]) => {
  const event = toIntakeEvent(name, JSON.stringify(body));
  return event ? reduceStream(state, event) : state;
}, emptyStream());

describe("the reading screen once the server's reading is over", () => {
  // 사용자 보고(2026-10-26): 「계획을 다 읽었어요」인데 막대는 「일정 읽기 8/9줄 · 15초째」로 마지막 패킷에 멈춰 초를 셌다.
  const lastPacket = fold([["progress", { phase: "reading", done: 8, total: 9 }]]);

  it("does not keep counting the last reading packet when the check could not be built (review: null)", () => {
    const view = readingScreenOf(intake("review", "review", { review: null, review_error: "review_failed" }), lastPacket, null);
    const steps = planSteps(view, false);
    expect(steps.current).toBeNull();
    expect(steps.finished).toBe(true);
  });

  it("still counts while the server reads", () => {
    const view = readingScreenOf(intake("reading", "reading"), lastPacket, null);
    expect(planSteps(view, false).current).toMatchObject({ key: "reading" });
    expect(planSteps(view, false).finished).toBe(false);
  });
});

describe("when the screen reads the intake again (GET) while it follows the stream", () => {
  const at = (kind: "accepted" | "stage" | "beat", stage: string | null): IntakeWatchEvent => ({ type: "progress", kind, stage, elapsed: 0, slow: false });

  it("re-reads on the first packet of a connection, every stage event and the end, and on a beat only every BEAT_REREAD_MS", () => {
    // ☆서버 교착 때 접수 GET 이 10분 110회 — beat(3초)마다 GET 을 다시 보냈다.
    let now = 0;
    const gate = rereadGate(() => now);
    const seen: boolean[] = [];
    const feed = (event: IntakeWatchEvent, ms: number) => { now = ms; seen.push(gate(event)); };
    feed(at("accepted", "reading"), 0);
    feed(at("stage", "reading"), 300);                       // a stage event always (the server sends it only on a change)
    feed(at("beat", "reading"), 3_300);
    feed(at("beat", "reading"), 6_300);
    feed(at("beat", "reading"), 300 + BEAT_REREAD_MS);        // what only the GET carries (the questions' second list) still comes, late at most this long
    feed(at("beat", "reading"), 3_300 + BEAT_REREAD_MS);
    feed(at("beat", "checking"), 4_000 + BEAT_REREAD_MS);     // a beat that says a new stage
    feed({ type: "done" }, 4_100 + BEAT_REREAD_MS);
    expect(seen).toEqual([true, true, false, false, true, false, true, true]);
  });

  it("re-reads again on a reconnect (a new connection replays its state)", () => {
    const first = rereadGate(() => 0);
    first(at("accepted", "reading"));
    expect(rereadGate(() => 0)(at("beat", "reading"))).toBe(true);
  });

  it("re-reads at most every 15 s on beats — 10 minutes of beats are at most 40 GETs, not 200", () => {
    let now = 0;
    const gate = rereadGate(() => now);
    let reads = 0;
    for (now = 0; now < 600_000; now += 3_000) if (gate(at(now ? "beat" : "accepted", "reading"))) reads += 1;
    expect(reads).toBeLessThanOrEqual(40);
  });

  it("polls only while there is no live stream — not for the rest of the reading once it was lost", () => {
    expect(followPolls("lost")).toBe(true);
    expect(followPolls("polling")).toBe(true);
    expect(followPolls("live")).toBe(false);
    expect(followPolls("stalled")).toBe(false);
  });
});
