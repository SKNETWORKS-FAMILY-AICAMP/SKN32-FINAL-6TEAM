/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 1단계]` The two things the plan screen asks before the plan is read, and what they send. The values are the backend's own
 * (`constraints.survey`: `pace` · `on_disruption` - see `features/onboarding/payload.ts`); nothing here is a new server contract.
 */

/** How full a day is made (the 「하루 일정의 여유」 choice). 「적당히」 is chosen from the start: left alone, it is sent. */
export type Pace = "relaxed" | "moderate" | "packed";
export const DEFAULT_PACE: Pace = "moderate";
/** In the order they are shown. The help line must not name a number of places (「한 곳쯤 더」 is the only measure said). */
export const PACES: readonly { value: Pace; ko: string; en: string }[] = [
  { value: "relaxed", ko: "여유롭게", en: "Relaxed" },
  { value: "moderate", ko: "적당히", en: "Balanced" },
  { value: "packed", ko: "꽉 차게", en: "Packed" },
];

/** 항로 지킴이 (Course Keeper): on = problems on the trip are changed by themselves and told; off = the customer is asked first. */
export type Guardian = "on" | "off";

/**
 * ★What 「건너뛰기 — 끄고 진행」 sends is `ask_first`, SAID OUT LOUD. Sending nothing is not the same: the server then applies closures, disasters and traffic stops by itself,
 * and the screen's promise (「끄고 진행하면 문제가 생길 때 먼저 물어봐요」) would be broken. So every choice of the card carries a value.
 */
export function disruptionOf(guardian: Guardian): "replace" | "ask_first" {
  return guardian === "on" ? "replace" : "ask_first";
}

/** The survey fields this screen decides. They are laid over whatever the preference survey already holds (the latest choice wins). */
export function criteriaOf(pace: Pace, guardian: Guardian): { pace: Pace; on_disruption: "replace" | "ask_first" } {
  return { pace, on_disruption: disruptionOf(guardian) };
}

export function isPace(value: unknown): value is Pace {
  return value === "relaxed" || value === "moderate" || value === "packed";
}
