import type { Language } from "../i18n";
import { submitIntake } from "./intake";

/**
 * A plan on its way to the server — `[2026-10-03 사용자 지시]` 「계획 확인하기」 moves to the progress screen at once instead
 * of waiting on the entry page for the server to answer.
 *
 * The entry page starts the sending (`beginIntake`) and navigates; the screen it opens (`intake-starting.tsx`) follows
 * `result`, draws the lines of the text being sent while it waits, and moves on to the intake's own page (the server's
 * progress stream, `watchIntake`) once the server has given the intake an id. The sending is held here, in memory, because
 * a page change cannot carry a file; a reload loses it and the screen sends the customer back to the entry page.
 */
export interface IntakeStart {
  text: string;
  files: File[];
  language: Language;
  /** The server's answer (`intake_id`), or its refusal. Already has a handler, so a failure nobody is waiting for is not "unhandled". */
  result: Promise<{ intake_id: string }>;
  /** The customer left before the server answered: stop waiting for it (an intake it already made stays unused). */
  cancel: () => void;
}

let current: IntakeStart | null = null;
/** A sending that failed: the entry page shows the server's sentence and gives the attached files back. */
let failure: { message: string; files: File[] } | null = null;

export function beginIntake(input: { text: string; files: File[]; language: Language; humanToken?: string | null }): IntakeStart {
  const controller = new AbortController();
  const result = submitIntake(input.text, input.files, input.language, input.humanToken, controller.signal);
  result.catch(() => undefined);
  failure = null;
  current = { text: input.text, files: input.files, language: input.language, result, cancel: () => controller.abort() };
  return current;
}

/** The sending in progress, or null (none was started, or the page was reloaded). */
export const intakeStart = (): IntakeStart | null => current;

/** The sending is over (answered, failed or given up): forget it, and the files with it. */
export function endIntakeStart(start: IntakeStart): void {
  if (current === start) current = null;
}

export function rememberIntakeFailure(start: IntakeStart, message: string): void {
  failure = { message, files: start.files };
}

export const intakeFailure = (): { message: string; files: File[] } | null => failure;
export function clearIntakeFailure(): void { failure = null; }
