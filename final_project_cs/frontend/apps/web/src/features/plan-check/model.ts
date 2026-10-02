import type { Coordinates } from "@/features/map/model";

/**
 * The plan-check screen (after 「계획 확인하기」), built from the mockup `mockups/tripilot-plan-check-streaming.html`.
 *
 * ★This file is the screen's data contract. The screen draws a `PlanCheckView` snapshot and nothing else; it never calls
 *   the server. Wiring it to the server (`GET /v1/web/trip-intakes/{id}`, its `…/events` stream, or what the backend
 *   agrees) is the backend's part (2026-10-03 user decision). The mockup's 「진행 이벤트 예시」 maps onto these fields.
 */

/** One check's result (mockup `result`): passed · filled in by the server · warning · must fix · not known yet · not checked yet. */
export type CheckResult = "ok" | "filled" | "warn" | "bad" | "unknown" | "pending";
/** Place checks: place · time · hours · closed. Move checks: route · mode · arrival. */
export type CheckKind = "place" | "time" | "hours" | "closed" | "route" | "mode" | "arrival";
export interface CheckRow { kind: CheckKind; result: CheckResult; text: string }

/** A card's verdict once its checks are in. Null while it is still being checked. */
export type Verdict = "keep" | "adjusted" | "review";

export interface PlanItem {
  id: string;
  day: number;
  /** "HH:MM" */
  startsAt: string;
  title: string;
  /** Null when the place is not settled — it shows as 「위치 미정」 instead of a pin. */
  coordinates: Coordinates | null;
  checks: CheckRow[];
  verdict: Verdict | null;
}

/** The way from one place to the next on the same day. */
export interface PlanMove {
  id: string;
  fromId: string;
  toId: string;
  day: number;
  /** "HH:MM" — leave at. */
  departAt: string;
  /** As the server words it, e.g. 「도보」 · 「지하철」. */
  mode: string;
  /** One line, e.g. 「12분 · 0.8km」. */
  summary: string;
  checks: CheckRow[];
  verdict: Verdict | null;
}

/** What a line of the uploaded plan turned into: the trip's date, a stop, or nothing. */
export type LineFinding = { kind: "date"; date: string } | { kind: "item"; day: number; startsAt: string; title: string };
export interface PlanLine { no: number; text: string; read: boolean; found: LineFinding | null }

export interface PlanDay { day: number; /** "YYYY-MM-DD" */ date: string }

/** received → reading (lines) → checking (places, hours, moves) → done. */
export type PlanStage = "received" | "reading" | "checking" | "done";
export const STAGES: readonly PlanStage[] = ["received", "reading", "checking", "done"];

export interface PlanCheckView {
  stage: PlanStage;
  /** The trip's title once the check is done. */
  title: string | null;
  days: PlanDay[];
  lines: PlanLine[];
  /** In itinerary order within each day. */
  items: PlanItem[];
  moves: PlanMove[];
}

const stageIndex = (stage: PlanStage) => STAGES.indexOf(stage);

/** Items and moves of one day in the order they are lived: item, move, item … */
export function timeline(view: Pick<PlanCheckView, "items" | "moves">, day: number): ({ type: "item"; item: PlanItem } | { type: "move"; move: PlanMove })[] {
  const out: ({ type: "item"; item: PlanItem } | { type: "move"; move: PlanMove })[] = [];
  for (const item of view.items.filter((entry) => entry.day === day)) {
    out.push({ type: "item", item });
    const move = view.moves.find((entry) => entry.fromId === item.id);
    if (move) out.push({ type: "move", move });
  }
  return out;
}

/** Every item and move in check order: day by day, along each day's timeline. */
function checkOrder(view: PlanCheckView): ({ type: "item"; id: string } | { type: "move"; id: string })[] {
  const days = [...new Set(view.items.map((item) => item.day))].sort((a, b) => a - b);
  return days.flatMap((day) => timeline(view, day).map((entry) => entry.type === "item" ? { type: "item" as const, id: entry.item.id } : { type: "move" as const, id: entry.move.id }));
}

const pendingCopy = <T extends { checks: CheckRow[]; verdict: Verdict | null }>(entity: T): T =>
  ({ ...entity, checks: entity.checks.map((row) => ({ ...row, result: "pending" as const, text: "" })), verdict: null });

/**
 * One visible change from `shown` toward `target`, or null when they already match.
 *
 * ★The server says what happened and in which order; the screen decides the pace. However many changes arrive at once
 *   (a stream burst, or a re-read after a poll), they are drawn one at a time in this order: reading starts → each line
 *   read → the days → checking starts → each place or move along the day (appear with its checks waiting → each check → its
 *   verdict) → done → title.
 *   Anything the screen cannot step toward (something removed, a line changed) jumps straight to `target`.
 */
