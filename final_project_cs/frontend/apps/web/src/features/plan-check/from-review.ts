import { compareItems, streamedReview } from "@/features/intake-review/stream-model";
import type { IntakeView } from "@/lib/live/intake";
import { modeChoiceOf } from "@/lib/live/move-options";
import { webTaxiPricingOf } from "@/lib/live/taxi-pricing";
import { itemRiskOf, problemText, type ItemRisk } from "@/lib/live/risks";
import { proposedTimeOf } from "./risk-candidate-edits";
import type { StreamLine, StreamState } from "@/lib/live/intake-events";
import type { Candidate, CandidateLeg, CheckLine, ItemRow, MoveRow, ReviewItem, ReviewMove, ReviewedIntakeView } from "@/lib/live/intake-review";
import { readingOf } from "./from-intake";
import type { CheckRow, PlaceInfo, PlanAsk, PlanCandidate, PlanCandidateLeg, PlanCheckView, PlanDay, PlanItem, PlanLine, PlanMove, PlanStage, PrefillNotes, Reread, Verdict } from "./model";

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

/** The two readings worth offering: a known field, two different non-empty values. One with no other reading keeps only its row's note. */
function rereadsOf(item: ReviewItem): Reread[] {
  return (Array.isArray(item.rereads) ? item.rereads : []).flatMap((entry) =>
    (entry?.field === "title" || entry?.field === "booking_no") && typeof entry.current === "string" && typeof entry.other === "string" && entry.other.trim() && entry.other !== entry.current
      ? [{ field: entry.field, current: entry.current, other: entry.other }] : []);
}

export function isLodgingReviewItem(item: ReviewItem): boolean {
  return item.kind === "lodging" || item.parts?.content_type === "32" || item.place?.content_type_id === "32"
    || /숙박|숙소|호텔|lodging|hotel/i.test(item.place?.category ?? "");
}

function planItem(item: ReviewItem, day: number, info: PlaceInfo | null): PlanItem {
  // The place the customer picked names the card; the words they wrote stay for the editor and as a small line under it.
  const picked = item.place_state === "customer" && item.place?.name && item.place.name !== item.title ? item.place.name : null;
  const risk = itemRiskOf(item.risk);
  if (risk) { risk.itemId = item.id; risk.title = picked ?? item.title; }
  return {
    id: item.id, day, date: item.date ?? "", startsAt: item.starts_at ?? "", endsAt: item.ends_at ?? "", ...(item.end_date ? { endDate: item.end_date } : {}),
    title: picked ?? item.title, ...(picked && { written: item.title }), place: item.place?.name ?? "", noPlace: item.place_state === "none", kind: item.kind ?? item.place?.kind ?? null,
    ...(isLodgingReviewItem(item) ? { displayKind: "lodging" } : {}),
    ...(item.lodging_group ? { lodgingGroup: { ...item.lodging_group, place: item.lodging_group.place?.name ?? null } } : {}),
    coordinates: located(item.place) ? { lat: item.place.latitude, lng: item.place.longitude } : null,
    checks: [...(item.rows ?? []).filter((line) => line.row !== "risk").map(row), ...riskChecks(risk)], risk,
    rereads: rereadsOf(item), verdict: verdictOf(item.status), locked: item.locked, booked: item.booked ?? null, info, suggestion: null,
    ...(item.vendor_booking ? { vendorBooking: true } : {}),
    // `[2026-10-20 C안]` What the question at the stop says (「맞는 곳이 n곳이라 가까운 …로 임시로 골랐어요」).
    placeState: item.place_state ?? null, placeChoices: item.candidates_hint ?? null,
  };
}

