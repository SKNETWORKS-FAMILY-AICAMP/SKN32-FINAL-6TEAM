import { doneLine } from "./chat-cards";
import type { TripStop } from "./model";

/**
 * `[2026-10-22 사용자 결정 — ST4F-719 · 목업 ⓑ]` What a change made from the chat changed, side by side (before → after). The server's answer names only the new values (「· 10월 24일(금)
 * 12:00~13:00 광장시장 점심」), so the screen compares the plan it had just before sending with the plan it read after. Only this tab knows the plan before: kept per change version in this
 * tab's session (as the undo of that change is), another tab or device shows the answer's text only.
 * `line`: what the server's answer writes for that stop after the change (`chat_edit.done_text`) — the card shows it, so the answer leaves that line out when it is the same.
 */
export interface ChatDiffRow { id: string; title: string; before: string; after: string; kind: "time" | "place"; line: string }
export interface ChatDiff { rows: ChatDiffRow[]; keep: { id: string; title: string; time: string }[] }

const range = (stop: TripStop) => stop.endTime ? `${stop.time}~${stop.endTime}` : stop.time;
const placeOf = (stop: TripStop) => stop.place ?? stop.title;

/**
 * The stops a change touched: same stop with another time or place; a stop taken out and another put in at the same day and time is one place change. The first stop after the last
 * change on that day that stayed as it was is 「그대로」 (`keep`). Null when nothing a customer sees changed.
 */
export function diffStops(before: readonly TripStop[], after: readonly TripStop[]): ChatDiff | null {
  const old = new Map(before.map((stop) => [stop.id, stop]));
  const now = new Set(after.map((stop) => stop.id));
  const rows: ChatDiffRow[] = [];
  const touched = new Set<string>();
  for (const stop of after) {
    const was = old.get(stop.id);
    if (!was) {
      const replaced = before.find((other) => !now.has(other.id) && other.date === stop.date && other.time === stop.time);
      if (replaced) { rows.push({ id: stop.id, title: stop.title, before: placeOf(replaced), after: placeOf(stop), kind: "place", line: doneLine(stop) }); touched.add(stop.id); }
      continue;
    }
    if (was.date === stop.date && range(was) !== range(stop)) { rows.push({ id: stop.id, title: stop.title, before: range(was), after: range(stop), kind: "time", line: doneLine(stop) }); touched.add(stop.id); }
    else if (placeOf(was) !== placeOf(stop)) { rows.push({ id: stop.id, title: stop.title, before: placeOf(was), after: placeOf(stop), kind: "place", line: doneLine(stop) }); touched.add(stop.id); }
  }
  if (rows.length === 0) return null;
  const last = after.reduce((at, stop, index) => (touched.has(stop.id) ? index : at), -1);
  const day = after[last].date;
  const next = after.slice(last + 1).find((stop) => stop.date === day && !touched.has(stop.id));
  return { rows, keep: next ? [{ id: next.id, title: next.title, time: range(next) }] : [] };
}

const KEY = "tripilot.web.chatDiffs.v1:";

/** This tab's diffs of one trip, by the version the change made. */
export function readDiffs(tripId: string): Record<string, ChatDiff> {
  try {
    const raw = JSON.parse(window.sessionStorage.getItem(KEY + tripId) ?? "{}") as unknown;
    return raw && typeof raw === "object" && !Array.isArray(raw) ? raw as Record<string, ChatDiff> : {};
  } catch { return {}; }
}

export function keepDiff(tripId: string, version: number, diff: ChatDiff) {
  try {
    const all = { ...readDiffs(tripId), [String(version)]: diff };
    const kept = Object.fromEntries(Object.entries(all).sort(([a], [b]) => Number(a) - Number(b)).slice(-20));
    window.sessionStorage.setItem(KEY + tripId, JSON.stringify(kept));
  } catch { /* shown for this page only */ }
}
