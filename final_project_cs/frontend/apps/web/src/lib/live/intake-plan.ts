import type { Language } from "../i18n";
import { translator } from "../i18n";
import { LiveError } from "./client";
import { getIntake, planIntake, type IntakePlanInput } from "./intake";
import type { PlanRequest } from "./intake-start";
import type { OpProgress } from "./stream";

/**
 * 「계획 짜 주기」 after the server has taken the intake (`[2026-10-03 사용자 지시]`): wait until the server has read the customer's
 * short text, then ask it to plan and register (`POST …/trip-intakes/{id}/plan`, streamed — `stream.ts`).
 *
 * ★The server plans only from an intake that has finished reading (`review`; while it reads, the plan call answers 409
 *   `intake_not_ready`) and only for the revision it holds now — so the intake is read again first and that revision is sent. A
 *   customer who wrote nothing has an intake that is `review` from the start, and the first read answers at once.
 */

/** How often the intake is asked while the server still reads (the same pace the intake screen falls back to). */
export const READ_POLL_MS = 1_500;
/** The server's own reading limit is longer, but a short text should not take minutes: past this the customer is told, not kept waiting. */
export const READ_LIMIT_MS = 300_000;

/** `reading`: the server reads the text (label = its own words for the stage). `planning`: the plan call is out — it cannot be taken back. */
export type PlanPhase = "reading" | "planning";

export interface PlanHooks {
  phase: (phase: PlanPhase, label?: string | null) => void;
  progress: (progress: OpProgress) => void;
  /** The customer left, or the screen is gone: stop quietly (nothing more is asked, and no plan is requested). */
  cancelled: () => boolean;
}

export interface PlanDeps {
  getIntake: typeof getIntake;
  planIntake: typeof planIntake;
  sleep: (ms: number) => Promise<void>;
  now: () => number;
}

const defaults: PlanDeps = {
  getIntake, planIntake,
  sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  now: () => Date.now(),
};

/**
 * Resolves with the registered trip's id, or with `null` when the customer left first. Rejects with the server's sentence
 * (a refusal, a read that failed, a plan it could not make) or with `read_timeout` / `connection_lost`.
 */
export async function planFromIntake(intakeId: string, ask: PlanRequest, language: Language, hooks: PlanHooks, deps: PlanDeps = defaults): Promise<string | null> {
  const t = translator(language);
  const began = deps.now();
  hooks.phase("reading");
  let view = await deps.getIntake(intakeId, language);
  while (view.status === "reading") {
    hooks.phase("reading", view.stage_label || null);
    if (deps.now() - began > READ_LIMIT_MS) {
      throw new LiveError("read_timeout", t("서버가 쓰신 글을 읽는 데 너무 오래 걸려요. 잠시 뒤 다시 보내 주세요.", "The server is taking too long to read your text. Please send again in a moment."));
    }
    await deps.sleep(READ_POLL_MS);
    if (hooks.cancelled()) return null;
    view = await deps.getIntake(intakeId, language);
  }
  if (hooks.cancelled()) return null;
  if (view.status === "fatal") {
    throw new LiveError(view.fatal?.code ?? "fatal", view.fatal?.detail || t("서버가 이 글을 읽지 못했어요.", "The server could not read this text."));
  }
  const input: IntakePlanInput = { start_date: ask.start_date, days: ask.days, party_size: ask.party_size, keep_read_items: false, ...(ask.survey && { survey: ask.survey }) };
  hooks.phase("planning");
  const result = await deps.planIntake(intakeId, view.revision, input, language, hooks.progress);
  return result.trip.trip_id;
}
