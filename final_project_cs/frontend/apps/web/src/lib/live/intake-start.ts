import type { TripSurvey } from "@/features/onboarding/payload";
import type { Language } from "../i18n";
import { submitIntake } from "./intake";
import { LiveError } from "./client";

/**
 * 「계획 짜 주기」 — what the customer asked the server to plan (`[2026-10-03 사용자 지시]`, the registration page's third panel).
 * The server's own request is `POST …/trip-intakes/{id}/plan` (`IntakePlanInput`); `wish` is the short text the customer wrote about
 * the trip they want (it rides as the intake's text, which the server reads as the preferences), and is kept here only so a refusal
 * can give it back.
 */
export interface PlanRequest {
  start_date: string;
  days: number;
  party_size: number;
  wish: string;
  /** Only when the customer finished the onboarding questions. */
  survey?: TripSurvey;
}

/**
 * A plan on its way to the server — `[2026-10-03 사용자 지시]` 「계획 확인하기」 moves to the progress screen at once instead
 * of waiting on the entry page for the server to answer.
 *
 * The entry page prepares the request (`beginIntake`) and renders its progress screen before navigating. That screen
 * starts sending after its first paint, follows `result`, and moves on to the intake's own page (the server's
 * progress stream, `watchIntake`) once the server has given the intake an id. The sending is held here, in memory, because
 * a page change cannot carry a file; a reload loses it and the screen sends the customer back to the entry page.
 *
 * With a `plan` the screen does not open the intake's page: it waits for the server to finish reading the short text, asks the
 * server to plan (`planFromIntake`) and goes on to the registered trip.
 */
export interface IntakeStart {
  text: string;
  files: File[];
  language: Language;
  /** Set when the customer chose 「계획 짜 주기」: only this is sent (a text of the wish, no files). */
  plan: PlanRequest | null;
  /** The server's answer (`intake_id`), or its refusal. Already has a handler, so a failure nobody is waiting for is not "unhandled". */
  result: Promise<{ intake_id: string }>;
  /** The customer left before the server answered: stop waiting for it (an intake it already made stays unused). */
  cancel: () => void;
  /** 진행 화면을 그린 뒤 호출한다. 경로가 바뀌어 두 번 호출되어도 전송은 한 번이다. */
  send: () => void;
}

/** What comes back to the entry page when the server refused: its sentence, and what the customer had chosen to send. */
export interface IntakeFailure { message: string; files: File[]; plan: PlanRequest | null; loginRequired?: boolean }

let current: IntakeStart | null = null;
/** A sending that failed: the entry page shows the server's sentence and gives the attached files and the planning request back. */
let failure: IntakeFailure | null = null;

export function beginIntake(input: { text: string; files: File[]; language: Language; humanToken?: string | null; plan?: PlanRequest | null }): IntakeStart {
  const controller = new AbortController();
  let resolve!: (value: { intake_id: string }) => void;
  let reject!: (error: unknown) => void;
  const result = new Promise<{ intake_id: string }>((yes, no) => { resolve = yes; reject = no; });
  let sent = false;
  const send = () => {
    if (sent || controller.signal.aborted) return;
    sent = true;
    void submitIntake(input.text, input.files, input.language, input.humanToken, controller.signal).then(resolve, reject);
  };
  result.catch(() => undefined);
  failure = null;
  current = { text: input.text, files: input.files, language: input.language, plan: input.plan ?? null, result, send, cancel: () => { controller.abort(); reject(new DOMException("Cancelled", "AbortError")); } };
  return current;
}

/** The sending in progress, or null (none was started, or the page was reloaded). */
export const intakeStart = (): IntakeStart | null => current;

/** The sending is over (answered, failed or given up): forget it, and the files with it. */
export function endIntakeStart(start: IntakeStart): void {
  if (current === start) current = null;
}

export function rememberIntakeFailure(start: IntakeStart, error: unknown): void {
  const detail = error instanceof LiveError ? error.detail as { login_required?: boolean } | undefined : undefined;
  failure = { message: error instanceof Error ? error.message : String(error), files: start.files, plan: start.plan,
    loginRequired: error instanceof LiveError && (detail?.login_required === true || error.code.startsWith("guest_trip_")) };
}

export const intakeFailure = (): IntakeFailure | null => failure;
export function clearIntakeFailure(): void { failure = null; }

const arrivals = new Map<string, string>();
export function rememberIntakeArrival(id: string, text: string): void { arrivals.set(id, text); }
export function intakeArrival(id: string): string | undefined { return arrivals.get(id); }
export function clearIntakeArrival(id: string): void { arrivals.delete(id); }
