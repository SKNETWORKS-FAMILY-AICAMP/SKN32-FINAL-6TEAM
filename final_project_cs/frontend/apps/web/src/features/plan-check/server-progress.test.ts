import { describe, expect, it } from "vitest";
import type { PlanCheckView, PlanLine, ServerProgress } from "./model";
import { planSteps, quietText, stepCount, stepDetail, stepName, type StepKey } from "./server-steps";

// `[2026-10-24 사용자 확정 — 진행 표시 ③ · ST4F-732]` The bar as the server's own steps (mockup `tripilot-plan-check-progress-steps.html` ③).
type Phases = NonNullable<PlanCheckView["serverPhases"]>;
const view = (stage: PlanCheckView["stage"], phases: Phases = {}, lines: PlanLine[] = []) => ({ stage, serverPhases: phases, lines });
const at = (phase: ServerProgress["phase"], done: number, total: number, title: string | null = null, step?: "recheck"): ServerProgress =>
  ({ phase, done, total, title, ...(step && { step }) });
const ko = (korean: string) => korean;
const states = (steps: ReturnType<typeof planSteps>) => Object.fromEntries(steps.steps.map((step) => [step.key, step.state])) as Record<StepKey, string>;

describe("the plan check's bar, one cell per step of the server", () => {
  it("marks a completed check as checked", () => {
    expect(planSteps(view("done"), false).unchecked).toBe(false);
  });

  it("has a cell for every step it works through — 「답 반영」 only when there are answers to put in", () => {
    expect(planSteps(view("reading"), false).steps.map((step) => step.key)).toEqual(["reading", "places", "hours", "moves", "risks", "prefill"]);
    expect(planSteps(view("reading"), true).steps.map((step) => step.key)).toContain("answers");
    expect(planSteps(view("checking", { answers: at("answers", 0, 1) }), false).steps.map((step) => step.key)).toContain("answers");   // the server sent it
  });

  it("reads the lines first — the model's count, or the lines read when the rules read them all", () => {
    expect(planSteps(view("received"), false).current).toBeNull();
    const counted = planSteps(view("reading", { reading: at("reading", 4, 8) }), false);
    expect(counted.current).toMatchObject({ key: "reading", fraction: 0.5 });
    const ruled = planSteps(view("reading", {}, [{ read: true } as PlanLine, { read: false } as PlanLine]), false);
    expect(ruled.current).toMatchObject({ key: "reading", fraction: 0.5 });
    expect(planSteps(view("reading", { reading: at("reading", 1, 8), reading_api: at("reading_api", 6, 8) }), false).current?.fraction).toBe(0.75);  // a paid re-read replaces it
  });

  it("stays on the reading at 8/8 — the model is still writing — and moves on once a step's count is over", () => {
    expect(planSteps(view("reading", { reading: at("reading", 8, 8) }), false).current?.key).toBe("reading");
    // hours 7/7 (current null) is over: the server is already on the legs, even before their first count arrives
    const hoursDone = planSteps(view("checking", { reading: at("reading", 8, 8), places: at("places", 7, 7), hours: at("hours", 7, 7) }), false);
    expect(hoursDone.current?.key).toBe("moves");
    expect(states(hoursDone)).toMatchObject({ reading: "done", places: "done", hours: "done", moves: "current", risks: "waiting" });
  });

  it("shows the weather check that used to run behind a full bar (2026-10-24: 6/6 for 25.5 s)", () => {
    const phases = { places: at("places", 7, 7), hours: at("hours", 7, 7), moves: at("moves", 6, 6), risks: at("risks", 1, 7, "북촌한옥마을") };
    const steps = planSteps(view("checking", phases), false);
    expect(steps.current).toMatchObject({ key: "risks" });
    expect(stepCount(steps.current!, ko)).toBe("1/7곳");
    expect(stepDetail(steps.current!, ko)).toBe("북촌한옥마을 확인 중");
    expect(steps.percent).toBeLessThan(99);
  });

  it("passes a step that had nothing to do in the done colour, and keeps the gaps being checked again as the current step", () => {
    const none = planSteps(view("checking", { risks: at("risks", 7, 7), prefill: at("prefill", 0, 0) }), false);
    expect(states(none).prefill).toBe("skipped");
    expect(none.steps.find((step) => step.key === "prefill")?.fraction).toBe(1);
    expect(none.current).toBeNull();
    expect(none.wrapping).toBe(true);                                             // every step over, the check not done yet
    const recheck = planSteps(view("checking", { prefill: at("prefill", 2, 2, null, "recheck") }), false);
    expect(recheck.current?.key).toBe("prefill");
    expect(stepDetail(recheck.current!, ko)).toBe("채운 일정 넣고 다시 확인 중");
    expect(stepCount(planSteps(view("checking", { prefill: at("prefill", 0, 0) }), false).steps.find((step) => step.key === "prefill")!, ko)).toBe("채울 빈칸 없음");
  });

  it("is full only when the check is done, and never goes back as the counts come", () => {
    const order: Phases[] = [{}, { reading: at("reading", 2, 8) }, { reading: at("reading", 8, 8), places: at("places", 3, 7) },
      { reading: at("reading", 8, 8), places: at("places", 7, 7), hours: at("hours", 0, 7, "경복궁") },
      { reading: at("reading", 8, 8), places: at("places", 7, 7), hours: at("hours", 7, 7), moves: at("moves", 3, 6, "A → B") },
      { reading: at("reading", 8, 8), places: at("places", 7, 7), hours: at("hours", 7, 7), moves: at("moves", 6, 6), risks: at("risks", 6, 7, "N서울타워") }];
    const values = order.map((phases) => planSteps(view("checking", phases), false).percent);
    expect(values).toEqual([...values].sort((a, b) => a - b));
    expect(Math.max(...values)).toBeLessThanOrEqual(99);
    const done = planSteps(view("done", order[order.length - 1]), false);
    expect(done.percent).toBe(100);
    expect(done.steps.every((step) => step.state === "done" || step.state === "skipped")).toBe(true);
  });

  it("names the steps and says for how long one has had no news past 8 s", () => {
    expect(["reading", "places", "hours", "moves", "risks", "prefill", "answers"].map((key) => stepName(key as StepKey, ko)))
      .toEqual(["일정 읽기", "장소", "운영시간", "이동", "날씨·도로", "빈칸 채우기", "답 반영"]);
    expect(quietText(7.9, ko)).toBe("");
    expect(quietText(12.4, ko)).toBe("12초째");
    const moves = planSteps(view("checking", { moves: at("moves", 2, 6, "광장시장 → 국립중앙박물관") }), false).current!;
    expect(`${stepCount(moves, ko)} · ${stepDetail(moves, ko)}`).toBe("2/6구간 · 광장시장 → 국립중앙박물관 확인 중");
    expect(stepDetail(planSteps(view("checking", { moves: at("moves", 5, 6) }), false).current!, ko)).toBe("확인 끝");
  });
});
