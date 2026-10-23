import type { Translate } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import type { IntakeDiningJudge, ReviewedIntakeView } from "@/lib/live/intake-review";

/** An old revision's result must not control the current plan's polling or button. */
export function currentDiningJudge(view: ReviewedIntakeView | undefined): IntakeDiningJudge | null {
  // Dry runs are not saved and have no worker whose result the screen can poll.
  if (view?.preview) return null;
  const judge = view?.review?.dining_judge;
  return judge && judge.revision === view?.revision ? judge : null;
}

export const diningPending = (judge: IntakeDiningJudge | null | undefined): boolean => judge?.status === "pending" || judge?.status === "running";

/** The dining worker has no reading SSE: follow it even when that stream has closed. */
export function intakeRefetchInterval(view: ReviewedIntakeView | undefined, readingPolling: boolean, error: unknown): 1500 | false {
  if (error || !view) return false;
  if (view.status === "reading") return readingPolling ? 1500 : false;
  return view.status === "review" && diningPending(currentDiningJudge(view)) ? 1500 : false;
}

export function refreshIntakeAfter(error: unknown): boolean {
  return error instanceof LiveError && ["stale_revision", "intake_dining_check_pending", "intake_dining_check_failed", "intake_dining_conditions_unmet"].includes(error.code);
}

/** These flags come from verified server evidence; warning/unknown rows stay advisory. */
export function diningRegistrationProblems(view: ReviewedIntakeView | undefined): string[] {
  return (view?.review?.items ?? []).flatMap((item) => (item.rows ?? [])
    .filter((line) => line.result === "bad" && line.blocks_registration === true)
    .map((line) => `${item.place?.name ?? item.title}: ${line.text}`));
}

export function intakeRegistrationReady(view: ReviewedIntakeView | undefined, baseReady?: boolean): boolean {
  const judge = currentDiningJudge(view);
  return Boolean(baseReady ?? (view?.review ? view.review.ready : view?.check?.ready)) && !diningPending(judge)
    && judge?.blocks_registration !== true && diningRegistrationProblems(view).length === 0;
}

export function diningStatusText(judge: IntakeDiningJudge | null | undefined, t: Translate): string | null {
  if (diningPending(judge)) return t("식당 이용 조건을 확인하고 있어요 · 완료되면 이 화면에 반영해요", "Checking restaurant conditions · results will appear here");
  if (judge?.status === "failed") return t("식당 이용 조건을 확인하지 못했어요 · 원하시면 다시 확인해 주세요", "Restaurant conditions could not be checked · use Recheck if you wish");
  return null;
}

export function diningRegistrationReason(view: ReviewedIntakeView | undefined, t: Translate): string | null {
  const judge = currentDiningJudge(view);
  if (diningPending(judge)) return diningStatusText(judge, t);
  return judge?.blocks_registration || diningRegistrationProblems(view).length
    ? t("식당 필수 조건에 맞지 않는 항목을 먼저 고쳐 주세요", "Fix the restaurant stops that do not meet required conditions first") : null;
}

export interface RegistrationIntent { intakeId: string; revision: number; runId: string | null }

/** A preview's single register action waits for the real applied revision, without retrying a save. */
export function registrationIntentDecision(intent: RegistrationIntent, view: ReviewedIntakeView | undefined, error: unknown,
  canRegister: (view: ReviewedIntakeView) => boolean = intakeRegistrationReady): "wait" | "register" | "cancel" {
  if (error || !view || view.intake_id !== intent.intakeId || view.revision !== intent.revision || view.status !== "review") return "cancel";
  const judge = currentDiningJudge(view);
  if (!judge || (intent.runId !== null && judge.run_id !== intent.runId)) return "cancel";
  if (diningPending(judge)) return "wait";
  return canRegister(view) ? "register" : "cancel";
}
