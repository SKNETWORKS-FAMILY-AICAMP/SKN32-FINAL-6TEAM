/**
 * The registration page's three ways to give a plan (`[2026-10-03 사용자 결정]`, live only):
 *   text  — 직접 입력 (the text box)
 *   files — 파일 선택
 *   plan  — 계획 짜 주기 (테스트): the server plans from a first day, a number of days and a number of travelers
 *
 * ★The panel the customer touched last is the one that is sent — and only that one (text → the text, files → the files, plan → its
 * conditions). If that panel is empty, 「계획 확인하기」 stays off and says why. The earlier rule — "an empty plan is not an error, it
 * goes on to a screen that offers to plan" (`[2026-09-30]`) — is replaced by this.
 */
export type RegistrationPane = "text" | "files" | "plan";

/** `days` · `party` are 0 until chosen. */
export interface PlanAsk { start: string; days: number; party: number; wish: string }
export const emptyAsk: PlanAsk = { start: "", days: 0, party: 0, wish: "" };

/** The server plans 1 to 7 days for 1 to 4 travelers (`POST …/plan`). */
export const PLAN_DAYS = [1, 2, 3, 4, 5, 6, 7] as const;
export const PLAN_PARTY = [1, 2, 3, 4] as const;
/** The wish is a short sentence about the trip; the long text is the other panel's job. */
export const WISH_MAX = 500;

export interface PaneValues { text: string; files: number; ask: PlanAsk }

/** Today's date in Seoul as `YYYY-MM-DD` — the earliest first day the server can plan from. */
export function seoulToday(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  const part = (type: string) => parts.find((entry) => entry.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

/** A calendar date written `YYYY-MM-DD` that exists (not 2026-02-30). */
export function isRealDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

export type AskProblem = "start" | "past" | "days" | "party";

/** What is missing from the planning conditions, first thing first; null when all three are chosen. `today` empty = not known yet (no date check). */
export function askProblem(ask: PlanAsk, today: string): AskProblem | null {
  if (!isRealDate(ask.start)) return "start";
  if (today && ask.start < today) return "past";
  if (!PLAN_DAYS.some((days) => days === ask.days)) return "days";
  if (!PLAN_PARTY.some((party) => party === ask.party)) return "party";
  return null;
}

/** Whether the panel the customer chose has something to send: text — one letter besides spaces; files — one file; plan — all three conditions. */
export function paneReady(active: RegistrationPane, values: PaneValues, today: string): boolean {
  if (active === "text") return values.text.trim().length > 0;
  if (active === "files") return values.files > 0;
  return askProblem(values.ask, today) === null;
}

/** Why 「계획 확인하기」 is off, as `[ko, en]` for `t(...)`; null when the chosen panel is ready. */
export function paneReason(active: RegistrationPane, values: PaneValues, today: string): [string, string] | null {
  if (paneReady(active, values, today)) return null;
  if (active === "text") return ["위에서 고른 「직접 입력」 칸에 내용을 넣어 주세요.", "Write something in the “Type it in” box you chose above."];
  if (active === "files") return ["위에서 고른 「파일 선택」 칸에 파일을 하나 이상 골라 주세요.", "Choose at least one file in the “Choose files” box you picked above."];
  if (askProblem(values.ask, today) === "past") return ["위에서 고른 「계획 짜 주기」 칸의 첫날은 오늘(서울 기준)이거나 그 뒤여야 해요.", "In the “Plan it for me” box you chose, the first day must be today (Seoul time) or later."];
  return ["위에서 고른 「계획 짜 주기」 칸에서 첫날 · 일수 · 인원을 모두 골라 주세요.", "In the “Plan it for me” box you chose, pick the first day, the days and the travelers."];
}

/** Which panel a sending came from, to give it back its highlight when the server refused: a plan → plan, files → files, otherwise the text. */
export function paneOfSending(sent: { plan: unknown; files: readonly unknown[] }): RegistrationPane {
  return sent.plan ? "plan" : sent.files.length > 0 ? "files" : "text";
}
