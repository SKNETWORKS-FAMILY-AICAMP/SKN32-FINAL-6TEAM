import type { Language } from "../i18n";
import { API_BASE, userKey } from "./client";
import { eventStreamParser, type WatchEnd } from "./events";
import type { CheckLine, CheckResult, ItemRow, ReviewItem, ReviewMove, ReviewNeeds } from "./intake-review";

/**
 * The server's reading progress of one plan (`GET /v1/web/trip-intakes/{id}/events`, text/event-stream).
 *
 * ★Content events are **copies of state**, not commands: the same key (`line` source+no · `item` id · `check` item+row ·
 *   `move` from+to) arriving twice just overwrites. So a reconnect — which replays everything so far — and a repeat
 *   change nothing, and the order only has to be kept for what the customer sees appear first.
 * ★The server keeps no pace. A burst may arrive at once; the screen lines the events up and shows each for a moment
 *   (`features/intake-review/pacer.ts`). The truth is always `GET /v1/web/trip-intakes/{id}` — events only show how it
 *   came to be.
 * ★`EventSource` cannot send the `X-User-Key` header and the key must not go in the URL, so — like the trip bell —
 *   the stream is read with `fetch`.
 */

/** `state` of `accepted` · `stage` · `result` — the read progress only; the values come from the GET. */
export interface IntakeState {
  status: "reading" | "review" | "confirmed" | "fatal";
  stage: string;
  stage_label: string;
  revision: number;
  fatal_code: string | null;
  quiet_seconds: number | null;
}

/** An original line that was read (by the rules, or pointed at by the model), and the stop found on it. */
export interface StreamLine {
  source_id: string;
  no: number;
  text: string;
  found: { id: string; index: number; day: number | null; date: string | null; starts_at: string | null; title: string } | null;
}

/**
 * `[2026-10-03 사용자 지시]` 「어디까지 됐는지」를 알리는 작은 알림(`progress`). The server sends one each time a stop's place or hours check
 * finishes (`places` · `hours`) and for each leg (`moves`): `done` of `total` in that phase, and what it is at now. The screen shows exactly
 * this — no percentage of its own is made up from the rows it has drawn.
 */
export const PROGRESS_PHASES = ["places", "hours", "moves"] as const;
export type ProgressPhase = (typeof PROGRESS_PHASES)[number];
export interface ProgressPacket { phase: ProgressPhase; done: number; total: number; current: { id: string; title: string } | null }

export type IntakeStreamEvent =
  | { type: "accepted"; state: IntakeState | null }
  | { type: "stage"; stage: string; label: string; state: IntakeState | null }
  /** Every 3 s while the line is quiet. `slow` = a model or place lookup has been awaited for more than 8 s in this stage. */
  | { type: "beat"; stage: string; label: string; slow: boolean; elapsed: number }
  | { type: "line"; line: StreamLine }
  | { type: "item"; item: ReviewItem }
  | { type: "check"; item: string; line: CheckLine<ItemRow> }
  | { type: "move"; move: ReviewMove }
  | { type: "progress"; progress: ProgressPacket }
  | { type: "done"; revision: number; needs: ReviewNeeds; ready: boolean }
  | { type: "result"; state: IntakeState | null }
  | { type: "error"; code: string; message: string; retryable: boolean };

const RESULTS: readonly CheckResult[] = ["ok", "filled", "warn", "bad", "unknown"];
const ITEM_ROWS: readonly string[] = ["place", "time", "hours", "closed", "booking"];
const STATUSES = ["reading", "review", "confirmed", "fatal"];

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const num = (value: unknown, fallback = 0) => typeof value === "number" && Number.isFinite(value) ? value : fallback;
const maybeNum = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value : null;
const maybeText = (value: unknown) => typeof value === "string" ? value : null;

function parse(data: string): Record<string, unknown> | null {
  try {
    const body: unknown = data ? JSON.parse(data) : {};
    return isObject(body) ? body : null;
  } catch { return null; }
}

function toState(value: unknown): IntakeState | null {
  if (!isObject(value) || !STATUSES.includes(text(value.status))) return null;
  return {
    status: value.status as IntakeState["status"],
    stage: text(value.stage), stage_label: text(value.stage_label, text(value.stage)),
    revision: num(value.revision), fatal_code: maybeText(value.fatal_code), quiet_seconds: maybeNum(value.quiet_seconds),
  };
}

/** A check line from the wire. An unknown `result` word is read as `unknown` — never as "fine". */
export function toCheckLine<Row extends string>(value: unknown, rows: readonly string[]): CheckLine<Row> | null {
  if (!isObject(value) || !rows.includes(text(value.row))) return null;
  const result = RESULTS.includes(value.result as CheckResult) ? value.result as CheckResult : "unknown";
  return { row: value.row as Row, result, text: text(value.text) };
}

