import { compareItems, streamedReview } from "@/features/intake-review/stream-model";
import type { IntakeView } from "@/lib/live/intake";
import type { StreamLine, StreamState } from "@/lib/live/intake-events";
import type { Candidate, CheckLine, ItemRow, MoveRow, ReviewItem, ReviewMove, ReviewedIntakeView } from "@/lib/live/intake-review";
import { readingOf } from "./from-intake";
import type { CheckRow, PlaceInfo, PlanCandidate, PlanCheckView, PlanItem, PlanLine, PlanMove, PlanStage, Verdict } from "./model";

/**
 * The plan-check screen's data from the server's own check (`review`, `wiki/external/rest-endpoints.md` 「확인 화면 검사 …」).
 *
 * ★The server decides whether a place is open and a leg is reachable; this file only changes its shape. A value the server
 *   did not give stays empty — a stop with no check line yet has none, a leg it could not check is `unknown`, never "fine".
 *   While the server is still checking, the same shape is built from the events that have come in (`StreamState`); the
 *   screen paces what it draws (`nextStep` in model.ts), the server keeps no pace.
 */

const row = (line: CheckLine<ItemRow | MoveRow>): CheckRow => ({ kind: line.row, result: line.result, text: line.text });

/** keep · adjusted · review. A leg that waits (an end has no place) is settled — it just has nothing to check. */
const verdictOf = (status: ReviewItem["status"] | ReviewMove["status"]): Verdict | null =>
  status === "keep" || status === "adjusted" || status === "review" ? status : status === "waiting" ? "keep" : null;

/** The day number the screen groups by: the server's, else the order of the stop's date. */
function dayNumbers(items: readonly ReviewItem[]): Map<string, number> {
  const dates = [...new Set(items.map((item) => item.date ?? ""))].sort((a, b) => (a || "9999").localeCompare(b || "9999"));
  return new Map(items.map((item) => [item.id, item.day ?? dates.indexOf(item.date ?? "") + 1]));
}

/** Place photos come from hosts the place data names; only http and https are ever requested — nothing like `javascript:` or `data:`. */
export function safePhotoUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.toString() : null;
  } catch { return null; }
}

export const located = (place: { latitude: number | null; longitude: number | null } | null | undefined): place is { latitude: number; longitude: number } =>
  typeof place?.latitude === "number" && typeof place?.longitude === "number";

function planItem(item: ReviewItem, day: number, info: PlaceInfo | null): PlanItem {
  // The place the customer picked names the card; the words they wrote stay for the editor and as a small line under it.
  const picked = item.place_state === "customer" && item.place?.name && item.place.name !== item.title ? item.place.name : null;
  return {
    id: item.id, day, date: item.date ?? "", startsAt: item.starts_at ?? "", endsAt: item.ends_at ?? "",
    title: picked ?? item.title, ...(picked && { written: item.title }), place: item.place?.name ?? "", noPlace: item.place_state === "none",
    coordinates: located(item.place) ? { lat: item.place.latitude, lng: item.place.longitude } : null,
    checks: (item.rows ?? []).map(row), verdict: verdictOf(item.status), locked: item.locked, info, suggestion: null,
  };
}

function planMove(move: ReviewMove, dayOf: Map<string, number>): PlanMove {
  return {
    id: `${move.from}:${move.to}`, fromId: move.from, toId: move.to, day: dayOf.get(move.from) ?? move.day ?? 1,
    departAt: move.depart ?? "", mode: move.mode_label ?? "", summary: move.summary,
    checks: move.rows.map(row), verdict: verdictOf(move.status),
  };
}

export interface ReviewShape {
  items: readonly ReviewItem[];
  moves: readonly ReviewMove[];
}

/**
 * The screen's view of items and legs. `infos` are what the change screen has fetched for a stop's own place (photos …),
 * by stop id; `base` is the intake read from the server (lines, title).
 */
