import type { Language } from "../i18n";
import { api, LiveError } from "./client";
import type { Review } from "./intake-review";

/**
 * `[2026-10-07 사용자 지시 — 이동수단 고르기]` For one leg of the checked plan the server says how each way (subway · bus · taxi · walking) would do - how long, what it costs, how much time is left before the next stop
 * starts - and the customer picks one that reaches in time. Contract: `wiki/records/plans/2026-10-05_이동수단_선택_서버계약안.md` (the mobility session's proposal; ★the server did not have it when this was
 * written - the screen is built against the proposal and shown only where the server answers).
 *
 * ★Nothing is made up here: a way the screen does not know is dropped, an option the server could not finish (`fits: null`) is not a late one, a fare the server could not give is 「요금 미상」,
 * and the reason a way cannot be picked is the server's own sentence.
 */
export type MoveOptionMode = "subway" | "bus" | "taxi" | "walk";
const MODES: readonly MoveOptionMode[] = ["subway", "bus", "taxi", "walk"];

export interface MoveOption {
  mode: MoveOptionMode;
  /** The server's name for it (「지하철 2호선」); the way's own name when it sent none. */
  label: string;
  minutes: number | null;
  km: number | null;
  /** Won; null = the server could not give it (shown as 「요금 미상」). A walk is 0. */
  fareKrw: number | null;
  /** A taxi fare is the lowest it can be (shown with 「~」), never the exact one. */
  fareIsFloor: boolean;
  fareIsEstimate: boolean;
  depart: string | null;
  arrive: string | null;
  /** Minutes left before the next stop starts; negative = late. */
  slackMin: number | null;
  /** `true` reaches in time and was confirmed · `false` does not · `null` the server could not finish it (not the same as late). */
  fits: boolean | null;
  /** The server's sentence for why this one cannot be picked. */
  whyNot: string | null;
  basis: "timetable" | "estimate" | null;
  grade: "확정" | "추정" | "근거없음" | null;
}

export interface MoveOptions {
  revision: number | null;
  /** The way the checked plan uses now, and the way the calculator chose (it stays when the customer picks another). */
  currentMode: string | null;
  recommendedMode: string | null;
  options: MoveOption[];
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value.trim() : null);
const number = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);

/** The names the screen gives a way when the server sends no label. */
export const MODE_WORDS: Record<MoveOptionMode, [string, string]> = { subway: ["지하철", "Subway"], bus: ["버스", "Bus"], taxi: ["택시", "Taxi"], walk: ["걸음", "Walk"] };

/** The server's sentence of a refused pick (`422 mode_not_fit` carries it as `why`), else the refusal's own sentence. */
export function refusalWhy(error: unknown): string | null {
  if (!(error instanceof LiveError)) return null;
  const why = (error.detail as { why?: unknown } | undefined)?.why;
  return typeof why === "string" && why.trim() ? why.trim() : error.message;
}

/** The answer of `GET …/options`; anything that is not one reads as none. */
export function moveOptionsOf(raw: unknown): MoveOptions | null {
  if (!isRecord(raw)) return null;
  const options = (Array.isArray(raw.options) ? raw.options : []).flatMap((entry): MoveOption[] => {
    if (!isRecord(entry)) return [];
    const mode = MODES.find((value) => value === entry.mode);
    if (!mode) return [];                                                  // a way the screen does not know is not shown
    const slackMin = number(entry.slack_min);
    // `fits` the server did not say: it reaches when nothing is late. One it explicitly says `null` for is unknown, never late.
    const fits = typeof entry.fits === "boolean" ? entry.fits : entry.fits === null ? null : slackMin !== null ? slackMin >= 0 : null;
    const grade = entry.grade === "확정" || entry.grade === "추정" || entry.grade === "근거없음" ? entry.grade : null;
    return [{
      mode, label: text(entry.label) ?? MODE_WORDS[mode][0], minutes: number(entry.minutes), km: number(entry.km), fareKrw: number(entry.fare_krw),
      fareIsFloor: entry.fare_is_floor === true, fareIsEstimate: entry.fare_is_estimate === true,
      depart: text(entry.depart), arrive: text(entry.arrive), slackMin, fits, whyNot: text(entry.why_not),
      basis: entry.basis === "timetable" || entry.basis === "estimate" ? entry.basis : null, grade,
    }];
  });
  return { revision: number(raw.revision), currentMode: text(raw.current_mode), recommendedMode: text(raw.recommended_mode), options };
}

