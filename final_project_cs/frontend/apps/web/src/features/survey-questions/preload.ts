import type { Language } from "@/lib/i18n";
import { submitSurveyAnswers, type IntakeSurveyAnswer } from "@/lib/live/intake";

const preloads = new Map<string, Promise<void>>();

/**
 * `[2026-10-20 ST4F-665]` Lay what the customer already answered (`startAnswers`) on a new intake, once, before the page reads it: the server fixes the list of loading questions at the
 * intake's first read and leaves an answered question out (`web-intakes.md` 「설문 질문」 고르는 규칙 1), so the start survey is not asked again.
 * The same intake gets one call however often this runs (a page drawn twice). Nothing to lay on: nothing is sent.
 * ★A call the server refuses (or that does not arrive) is not retried and does not stop the page: the server then holds none of these answers, so it asks those questions while it
 *   reads - what the page did before this existed - and the registration's own survey still carries them (`confirmIntake`).
 */
export function preloadAnswers(intakeId: string, answers: Record<string, IntakeSurveyAnswer>, language: Language): Promise<void> {
  if (Object.keys(answers).length === 0) return Promise.resolve();
  let sending = preloads.get(intakeId);
  if (!sending) {
    sending = submitSurveyAnswers(intakeId, answers, language).then(() => undefined, () => undefined);
    preloads.set(intakeId, sending);
  }
  return sending;
}