function toItem(body: Record<string, unknown>): ReviewItem | null {
  const id = text(body.id);
  if (!id) return null;
  const place = isObject(body.place) ? {
    name: text(body.place.name), latitude: maybeNum(body.place.latitude), longitude: maybeNum(body.place.longitude),
    source: maybeText(body.place.source), kind: maybeText(body.place.kind),
    content_id: maybeText(body.place.content_id), content_type_id: maybeText(body.place.content_type_id),
  } : null;
  const status = text(body.status);
  return {
    id, source_id: text(body.source_id), index: num(body.index), title: text(body.title), kind: maybeText(body.kind),
    day: maybeNum(body.day), date: maybeText(body.date), starts_at: maybeText(body.starts_at), ends_at: maybeText(body.ends_at),
    locked: body.locked === true, status: status === "keep" || status === "adjusted" || status === "review" ? status : null,
    can_lock: body.can_lock === true, place_state: (text(body.place_state, "unresolved")) as ReviewItem["place_state"],
    place, candidates_hint: maybeNum(body.candidates_hint),
  };
}

function toMove(body: Record<string, unknown>): ReviewMove | null {
  const from = text(body.from), to = text(body.to);
  if (!from || !to) return null;
  const rows = Array.isArray(body.rows) ? body.rows.map((row) => toCheckLine<"route" | "mode" | "arrival">(row, ["route", "mode", "arrival"])).filter((row) => row !== null) : [];
  const status = text(body.status);
  const mode = text(body.mode);
  return {
    from, to, day: maybeNum(body.day), date: maybeText(body.date),
    status: status === "keep" || status === "review" ? status : "waiting",
    mode: ["walk", "subway", "bus", "transit", "estimate"].includes(mode) ? mode as ReviewMove["mode"] : null,
    mode_label: maybeText(body.mode_label), minutes: maybeNum(body.minutes), km: maybeNum(body.km),
    depart: maybeText(body.depart), arrive: maybeText(body.arrive), slack_min: maybeNum(body.slack_min),
    basis: body.basis === "timetable" || body.basis === "estimate" ? body.basis : null,
    summary: text(body.summary), fare_krw: maybeNum(body.fare_krw), rows,
  };
}

/** One server-sent event block → an event, or null for what the screen does not use (or a body it cannot read). */
export function toIntakeEvent(name: string, data: string): IntakeStreamEvent | null {
  const body = parse(data);
  if (!body) return null;
  switch (name) {
    case "accepted": return { type: "accepted", state: toState(body.state) };
    case "stage": return { type: "stage", stage: text(body.stage), label: text(body.label, text(body.stage)), state: toState(body.state) };
    case "beat": return { type: "beat", stage: text(body.stage), label: text(body.label, text(body.stage)), slow: body.slow === true, elapsed: num(body.elapsed) };
    case "line": {
      const sourceId = text(body.source_id), no = num(body.no, -1);
      if (!sourceId || no < 1) return null;
      const found = isObject(body.found) && text(body.found.id) ? {
        id: text(body.found.id), index: num(body.found.index), day: maybeNum(body.found.day), date: maybeText(body.found.date),
        starts_at: maybeText(body.found.starts_at), title: text(body.found.title),
      } : null;
      return { type: "line", line: { source_id: sourceId, no, text: text(body.text), found } };
    }
    case "item": { const item = toItem(body); return item && { type: "item", item }; }
    case "check": {
      const line = toCheckLine<ItemRow>(body, ITEM_ROWS);
      return line && text(body.item) ? { type: "check", item: text(body.item), line } : null;
    }
    case "move": { const move = toMove(body); return move && { type: "move", move }; }
    case "progress": {
      const phase = PROGRESS_PHASES.find((name) => name === body.phase);
      const done = maybeNum(body.done), total = maybeNum(body.total);
      // A packet that does not make sense (an unknown phase, no numbers, more done than total) says nothing — it is not guessed at.
      if (!phase || done === null || total === null || done < 0 || total < 1 || done > total) return null;
      const current = isObject(body.current) && text(body.current.id) ? { id: text(body.current.id), title: text(body.current.title) } : null;
      return { type: "progress", progress: { phase, done: Math.floor(done), total: Math.floor(total), current } };
    }
    case "done": {
      const needs = isObject(body.needs) ? body.needs : {};
      return { type: "done", revision: num(body.revision), ready: body.ready === true,
        needs: { items: num(needs.items), moves: num(needs.moves), total: num(needs.total, num(needs.items) + num(needs.moves)) } };
    }
    case "result": return { type: "result", state: toState(body.state) };
    case "error": return { type: "error", code: text(body.code, "error"), message: text(body.message), retryable: body.retryable === true };
    default: return null;
  }
}