const pair = (from: string, to: string) => `${encodeURIComponent(from)}~${encodeURIComponent(to)}`;

/**
 * `GET /v1/web/trip-intakes/{id}/moves/{from}~{to}/options`: the ways for one leg, or null when the server has nothing to offer for it (a server without the feature, a leg that is not
 * calculated: 404). Only a leg is asked, only when the customer opens the box - a whole plan of them would be dozens of calculations.
 */
export async function getMoveOptions(intakeId: string, fromId: string, toId: string, language: Language, revision?: number | null): Promise<MoveOptions | null> {
  // `[2026-10-07 이동 세션 구현]` The server takes the revision the screen shows (`?revision=`) and answers for it.
  const asked = typeof revision === "number" ? `?revision=${revision}` : "";
  try {
    return moveOptionsOf(await api<unknown>(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/moves/${pair(fromId, toId)}/options${asked}`, language));
  } catch (error) {
    if (error instanceof LiveError && (error.status === 404 || error.status === 405)) return null;
    throw error;
  }
}

/**
 * `[2026-10-23 사용자 지시 — 경로 후보 먼저 3개 · 목록을 내리면 더]` One route the calculator found for a leg: the lines ridden (「3호선 → 2호선」), how long, when to leave and arrive, the time left.
 * The checked plan carries the first three of each leg (`moves[].routes`, the same calculation - no wait); the rest come from `GET …/routes` when the list is scrolled to its end.
 * `early` = it leaves before the plan's departure (still after the stop before ends). `key` is what is sent back to take it.
 */
export interface MoveRoute {
  key: string;
  mode: string;
  modeLabel: string;
  label: string;
  minutes: number | null;
  depart: string | null;
  arrive: string | null;
  slackMin: number | null;
  fareKrw: number | null;
  walkM: number | null;
  transfers: number | null;
  lines: string[];
  planned: boolean;
  early: boolean;
}

/** One `routes[]` entry of the server; one without a key is not shown (it could not be taken). */
export function moveRouteOf(raw: unknown): MoveRoute | null {
  if (!isRecord(raw)) return null;
  const key = text(raw.key);
  if (!key) return null;
  const lines = Array.isArray(raw.lines) ? raw.lines.flatMap((line) => (text(line) ? [text(line) as string] : [])) : [];
  return {
    key, mode: text(raw.mode) ?? "transit", modeLabel: text(raw.mode_label) ?? "", label: text(raw.label) ?? "", minutes: number(raw.minutes),
    depart: text(raw.depart), arrive: text(raw.arrive), slackMin: number(raw.slack_min), fareKrw: number(raw.fare_krw), walkM: number(raw.walk_m),
    transfers: number(raw.transfers), lines, planned: raw.planned === true, early: raw.early === true,
  };
}

export const moveRoutesOf = (raw: unknown): MoveRoute[] => (Array.isArray(raw) ? raw.flatMap((entry) => { const route = moveRouteOf(entry); return route ? [route] : []; }) : []);

export interface MoveRoutesPage { routes: MoveRoute[]; nextOffset: number; hasMore: boolean; total: number | null; why: string | null }

/**
 * `GET /v1/web/trip-intakes/{id}/moves/{from}~{to}/routes?offset=&limit=`: the routes after the ones shown (`offset` = how many are on the screen). The server counts the leg once more with more
 * routes allowed (about 0.6-2.2 s on a test PC, 2026-10-23). null = the server has nothing for this leg (an older server: 404/405). An empty page with `why` and `hasMore` = it ran out of time; ask again.
 */
export async function getMoveRoutes(intakeId: string, fromId: string, toId: string, offset: number, limit: number, language: Language, revision?: number | null): Promise<MoveRoutesPage | null> {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (typeof revision === "number") query.set("revision", String(revision));
  try {
    const raw = await api<unknown>(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/moves/${pair(fromId, toId)}/routes?${query.toString()}`, language);
    if (!isRecord(raw)) return null;
    const routes = moveRoutesOf(raw.routes);
    return { routes, nextOffset: number(raw.next_offset) ?? offset + routes.length, hasMore: raw.has_more === true, total: number(raw.total), why: text(raw.why) };
  } catch (error) {
    if (error instanceof LiveError && (error.status === 404 || error.status === 405)) return null;
    throw error;
  }
}

/**
 * `[2026-10-23 사용자 지시 — 배포 직후 첫 「더 보기」]` How long the screen waits before asking once more by itself when the server answered 「it took too long」 (an empty page with `why` and `hasMore`).
 * The server keeps counting after it answers and keeps the result, so the second ask is quick (x600 right after a deploy: 25 s and nothing, asked again 6 s and five routes; warm about 1 s).
 */
export const ROUTES_RETRY_MS = 3_000;

/** Ask the same page again by itself: only for an empty page the server could not finish in time, and only once (a second one waits for 「다시 불러오기」). */
export function retryRoutesPage(page: MoveRoutesPage | null, retried: boolean): boolean {
  return !retried && page !== null && page.routes.length === 0 && page.why !== null && page.hasMore;
}

/** `POST …/route` `{revision, key}` (`"recommended"` = back to the calculator's route): the server counts the leg again and takes the route only if it is still there and reaches in time; it answers with the whole plan. */
export async function setMoveRoute(intakeId: string, fromId: string, toId: string, revision: number, key: string, language: Language): Promise<{ revision: number; review: Review }> {
  const body = await api<{ revision?: unknown; review?: unknown }>(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/moves/${pair(fromId, toId)}/route`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, key }),
  });
  if (!isRecord(body.review) || typeof body.revision !== "number") throw new LiveError("bad_answer", "The server did not send the plan back");
  return { revision: body.revision, review: body.review as unknown as Review };
}

/** What became of the customer's route after the stops around the leg changed: kept, or back to the recommended route (with the reason). */
export interface RouteChoice { key: string | null; state: "kept" | "dropped" | null; why: string | null }

export function routeChoiceOf(raw: unknown): RouteChoice | null {
  if (!isRecord(raw)) return null;
  return { key: text(raw.key), state: raw.state === "kept" || raw.state === "dropped" ? raw.state : null, why: text(raw.why) };
}

/** What 「…」 the server wrote about a leg's choice after a change of the stops around it: the choice was kept, or went back to the recommendation (with the reason). */
export interface ModeChoice { mode: string | null; state: "kept" | "dropped" | null; why: string | null }

export function modeChoiceOf(raw: unknown): ModeChoice | null {
  if (!isRecord(raw)) return null;
  return { mode: text(raw.mode), state: raw.state === "kept" || raw.state === "dropped" ? raw.state : null, why: text(raw.why) };
}

/**
 * `POST …/mode` `{revision, mode}` (`"recommended"` = back to what the calculator chose): the server counts the leg again with that way and takes it only if it reaches in time; it answers with
 * the whole checked plan, which is what the screen shows from then on (no 「다시 제출」 is needed). A refusal is a `LiveError`: 409 `stale_revision` (the plan moved on), 422 `mode_not_fit`
 * (with the server's `why`), 404.
 */
export async function setMoveMode(
  intakeId: string, fromId: string, toId: string, revision: number, mode: MoveOptionMode | "recommended", language: Language,
): Promise<{ revision: number; review: Review }> {
  const body = await api<{ revision?: unknown; review?: unknown }>(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/moves/${pair(fromId, toId)}/mode`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, mode }),
  });
  if (!isRecord(body.review) || typeof body.revision !== "number") throw new LiveError("bad_answer", "The server did not send the plan back");
  return { revision: body.revision, review: body.review as unknown as Review };
}