export function nextStep(shown: PlanCheckView, target: PlanCheckView): PlanCheckView | null {
  if (JSON.stringify(shown) === JSON.stringify(target)) return null;
  const jump = () => target;
  if (stageIndex(target.stage) < stageIndex(shown.stage)) return jump();
  if (shown.lines.length > target.lines.length || shown.items.some((item) => !target.items.some((other) => other.id === item.id))
    || shown.moves.some((move) => !target.moves.some((other) => other.id === move.id))) return jump();

  // Reading starts before the first line is read, so the bar moves with the lines.
  if (shown.stage === "received" && target.stage !== "received") return { ...shown, stage: "reading" };
  // Lines: a line appears or is read, one at a time.
  for (let index = 0; index < target.lines.length; index += 1) {
    const want = target.lines[index], have = shown.lines[index];
    if (!have) return { ...shown, lines: [...shown.lines, { ...want, read: false, found: null }] };
    if (have.no !== want.no || have.text !== want.text || (have.read && !want.read)) return jump();
    if (!have.read && want.read) return { ...shown, lines: shown.lines.map((line, at) => at === index ? want : line) };
    if (JSON.stringify(have.found) !== JSON.stringify(want.found)) return { ...shown, lines: shown.lines.map((line, at) => at === index ? want : line) };
  }
  // The trip's days come with the reading; checking starts once every line is read.
  if (JSON.stringify(shown.days) !== JSON.stringify(target.days)) return { ...shown, days: target.days };
  if (shown.stage === "reading" && stageIndex(target.stage) > stageIndex("reading")) return { ...shown, stage: "checking" };

  // Places and moves along each day: appear (checks waiting) → each check → verdict.
  for (const entry of checkOrder(target)) {
    if (entry.type === "item") {
      const want = target.items.find((item) => item.id === entry.id)!;
      const have = shown.items.find((item) => item.id === entry.id);
      const step = advance(have, want);
      if (step === undefined) continue;
      const items = have ? shown.items.map((item) => item.id === want.id ? step : item) : insertInOrder(shown.items, step, target.items);
      return { ...shown, items };
    }
    const want = target.moves.find((move) => move.id === entry.id)!;
    const have = shown.moves.find((move) => move.id === entry.id);
    const step = advance(have, want);
    if (step === undefined) continue;
    const moves = have ? shown.moves.map((move) => move.id === want.id ? step : move) : [...shown.moves, step];
    return { ...shown, moves };
  }
  // Done only once every check is in, then the title.
  if (stageIndex(shown.stage) < stageIndex(target.stage)) return { ...shown, stage: STAGES[stageIndex(shown.stage) + 1] };
  if (shown.title !== target.title) return { ...shown, title: target.title };
  return jump();
}

/** The next state of one place or move toward `want`, or undefined when it already matches. */
function advance<T extends { checks: CheckRow[]; verdict: Verdict | null }>(have: T | undefined, want: T): T | undefined {
  if (!have) return pendingCopy(want);
  if (JSON.stringify(have) === JSON.stringify(want)) return undefined;
  if (have.checks.length !== want.checks.length || have.checks.some((row, at) => row.kind !== want.checks[at].kind)) return want;
  const at = have.checks.findIndex((row, index) => JSON.stringify(row) !== JSON.stringify(want.checks[index]));
  if (at >= 0) return { ...have, checks: have.checks.map((row, index) => index === at ? want.checks[at] : row) };
  return { ...have, ...want };
}

/** Put `item` where it stands in `order` (the server's order), among the items already shown. */
function insertInOrder(items: PlanItem[], item: PlanItem, order: PlanItem[]): PlanItem[] {
  const rank = (id: string) => order.findIndex((entry) => entry.id === id);
  return [...items, item].sort((a, b) => rank(a.id) - rank(b.id));
}

/**
 * How many places and moves there will be. Places come from the lines read (a line that turned into a stop), moves from
 * the stops of each day (one between two stops) — so the counts and the bar know the whole before every card is shown.
 * What the screen already shows counts when it is more.
 */
export function expected(view: Pick<PlanCheckView, "lines" | "items" | "moves">): { places: number; moves: number } {
  const stops = view.lines.flatMap((line) => line.read && line.found?.kind === "item" ? [line.found.day] : []);
  const perDay = [...new Set(stops)].map((day) => stops.filter((value) => value === day).length);
  return { places: Math.max(view.items.length, stops.length), moves: Math.max(view.moves.length, perDay.reduce((sum, count) => sum + Math.max(0, count - 1), 0)) };
}

/** 0–100 along the four steps. Within reading it follows the lines read; within checking, the places and moves done. */
export function progress(view: PlanCheckView): number {
  const third = 100 / 3;
  if (view.stage === "received") return 0;
  if (view.stage === "done") return 100;
  if (view.stage === "reading") return view.lines.length ? third * view.lines.filter((line) => line.read).length / view.lines.length : 0;
  const total = expected(view);
  const all = total.places + total.moves;
  const done = [...view.items, ...view.moves].filter((entity) => entity.verdict !== null).length;
  return third + (all ? third * Math.min(done, all) / all : 0);
}

export interface Tally { places: number; placesDone: number; moves: number; movesDone: number; placesReview: number; movesReview: number }

export function tally(view: Pick<PlanCheckView, "lines" | "items" | "moves">): Tally {
  const total = expected(view);
  return {
    places: total.places,
    placesDone: view.items.filter((item) => item.verdict !== null).length,
    moves: total.moves,
    movesDone: view.moves.filter((move) => move.verdict !== null).length,
    placesReview: view.items.filter((item) => item.verdict === "review").length,
    movesReview: view.moves.filter((move) => move.verdict === "review").length,
  };
}

/** Lines that turned into a stop, among those read so far. */
export const foundCount = (view: Pick<PlanCheckView, "lines">) => view.lines.filter((line) => line.read && line.found?.kind === "item").length;
