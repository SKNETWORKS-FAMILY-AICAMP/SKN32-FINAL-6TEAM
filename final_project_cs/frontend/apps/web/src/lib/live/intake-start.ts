import type { TripSurvey } from "@/features/onboarding/payload";
import type { Language, Translate } from "../i18n";
import { submitIntake, type IntakeView } from "./intake";
import { LiveError } from "./client";
import { ALL_PAST_CODE, ALL_PAST_TEXT } from "./error-text";

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
export interface IntakeFailure { message: string; files: File[]; plan: PlanRequest | null; loginRequired?: boolean; text?: string }

let current: IntakeStart | null = null;
/** A sending that failed: the entry page shows the server's sentence and gives the attached files and the planning request back. */
let failure: IntakeFailure | null = null;
// Keep only the current submission until its read result can decide whether it must be returned.
let submission: { intakeId: string; text: string; files: File[] } | null = null;

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
  submission = null;
  current = { text: input.text, files: input.files, language: input.language, plan: input.plan ?? null, result, send, cancel: () => { controller.abort(); reject(new DOMException("Cancelled", "AbortError")); } };
  return current;
}

/** The sending in progress, or null (none was started, or the page was reloaded). */
export const intakeStart = (): IntakeStart | null => current;

/** The sending is over (answered, failed or given up): forget it, and the files with it. */
export function endIntakeStart(start: IntakeStart): void {
  if (current === start) current = null;
}

/** A refusal that only an account can get past (a guest's trip limit, or the server says a sign-in is needed): the entry page offers 「계정으로 계속하기」. */
export function loginRequiredBy(error: unknown): boolean {
  const detail = error instanceof LiveError ? error.detail as { login_required?: boolean } | undefined : undefined;
  return error instanceof LiveError && (detail?.login_required === true || error.code.startsWith("guest_trip_"));
}

export function rememberIntakeFailure(start: IntakeStart, error: unknown): void {
  failure = { message: error instanceof Error ? error.message : String(error), files: start.files, plan: start.plan, loginRequired: loginRequiredBy(error) };
}

export const intakeFailure = (): IntakeFailure | null => failure;
export function clearIntakeFailure(): void { failure = null; }

const arrivals = new Map<string, string>();
export function rememberIntakeArrival(id: string, text: string, files: File[] = []): void {
  arrivals.set(id, text);
  submission = { intakeId: id, text, files: [...files] };
}
export function intakeArrival(id: string): string | undefined { return arrivals.get(id); }
export function clearIntakeArrival(id: string): void { arrivals.delete(id); }

export function forgetIntakeSubmission(id: string): void { if (submission?.intakeId === id) submission = null; }

/**
 * A finished read that goes back to 「계획 담기」 instead of opening the plan check, and the sentence said there — or null (stay on the intake page).
 * - No stops were read at all (`review` with no items in any source).
 * - ★`[2026-10-26 사용자 지시]` 「전부 과거면 계획 고르는 화면으로 넘어가면 안되고 그 전에 있는 계획담기 페이지의 가드레일에 걸려서 통과 안되게」: the server ended the
 *   intake because every stop it read is before today (`fatal`, `fatal.code` = `all_dates_in_past`). Korean is the server's sentence, English the web's.
 * Any other failure stays on the intake page with its own panel; a plan with stops (some of them past included) goes on to the plan check.
 */
export function entryReturnOf(view: Pick<IntakeView, "status" | "fatal" | "sources"> | undefined, t: Translate): string | null {
  if (!view) return null;
  if (view.status === "fatal" && view.fatal?.code === ALL_PAST_CODE) return t(ALL_PAST_TEXT[0], ALL_PAST_TEXT[1]);
  if (view.status === "review" && view.sources.every((source) => source.items.length === 0)) return t("일정을 찾지 못했어요. 날짜·시간·장소를 확인해 다시 입력하거나 파일을 올려 주세요.", "No stops were found. Check the dates, times and places, then edit your plan or upload a file.");
  return null;
}

/** Reading finished without stops (or with every stop before today — `entryReturnOf`): return the submitted input, without sending it again. */
export function rememberEmptyIntake(id: string, message: string, originalText: string): void {
  const sent = submission?.intakeId === id ? submission : null;
  failure = { message, text: sent?.text || originalText || undefined, files: sent?.files ?? [], plan: null };
  forgetIntakeSubmission(id);
}
