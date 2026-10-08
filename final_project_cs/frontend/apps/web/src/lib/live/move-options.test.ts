import { describe, expect, it } from "vitest";
import { LiveError } from "./client";
import { modeChoiceOf, moveOptionsOf, refusalWhy } from "./move-options";

const BODY = {
  intake_id: "i1", revision: 3, from: "0-0", to: "0-1", current_mode: "subway", recommended_mode: "subway",
  options: [
    { mode: "subway", label: "지하철 2호선", minutes: 16, km: 1.5, fare_krw: 1550, fare_is_floor: false, depart: "12:00", arrive: "12:16", slack_min: 14, fits: true, basis: "timetable", grade: "확정" },
    { mode: "bus", minutes: 38, slack_min: -8, fits: false, why_not: "버스로는 8분 늦어요 · 다음 일정이 12:30에 시작해요", basis: "timetable", grade: "확정" },
    { mode: "taxi", label: "택시", minutes: 12, fare_krw: 9000, fare_is_floor: true, slack_min: 18, basis: "estimate", grade: "추정" },
    { mode: "walk", minutes: 52, fare_krw: 0, slack_min: 3, fits: null, why_not: "계산이 오래 걸려 확인하지 못했어요" },
    { mode: "rocket", minutes: 1, fits: true },
  ],
};

describe("moveOptionsOf — the ways to go for one leg, as the server sent them", () => {
  it("keeps an estimated taxi fare distinct from a minimum fare", () => {
    const result = moveOptionsOf({ options: [{ mode: "taxi", fare_krw: 9000, fare_is_floor: false, fare_is_estimate: true }] });
    expect(result!.options[0]).toMatchObject({ fareKrw: 9000, fareIsFloor: false, fareIsEstimate: true });
  });
  it("is none for anything that is not an answer", () => {
    for (const raw of [null, undefined, "x", [], 3]) expect(moveOptionsOf(raw)).toBeNull();
  });

  it("reads the ways in the server's order and drops a way the screen does not know", () => {
    const result = moveOptionsOf(BODY)!;
    expect(result.revision).toBe(3);
    expect(result.currentMode).toBe("subway");
    expect(result.recommendedMode).toBe("subway");
    expect(result.options.map((option) => option.mode)).toEqual(["subway", "bus", "taxi", "walk"]);
    expect(result.options[0]).toMatchObject({ label: "지하철 2호선", minutes: 16, fareKrw: 1550, fareIsFloor: false, slackMin: 14, fits: true, grade: "확정" });
  });

  it("names a way with its own words when the server sent no label, and says the reason as the server wrote it", () => {
    const [, bus] = moveOptionsOf(BODY)!.options;
    expect(bus.label).toBe("버스");
    expect(bus).toMatchObject({ fits: false, slackMin: -8, whyNot: "버스로는 8분 늦어요 · 다음 일정이 12:30에 시작해요" });
  });

  it("keeps a taxi fare as the lowest it can be and a fare it was not given as unknown (never 0)", () => {
    const options = moveOptionsOf(BODY)!.options;
    expect(options[2]).toMatchObject({ fareKrw: 9000, fareIsFloor: true, grade: "추정", basis: "estimate" });
    expect(moveOptionsOf({ options: [{ mode: "subway", minutes: 10, slack_min: 5 }] })!.options[0].fareKrw).toBeNull();
  });

  it("decides `fits` from the slack only when the server said nothing, and never turns an explicit unknown into late", () => {
    const options = moveOptionsOf(BODY)!.options;
    expect(options[2].fits).toBe(true);                                       // no `fits`, slack 18: it reaches
    expect(options[3].fits).toBeNull();                                       // `fits: null`: the server could not finish it - not late
    expect(moveOptionsOf({ options: [{ mode: "bus", minutes: 5 }] })!.options[0].fits).toBeNull();   // no `fits` and no slack: unknown
  });
});

describe("modeChoiceOf — what became of the customer's choice when the stops around the leg changed", () => {
  it("reads whether it was kept or went back to the recommendation, with the reason", () => {
    expect(modeChoiceOf({ mode: "taxi", state: "dropped", why: "앞 일정이 늦어져 택시로도 닿지 않아요" })).toEqual({ mode: "taxi", state: "dropped", why: "앞 일정이 늦어져 택시로도 닿지 않아요" });
    expect(modeChoiceOf({ mode: "taxi", state: "kept" })).toEqual({ mode: "taxi", state: "kept", why: null });
    expect(modeChoiceOf({ state: "weird" })!.state).toBeNull();
    expect(modeChoiceOf(null)).toBeNull();
  });
});

describe("refusalWhy — the server's own reason for a pick it did not take", () => {
  it("says the `why` of a `mode_not_fit` refusal, else the refusal's sentence; nothing for what is not a refusal", () => {
    expect(refusalWhy(new LiveError("mode_not_fit", "그 수단은 고를 수 없어요", { code: "mode_not_fit", why: "택시로도 늦어요" }, 422))).toBe("택시로도 늦어요");
    expect(refusalWhy(new LiveError("mode_not_fit", "그 수단은 고를 수 없어요", { code: "mode_not_fit" }, 422))).toBe("그 수단은 고를 수 없어요");
    expect(refusalWhy(new LiveError("mode_not_fit", "그 수단은 고를 수 없어요", { why: "  " }, 422))).toBe("그 수단은 고를 수 없어요");
    expect(refusalWhy(new Error("x"))).toBeNull();
  });
});
