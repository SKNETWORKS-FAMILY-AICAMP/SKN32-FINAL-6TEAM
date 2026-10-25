import type { Translate } from "@/lib/i18n";
import type { PlanCheckView, ServerProgress } from "./model";

/**
 * ★`[2026-10-24 사용자 확정 — 진행 표시 ③ · ST4F-732]` The plan check's progress as the server's own steps (mockup `mockups/tripilot-plan-check-progress-steps.html` ③):
 * one cell per step it works through, the name of the step it is at under that cell, and one line under the bar with what it is looking at — past
 * `LONG_STEP_S` on one step, for how long. The four points (받았어요 · 일정 읽기 · 장소·운영시간 · 정리 완료) filled 「장소·운영시간」 at the last hours
 * count while the weather check, the gaps filled first and the answers still ran with nothing to show (2026-10-24 local run: 6/6 for 25.5 s).
 *
 * Only what the server sent is shown: a step it skipped (no gap to fill · no answer to put in · an older server) is passed in the done colour — grey there read as
 * 「the last cell never fills」 (user, 2026-10-24).
 */
export const STEP_KEYS = ["reading", "places", "hours", "moves", "risks", "prefill", "answers"] as const;
export type StepKey = (typeof STEP_KEYS)[number];
export type StepState = "done" | "skipped" | "current" | "waiting";
export interface Step { key: StepKey; state: StepState; /** 0–1 of the cell filled. */ fraction: number; packet: ServerProgress | null }
export interface Steps {
  steps: Step[];
  /** The step the server is at. Null before it has begun (just received) and once every step is over (the result is being put together, or done). */
  current: Step | null;
  /** Every step is over but the check is not done yet: the screen is putting the result together. */
  wrapping: boolean;
  /** 0–100, the cells filled. 100 only once the check is done. */
  percent: number;
  finished: boolean;
}

/** ★우리가 고른 값 — the same as the server's `slow` beat (`op_stream.slow_seconds`): one step quiet this long says for how long under the bar. */
export const LONG_STEP_S = 8;

/** The packet of one step: the reading is `reading`, or `reading_api` once a paid model reads it again from the start (it then replaces the first count). */
function packetOf(view: Pick<PlanCheckView, "serverPhases">, key: StepKey): ServerProgress | null {
  const phases = view.serverPhases ?? {};
  return (key === "reading" ? phases.reading_api ?? phases.reading : phases[key]) ?? null;
}

const linesRead = (view: Pick<PlanCheckView, "lines">) => view.lines.length ? view.lines.filter((line) => line.read).length / view.lines.length : 0;

/** A step whose count reached its end is over — except the reading (the model is still writing at m/m) and the gaps being checked again with what was filled. */
const over = (key: StepKey, packet: ServerProgress | null) =>
  packet !== null && key !== "reading" && packet.step !== "recheck" && (packet.total === 0 || packet.done >= packet.total);

/**
 * The cells from the view. `withAnswers` shows the 「답 반영」 cell: there are questions read while it read (the server puts their answers in at the end), or the
 * server already sent that step. Without it the cell is left out — a plan with no such question never has that step.
 */
export function planSteps(view: Pick<PlanCheckView, "stage" | "serverPhases" | "lines">, withAnswers: boolean): Steps {
  const keys = STEP_KEYS.filter((key) => key !== "answers" || withAnswers || packetOf(view, "answers"));
  const finished = view.stage === "done";
  let at = view.stage === "received" ? -1 : view.stage === "checking" ? 1 : 0;      // an older server sends no counts: the stage says reading or the check
  keys.forEach((key, index) => { if (packetOf(view, key)) at = Math.max(at, index); });
  while (at >= 0 && at < keys.length && over(keys[at], packetOf(view, keys[at]))) at += 1;
  if (finished) at = keys.length;
  const steps = keys.map((key, index): Step => {
    const packet = packetOf(view, key);
    if (packet && packet.total === 0) return { key, state: "skipped", fraction: 1, packet };
    if (index < at) return { key, state: packet ? "done" : "skipped", fraction: 1, packet };
    // No count from the server for the reading (the rules read every line · an older server): the lines read so far fill it, as the bar did before.
    if (index === at) return { key, state: "current", fraction: packet && packet.total ? Math.min(1, packet.done / packet.total) : !packet && key === "reading" ? linesRead(view) : 0, packet };
    return { key, state: "waiting", fraction: 0, packet };
  });
  const current = steps.find((step) => step.state === "current") ?? null;
  const percent = finished ? 100 : Math.min(99, steps.reduce((sum, step) => sum + step.fraction, 0) / steps.length * 100);
  return { steps, current, wrapping: !finished && at >= keys.length, percent, finished };
}

/** The name of a step, as under its cell. */
export function stepName(key: StepKey, t: Translate): string {
  switch (key) {
    case "reading": return t("일정 읽기", "Reading");
    case "places": return t("장소", "Places");
    case "hours": return t("운영시간", "Hours");
    case "moves": return t("이동", "Routes");
    case "risks": return t("날씨·도로", "Weather & roads");
    case "prefill": return t("빈칸 채우기", "Filling gaps");
    case "answers": return t("답 반영", "Your answers");
  }
}

/** 「2/7곳」 — how far the step is, in its own unit. Empty until the server counted it. */
export function stepCount(step: Step, t: Translate): string {
  const packet = step.packet;
  if (!packet) return "";
  if (packet.total === 0) return step.key === "prefill" ? t("채울 빈칸 없음", "No gaps to fill") : "";
  const unit = step.key === "reading" ? t("줄", " lines") : step.key === "moves" ? t("구간", " legs") : step.key === "answers" ? t("개", " answers") : t("곳", " stops");
  return `${packet.done}/${packet.total}${unit}`;
}

/** What the step is looking at now — 「북촌한옥마을 확인 중」 (the step's name stands before it, so the words stay short). */
export function stepDetail(step: Step, t: Translate): string {
  const packet = step.packet;
  if (!packet) return "";
  switch (step.key) {
    case "reading": return packet.total > 0 && packet.done >= packet.total ? t("다 읽고 일정으로 정리하는 중", "Read — turning it into stops") : "";
    case "prefill":
      if (packet.step === "recheck") return t("채운 일정 넣고 다시 확인 중", "Checking again with what was filled");
      return packet.title ? t(`${packet.title} 채울 일정 찾는 중`, `Finding a stop for ${packet.title}`) : t("채울 일정 찾는 중", "Finding stops to fill");
    case "answers": return t("고른 답 반영하고 다시 확인 중", "Putting in your answers and checking again");
    default: return packet.title ? t(`${packet.title} 확인 중`, `Checking ${packet.title}`) : t("확인 끝", "Checked");
  }
}

/** 「n초째」 — once one step has had no news for `LONG_STEP_S`. */
export function quietText(seconds: number, t: Translate): string {
  return seconds >= LONG_STEP_S ? t(`${Math.floor(seconds)}초째`, `${Math.floor(seconds)} s`) : "";
}