/** What the screen builds up from the events — each map is keyed the way the server keys its copies. */
export interface StreamState {
  stage: string | null;
  stageLabel: string | null;
  lines: Record<string, StreamLine>;
  items: Record<string, ReviewItem>;
  checks: Record<string, CheckLine<ItemRow>>;
  moves: Record<string, ReviewMove>;
  /** First-arrival order of the keys above (`line:` · `item:` · `check:` · `move:` prefixed) — what appeared first is shown first. */
  order: string[];
  done: { revision: number; needs: ReviewNeeds; ready: boolean } | null;
  /** The latest `progress` packet of each phase (the server keeps one value per phase and overwrites it — places come while it reads, hours and moves while it checks). */
  phases: Partial<Record<ProgressPhase, ProgressPacket>>;
  /** What the screen shows: the packet of the furthest phase that has come. Null until one has. */
  progress: ProgressPacket | null;
}

export const emptyStream = (): StreamState => ({ stage: null, stageLabel: null, lines: {}, items: {}, checks: {}, moves: {}, order: [], done: null, phases: {}, progress: null });

/** The packet of the furthest phase present (places < hours < moves) — a replay after a reconnect brings every phase's last value in any order. */
function furthest(phases: StreamState["phases"]): ProgressPacket | null {
  for (let at = PROGRESS_PHASES.length - 1; at >= 0; at -= 1) { const packet = phases[PROGRESS_PHASES[at]]; if (packet) return packet; }
  return null;
}

export const lineKey = (line: Pick<StreamLine, "source_id" | "no">) => `${line.source_id}:${line.no}`;
export const checkKey = (item: string, row: string) => `${item}:${row}`;
export const moveKey = (move: Pick<ReviewMove, "from" | "to">) => `${move.from}:${move.to}`;

function put<T>(state: StreamState, kind: "line" | "item" | "check" | "move", bucket: Record<string, T>, key: string, value: T): Record<string, T> {
  if (!(key in bucket)) state.order.push(`${kind}:${key}`);
  return { ...bucket, [key]: value };
}

/** Apply one event (a copy of state, so applying it twice gives the same result). Returns a new state; the old one is left alone. */
export function reduceStream(previous: StreamState, event: IntakeStreamEvent): StreamState {
  const state: StreamState = { ...previous, order: [...previous.order] };
  switch (event.type) {
    case "stage": return { ...state, stage: event.stage, stageLabel: event.label };
    case "accepted": return event.state ? { ...state, stage: event.state.stage, stageLabel: event.state.stage_label } : previous;
    case "line": return { ...state, lines: put(state, "line", state.lines, lineKey(event.line), event.line) };
    case "item": return { ...state, items: put(state, "item", state.items, event.item.id, event.item) };
    case "check": return { ...state, checks: put(state, "check", state.checks, checkKey(event.item, event.line.row), event.line) };
    case "move": return { ...state, moves: put(state, "move", state.moves, moveKey(event.move), event.move) };
    case "progress": {
      const before = previous.phases[event.progress.phase];
      // Same phase, same total, fewer done: an older packet arriving late — the count never steps back. A different total is a new count (the next source).
      if (before && before.total === event.progress.total && before.done > event.progress.done) return previous;
      const phases = { ...previous.phases, [event.progress.phase]: event.progress };
      return { ...state, phases, progress: furthest(phases) };
    }
    case "done": return { ...state, done: { revision: event.revision, needs: event.needs, ready: event.ready } };
    default: return previous;                      // beat · result · error change nothing the screen builds
  }
}

/** Open the reading progress of one plan and call `onEvent` until the stream ends or `signal` aborts. Never throws. */
export async function watchIntake(intakeId: string, language: Language, onEvent: (event: IntakeStreamEvent) => void, signal: AbortSignal): Promise<WatchEnd> {
  let response: Response;
  try {
    const key = await userKey(language);
    response = await fetch(`${API_BASE}/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/events`, {
      headers: { "X-User-Key": key, Accept: "text/event-stream" },
      cache: "no-store",
      signal,
    });
  } catch {
    return signal.aborted ? "closed" : "failed";
  }
  // Refused before the stream opened (not yours · too many open streams · …) is an ordinary HTTP error with a JSON body.
  if (response.status === 404 || response.status === 405) return "unsupported";
  if (!response.ok || !response.body) return "failed";
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  const feed = eventStreamParser((name, data) => {
    const event = toIntakeEvent(name, data);
    if (event) onEvent(event);
  });
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return "closed";
      feed(value);
    }
  } catch {
    return signal.aborted ? "closed" : "failed";
  }
}