export function viewOfReview(base: PlanCheckView, review: ReviewShape, stage: PlanStage, infos: Readonly<Record<string, PlaceInfo>> = {}): PlanCheckView {
  const dayOf = dayNumbers(review.items);
  const items = review.items.map((item) => planItem(item, dayOf.get(item.id) ?? 1, infos[item.id] ?? null));
  const days = [...new Map(items.map((item) => [item.day, item.date])).entries()].map(([day, date]) => ({ day, date })).sort((a, b) => a.day - b.day);
  return { ...base, stage, days, items, moves: review.moves.map((move) => planMove(move, dayOf)) };
}

/**
 * The finished check (`status` review or confirmed) — null when the server did not build one (`review` is null with a
 * `review_error`), so the caller falls back to what it can say from the read values alone.
 */
export function reviewResultOf(intake: ReviewedIntakeView, base: PlanCheckView, infos?: Readonly<Record<string, PlaceInfo>>): PlanCheckView | null {
  if (!intake.review) return null;
  return viewOfReview({ ...base, title: intake.check?.title ?? null }, intake.review, "done", infos);
}

/** Lines the stream has told about that the intake does not hold yet (a read that is a moment ahead of the GET). */
function withStreamLines(lines: PlanLine[], intake: IntakeView, stream: StreamState): PlanLine[] {
  // The screen numbers lines across sources, in the order of the sources; a stream line points at (source, its own no).
  const offsets = new Map<string, number>();
  let total = 0;
  for (const source of intake.sources) { offsets.set(source.source_id, total); total += source.lines.length; }
  const next = lines.map((line) => ({ ...line }));
  for (const entry of Object.values(stream.lines) as StreamLine[]) {
    const offset = offsets.get(entry.source_id);
    if (offset === undefined) continue;
    const at = offset + entry.no - 1;
    if (at < 0 || at >= next.length) continue;
    next[at] = { ...next[at], read: true, found: entry.found ? { kind: "item", day: entry.found.day, startsAt: entry.found.starts_at, title: entry.found.title } : next[at].found };
  }
  return next;
}

/**
 * The screen while the server is still reading and checking: the lines and what was found on them (the intake plus the
 * stream), then the places and legs with the check lines that have come in. `stage` follows the server's stage — once any
 * place or leg has come, the screen is on the check, however the last stage event reads.
 */
export function streamingViewOf(intake: IntakeView, stream: StreamState, infos?: Readonly<Record<string, PlaceInfo>>): PlanCheckView {
  const base = readingOf(intake);
  const lines = withStreamLines(base.lines, intake, stream);
  const streamed = streamedReview(stream);
  const checking = intake.stage === "checking" || streamed.items.length > 0 || streamed.moves.length > 0;
  const stage: PlanStage = intake.stage === "received" ? "received" : checking ? "checking" : "reading";
  const view = viewOfReview({ ...base, lines }, { items: [...streamed.items].sort(compareItems), moves: streamed.moves }, stage, infos);
  // ★`[2026-10-03]` The server's own count (`progress` packet) rides on the view as it is; with none (an older server) the bar is worked out from the rows as before.
  const packet = stream.progress;
  return packet ? { ...view, serverProgress: { phase: packet.phase, done: packet.done, total: packet.total, title: packet.current?.title ?? null } } : view;
}

/** Candidates → the change screen's cards. `distance.from` is the nearby stop the distance was measured from. */
export function planCandidate(candidate: Candidate, itemId: string, source: PlanCandidate["source"], info: PlaceInfo | null): PlanCandidate {
  return {
    id: `${itemId}:${candidate.place.ref ?? candidate.place.name}:${candidate.rank}`,
    name: candidate.place.name, source, rank: source === "candidate" ? candidate.rank : null,
    distance: typeof candidate.distance_m === "number" && candidate.reference ? { km: candidate.distance_m / 1000, from: candidate.reference } : null,
    coordinates: located(candidate.place) ? { lat: candidate.place.latitude, lng: candidate.place.longitude } : null,
    info, checks: candidate.rows.map(row),
  };
}