function planMove(move: ReviewMove, dayOf: Map<string, number>): PlanMove {
  return {
    id: `${move.from}:${move.to}`, fromId: move.from, toId: move.to,
    // `[2026-10-13]` A morning move from the stay belongs to the day it opens (its `to`), not the check-in day of the stay.
    day: move.from_stay ? (move.day ?? dayOf.get(move.to) ?? 1) : (dayOf.get(move.from) ?? move.day ?? 1),
    ...(move.from_stay ? { fromStay: true } : {}),
    departAt: move.depart ?? "", mode: move.mode_label ?? "", summary: move.summary,
    minutes: move.minutes ?? null, arriveAt: move.arrive ?? "", slackMin: move.slack_min ?? null, estimated: move.basis === "estimate",
    modeKey: move.mode ?? null, recommendedMode: move.recommended_mode ?? null, modeChoice: modeChoiceOf(move.mode_choice),
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
export function viewOfReview(base: PlanCheckView, review: ReviewShape, stage: PlanStage, infos: Readonly<Record<string, PlaceInfo>> = {},
  filled: ReadonlyMap<string, string> = new Map()): PlanCheckView {
  const dayOf = dayNumbers(review.items);
  const items = review.items.map((item) => withFilled(planItem(item, dayOf.get(item.id) ?? 1, infos[item.id] ?? null), filled.get(item.id)));
  const days = [...new Map(items.map((item) => [item.day, item.date])).entries()].map(([day, date]) => ({ day, date })).sort((a, b) => a.day - b.day);
  return { ...base, stage, days, items, moves: review.moves.map((move) => planMove(move, dayOf)) };
}

/**
 * The finished check (`status` review or confirmed) — null when the server did not build one (`review` is null with a
 * `review_error`), so the caller falls back to what it can say from the read values alone.
 */
export function reviewResultOf(intake: ReviewedIntakeView, base: PlanCheckView, infos?: Readonly<Record<string, PlaceInfo>>): PlanCheckView | null {
  if (!intake.review) return null;
  const view = viewOfReview({ ...base, revision: intake.revision, title: intake.check?.title ?? null, taxiPricing: webTaxiPricingOf(intake.review.taxi_pricing),
    prefill: prefillNotesOf(intake), risksAvailable: intake.review.risk_schema_version === 1,
    riskMode: intake.review.risk_mode, riskCheckedAt: intake.review.risk_checked_at }, intake.review, "done", infos, filledReasons(intake));
  const unfound = unfoundQuestions(intake);
  const asks = asksOf(intake, view.days);
  return { ...(unfound.size ? { ...view, items: view.items.map((item) => withUnfound(item, unfound.get(item.id))) } : view), ...(asks.length ? { asks } : {}) };
}

const clockOf = (value: unknown): string => {
  const match = typeof value === "string" ? /(\d{1,2}):(\d{2})/.exec(value) : null;
  return match ? `${match[1].padStart(2, "0")}:${match[2]}` : "";
};

/**
 * ★`[2026-10-21 사용자 결정 — P6 해석 확인 질문]` The questions the first check stops to ask (`interpretations[]`): only those not answered whose stop is still out (the AI's reading is what
 * the plan holds), each at its line's day and time as the rule read them (`sources[].items`). The words and options are the server's as they are; a question whose stop or options cannot be
 * read is left out (never made up).
 */
export function asksOf(intake: Pick<IntakeView, "interpretations" | "sources">, days: readonly PlanDay[]): PlanAsk[] {
  return (intake.interpretations ?? []).flatMap((entry) => {
    if (entry?.kind !== "interpretation" || entry.answer != null || entry.applied !== "reading" || typeof entry.question !== "string" || !entry.question || !Array.isArray(entry.options)) return [];
    const stop = intake.sources.find((source) => source.source_id === entry.source_id)?.items.find((item) => item.index === entry.index);
    const options = entry.options.flatMap((option) => option && typeof option.id === "string" && typeof option.label === "string"
      ? [{ id: option.id, label: option.label, recommended: option.recommended === true, reason: typeof option.reason === "string" ? option.reason : null,
          effect: typeof option.effect === "string" ? option.effect : null, pickMyself: option.action === "pick_myself", query: typeof option.query === "string" && option.query ? option.query : null }] : []);
    if (!stop || !options.length) return [];
    const date = stop.date ?? (typeof stop.fields.date?.value === "string" ? stop.fields.date.value : "");
    const day = stop.day ?? days.find((entry) => entry.date === date)?.day ?? days[0]?.day ?? 1;
    const title = typeof stop.fields.title?.value === "string" ? stop.fields.title.value : "";
    return [{ id: entry.id, itemId: entry.item, day, date, startsAt: clockOf(stop.fields.starts_at?.value), title, question: entry.question, quote: entry.quote ?? "", options }];
  });
}

/**
 * `[2026-10-19 사용자 결정 — 못 찾은 장소는 후보 보이고 묻기]` The questions about a stop whose place was not found (`prefill.questions[]` `kind: "place_not_found"`), by the check's stop id.
 * Only those that name a stop of the check — the card of that stop carries the question; one that names none stays in the note above the list.
 */
export function unfoundQuestions(intake: Pick<IntakeView, "prefill"> & { review?: { items: readonly { id: string }[] } | null }): Map<string, { question: string; blocked: boolean }> {
  const ids = new Set((intake.review?.items ?? []).map((item) => item.id));
  const out = new Map<string, { question: string; blocked: boolean }>();
  for (const entry of intake.prefill?.questions ?? []) {
    if (entry?.kind !== "place_not_found" || typeof entry.item !== "string" || !ids.has(entry.item) || typeof entry.question !== "string" || !entry.question) continue;
    if (!out.has(entry.item)) out.set(entry.item, { question: entry.question, blocked: entry.blocked === true });
  }
  return out;
}

/** A stop that has a place now (picked, or 「장소 없음」) is not asked about any more, whatever the record of the first fill still says. */
function withUnfound(item: PlanItem, unfound: { question: string; blocked: boolean } | undefined): PlanItem {
  return unfound && !item.coordinates && !item.noPlace ? { ...item, unfound } : item;
}

/**
 * `[2026-10-16 D-025]` 「우리가 채움」 — a stop the server filled in first carries one ✎ line with the reason, ahead of its own checks.
 * Only stops the server names in `prefill.filled`; a stop the customer changed afterwards keeps the line until the server drops it.
 */
function withFilled(item: PlanItem, reason: string | undefined): PlanItem {
  return reason ? { ...item, checks: [{ kind: "place", result: "filled", text: `먼저 채움 · ${reason}` }, ...item.checks] } : item;
}

export function filledReasons(intake: Pick<IntakeView, "prefill">): Map<string, string> {
  const out = new Map<string, string>();
  for (const entry of intake.prefill?.filled ?? []) if (entry?.item && typeof entry.reason === "string" && entry.reason) out.set(entry.item, entry.reason);
  return out;
}

/** The note above the list: questions only the traveller can answer, and the traveller's own words read as a move, a condition or a preference. Null when there is nothing to say. */
export function prefillNotesOf(intake: Pick<IntakeView, "prefill" | "sources"> & Partial<Pick<IntakeView, "check">> & { review?: { items: readonly { id: string }[] } | null }): PrefillNotes | null {
  // `[2026-10-19]` A question about a stop's place not found is asked on that stop's card, not here.
  const onCards = new Set(unfoundQuestions(intake).keys());
  const questions = [...new Set((intake.prefill?.questions ?? [])
    .filter((entry) => !(entry?.kind === "place_not_found" && typeof entry.item === "string" && onCards.has(entry.item)))
    .map((entry) => entry?.question).filter((text): text is string => typeof text === "string" && text.length > 0))];
  const understood = [...new Set(intake.sources.flatMap((source) => {
    const read = source.understanding;
    if (!read) return [];
    return [...(read.moves ?? []), ...(read.conditions ?? []), ...(read.preferences ?? [])].map((entry) => entry?.quote).filter((text): text is string => typeof text === "string" && text.length > 0);
  }))];
  const filledCount = (intake.prefill?.filled ?? []).length;
  // `[2026-10-16 D-025 후속]` What we hand to an owner from those words — only lines the server named fully (label · text · owner)
  const handoff = (intake.check?.handoff ?? [])
    .filter((entry) => entry && typeof entry.label === "string" && typeof entry.text === "string" && entry.text && typeof entry.owner === "string")
    .map((entry) => ({ label: entry.label, text: entry.text, owner: entry.owner, mine: entry.status !== "customer" }));
  return questions.length || understood.length || filledCount || handoff.length ? { filledCount, questions, understood, handoff } : null;
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
    next[at] = { ...next[at], read: true, found: entry.found ? { kind: "item", id: entry.found.id, sourceKey: `${entry.source_id}:${entry.found.index}`, date: entry.found.date, day: entry.found.day, startsAt: entry.found.starts_at, title: entry.found.title } : next[at].found };
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
  const drawnView = viewOfReview({ ...base, lines }, { items: [...streamed.items].sort(compareItems), moves: streamed.moves }, stage, infos);
  // `[2026-10-21 P6]` The questions the intake already holds: the check does not draw past their place while the server works (it asks there once the check is final).
  const asks = asksOf(intake, drawnView.days);
  const view = asks.length ? { ...drawnView, asks } : drawnView;
  // ★`[2026-10-03]` The server's own count (`progress` packet) rides on the view as it is; with none (an older server) the bar is worked out from the rows as before.
  const packet = stream.progress;
  return packet ? { ...view, serverProgress: { phase: packet.phase, done: packet.done, total: packet.total, title: packet.current?.title ?? null } } : view;
}

/** Candidates → the change screen's cards. `distance.from` is the nearby stop the distance was measured from. */
export function planCandidate(candidate: Candidate, itemId: string, source: PlanCandidate["source"], info: PlaceInfo | null): PlanCandidate {
  const risk = itemRiskOf(candidate.risk);
  const proposedTime = proposedTimeOf(candidate);
  const timing = proposedTime ? [proposedTime.date, `${proposedTime.startsAt}${proposedTime.endsAt ? `–${proposedTime.endsAt}` : ""}`].filter(Boolean).join(" · ") : null;
  const reason = [candidate.reason?.trim(), timing].filter(Boolean).join(" · ");
  return {
    id: `${itemId}:${candidate.place.ref ?? candidate.place.name}:${candidate.rank}`,
    name: candidate.place.name, source, rank: source === "candidate" ? candidate.rank : null,
    distance: typeof candidate.distance_m === "number" && candidate.reference ? { km: candidate.distance_m / 1000, from: candidate.reference } : null,
    coordinates: located(candidate.place) ? { lat: candidate.place.latitude, lng: candidate.place.longitude } : null,
    info, checks: [...candidate.rows.filter((line) => line.row !== "risk").map(row), ...riskChecks(risk)], risk,
    ...(proposedTime ? { proposedTime } : {}),
    ...(candidate.basis ? { basis: candidate.basis } : {}),
    ...(candidate.basis === "meal_inferred" ? { placeKind: "dining" } : candidate.place.kind === "dining" || candidate.place.kind === "activity" ? { placeKind: candidate.place.kind } : {}),
    ...(reason ? { reason } : {}),
    ...(candidate.legs ? { legs: { before: legOf(candidate.legs.before), after: legOf(candidate.legs.after) } } : {}),
    ...(candidate.pending ? { pending: { before: candidate.pending.before === true, after: candidate.pending.after === true, reason: candidate.pending.reason === true } } : {}),
  };
}

function legOf(leg: CandidateLeg | null | undefined): PlanCandidateLeg | null {
  return leg ? { with: leg.with, minutes: leg.minutes, modeLabel: leg.mode_label, estimated: leg.estimated, slackMin: leg.slack_min } : null;
}

function riskChecks(risk: ItemRisk | null): CheckRow[] {
  if (!risk) return [];
  const text = risk.problems.map(problemText).filter(Boolean).join("; ");
  return [{ kind: "risk", result: risk.status === "problem" ? "warn" : risk.status === "clear" ? "ok" : "unknown",
    text: text || (risk.status === "clear" ? "확인한 위험 정보에서 겹치는 문제가 없어요"
      : risk.reason || `확인 불가: ${risk.unknownCategories.join(" · ") || "위험 정보"}`) }];
}
