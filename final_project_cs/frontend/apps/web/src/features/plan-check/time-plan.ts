/**
 * The time maths of one day of a travel plan: how much free time lies between stops, how far a stop can be moved, and what moving
 * it does to its neighbours. Pure (no React, no clock), so the rules are tested without a browser.
 *
 * Every function takes ONE day: `stops` ordered by `start` ascending, and `legs` (travel time between two consecutive stops, looked
 * up by the two ids; a pair with no leg counts as 0 minutes). All times are whole minutes since midnight of that day (0..1440).
 */

/** One stop of the day. `fixed` = locked or booked: it cannot move and nothing may push it. `end` null = the end is not known. */
export interface TimedStop { id: string; start: number; end: number | null; fixed: boolean }
/** Travel time between two consecutive stops of the day. */
export interface TimedLeg { fromId: string; toId: string; minutes: number }
/** A stop at its new time (`end` is shifted by the same amount as `start`; null stays null). */
export interface Retime { id: string; start: number; end: number | null }
/** The range of START times a stop can have. */
export interface TimeRange { min: number; max: number }
/** What moving one stop does: where it lands, who is pushed with it (day order, the moved stop included), and the range it was held to. */
export interface MoveResult { start: number; changes: Retime[]; clamped: boolean; min: number; max: number }

/** The day ends here (24:00). A stop must end by it. */
export const DAY_END = 1440;
/** Times are moved in steps of this many minutes. */
export const SNAP = 5;
/** A stop with no known end takes this long for the maths. */
export const ASSUMED_MINUTES = 60;
/**
 * Space between two stops on screen: `GAP_BASE_PX` even with no free time, growing with the free time along a curve that flattens out toward
 * `GAP_BASE_PX + GAP_EXTRA_PX` (`[2026-10-04]` codex: a straight line made long idle stretches 120 px each and the list too long to scroll; the curve
 * still tells 30 minutes from 2 hours - about 40 px and 71 px - and never passes 80 px). `GAP_SCALE_MINUTES` is how fast it flattens.
 */
export const GAP_BASE_PX = 14, GAP_EXTRA_PX = 66, GAP_SCALE_MINUTES = 60;
/** The most space a gap can take (the curve reaches it only in the limit). */
export const GAP_MAX_PX = GAP_BASE_PX + GAP_EXTRA_PX;

// ---------------------------------------------------------------------------------------------------------------------------------
// Reading and writing a time
// ---------------------------------------------------------------------------------------------------------------------------------

const HM = /^(\d{1,2}):(\d{2})$/;

/**
 * "09:30" (or "9:30") -> 570. Null for "" or anything that is not a time of day: hours 0-23, minutes 0-59, surrounding spaces
 * ignored. "24:00" is not accepted: nothing starts at midnight's end, so the latest time that can be typed is 23:59.
 */
export function parseHm(text: string): number | null {
  const found = HM.exec(text.trim());
  if (!found) return null;
  const hours = Number(found[1]);
  const minutes = Number(found[2]);
  if (hours > 23 || minutes > 59) return null;
  return hours * 60 + minutes;
}

/**
 * 570 -> "09:30". For display only: the value is rounded to a whole minute and clamped to 0..1439, so 1440 shows as "23:59", not
 * "24:00". Not a number (NaN, infinite) shows "--:--" - an unknown time is not drawn as midnight.
 */
export function formatHm(minutes: number): string {
  if (!Number.isFinite(minutes)) return "--:--";
  const whole = Math.min(DAY_END - 1, Math.max(0, Math.round(minutes)));
  const hours = Math.floor(whole / 60);
  return `${String(hours).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}`;
}

/** A zero that is never "-0" (`Object.is(-0, 0)` is false, which would leak into comparisons and snapshots). */
function plain(value: number): number {
  return value === 0 ? 0 : value;
}

/** Round to the nearest multiple of `step` (a half rounds up). A step that is not a positive number leaves the value as it is. */
export function snap(minutes: number, step: number = SNAP): number {
  if (!(step > 0)) return minutes;
  return plain(Math.round(minutes / step) * step);
}

/** Round UP to a multiple of `step`: the first allowed time that is not earlier than `minutes`. */
function snapUp(minutes: number, step: number = SNAP): number {
  return plain(Math.ceil(minutes / step) * step);
}

/** Round DOWN to a multiple of `step`: the last allowed time that is not later than `minutes`. */
function snapDown(minutes: number, step: number = SNAP): number {
  return plain(Math.floor(minutes / step) * step);
}

// ---------------------------------------------------------------------------------------------------------------------------------
// Free time
// ---------------------------------------------------------------------------------------------------------------------------------

/** How long the stop takes: `end - start`, `ASSUMED_MINUTES` when the end is unknown, never below 0. */
export function occupancy(stop: Pick<TimedStop, "start" | "end">): number {
  if (stop.end === null) return ASSUMED_MINUTES;
  return Math.max(0, stop.end - stop.start);
}

type LegLookup = (fromId: string, toId: string) => number;

/** Travel minutes between two stops by id: 0 when the pair has no leg (or a negative one). If a pair is listed twice the first counts. */
function legLookup(legs: readonly TimedLeg[]): LegLookup {
  const minutes = new Map<string, number>();
  for (const leg of legs) {
    const key = `${leg.fromId}\u0000${leg.toId}`;
    if (!minutes.has(key)) minutes.set(key, Math.max(0, leg.minutes));
  }
  return (fromId, toId) => minutes.get(`${fromId}\u0000${toId}`) ?? 0;
}

/** Travel minutes from stop `fromId` to stop `toId` (0 when unknown). */
export function legMinutes(legs: readonly TimedLeg[], fromId: string, toId: string): number {
  return legLookup(legs)(fromId, toId);
}

/** The stop at `index`, or a RangeError: asking about a stop the day does not have is a bug of the caller, not a time. */
function stopAt(stops: readonly TimedStop[], index: number): TimedStop {
  const stop = Number.isInteger(index) ? stops[index] : undefined;
  if (!stop) throw new RangeError(`time-plan: no stop at index ${index} (the day has ${stops.length})`);
  return stop;
}

/**
 * Free minutes between stop `index` and the next one: `next.start - (stop.start + occupancy + travel)`. Negative = already late
 * (the next stop starts before the traveller can be there). Null for the last stop (nothing follows) and for an index with no stop.
 */
export function slackAfter(stops: readonly TimedStop[], legs: readonly TimedLeg[], index: number): number | null {
  const stop = stops[index];
  const next = stops[index + 1];
  if (!stop || !next) return null;
  return next.start - (stop.start + occupancy(stop) + legLookup(legs)(stop.id, next.id));
}

/**
 * Space on screen for the free time between two stops, in whole px: `GAP_BASE_PX + GAP_EXTRA_PX * (1 - e^(-free / GAP_SCALE_MINUTES))`.
 * No slack (null), none left (0) or negative slack (already late) gets the base space only - the wording says "late", the distance does not.
 */
export function gapPx(slackMinutes: number | null): number {
  if (slackMinutes === null || !(slackMinutes > 0)) return GAP_BASE_PX;
  return Math.round(GAP_BASE_PX + GAP_EXTRA_PX * (1 - Math.exp(-slackMinutes / GAP_SCALE_MINUTES)));
}

// ---------------------------------------------------------------------------------------------------------------------------------
// How far a stop can go
// ---------------------------------------------------------------------------------------------------------------------------------

/**
 * A range snapped inwards (min up, max down). When nothing is left, the only start the stop can have is the one it has.
 * A stop that already stands outside the range (it overlaps a neighbour before any move, or sits off the 5-minute grid next to
 * its limit) keeps its own place in the range: the range is widened to reach it, so a drag never throws the stop the other way
 * and a push is still only ever caused by the move (widening one side leaves the other side's guarantee as it was).
 */
function inwards(min: number, max: number, start: number, step: number): TimeRange {
  const low = snapUp(min, step);
  const high = snapDown(max, step);
  if (low > high) return { min: start, max: start };
  return { min: Math.min(low, start), max: Math.max(high, start) };
}

/**
 * The START times stop `index` can have WITHOUT moving any other stop: from the end of the previous stop plus the travel to it
 * (0 for the first stop) to the start of the next stop minus the travel and its own length (`DAY_END` minus its length for the
 * last stop). `min` is snapped up and `max` down to `SNAP`. With no room at all, `{ min: start, max: start }`, and a `fixed` stop
 * can only stay where it is. A stop already standing outside this range keeps its place in it (see `inwards`).
 * This is the range typed input may use when the customer does not want neighbours to move; see `pushRange` for what a drag may use.
 */
export function ownRange(stops: readonly TimedStop[], legs: readonly TimedLeg[], index: number, step: number = SNAP): TimeRange {
  const stop = stopAt(stops, index);
  if (stop.fixed) return { min: stop.start, max: stop.start };
  const leg = legLookup(legs);
  const previous = stops[index - 1];
  const next = stops[index + 1];
  const min = previous ? previous.start + occupancy(previous) + leg(previous.id, stop.id) : 0;
  const max = (next ? next.start - leg(stop.id, next.id) : DAY_END) - occupancy(stop);
  return inwards(min, max, stop.start, step);
}

/**
 * The START times stop `index` can reach when the stops before it may be pushed earlier and the stops after it pushed later
 * (packed as tight as the stops and their travel allow), but never across a `fixed` stop and never out of the day: the first stop
 * starts at 0 or later and the last one ends by `DAY_END`. `min` is snapped up and `max` down to `SNAP`; with no room at all it is
 * `{ min: start, max: start }`. A `fixed` stop can only stay where it is; a stop already standing outside the range keeps its
 * place in it (see `inwards`). This is the range a drag may use (`ownRange` is the smaller range that moves nobody else).
 */
export function pushRange(stops: readonly TimedStop[], legs: readonly TimedLeg[], index: number, step: number = SNAP): TimeRange {
  const stop = stopAt(stops, index);
  if (stop.fixed) return { min: stop.start, max: stop.start };
  const leg = legLookup(legs);

  // Earliest: everything before is packed against the nearest fixed stop before this one (or against the start of the day).
  let packedBefore = 0;
  let floor = 0;
  for (let k = index - 1; k >= 0; k--) {
    packedBefore += occupancy(stops[k]) + leg(stops[k].id, stops[k + 1].id);
    if (stops[k].fixed) { floor = stops[k].start; break; }
  }

  // Latest: this stop and everything after it are packed against the nearest fixed stop after this one (or against the end of the day).
  let packedAfter = occupancy(stop);
  let ceiling = DAY_END;
  for (let k = index + 1; k < stops.length; k++) {
    packedAfter += leg(stops[k - 1].id, stops[k].id);
    if (stops[k].fixed) { ceiling = stops[k].start; break; }
    packedAfter += occupancy(stops[k]);
  }

  return inwards(floor + packedBefore, ceiling - packedAfter, stop.start, step);
}

// ---------------------------------------------------------------------------------------------------------------------------------
// Moving a stop
// ---------------------------------------------------------------------------------------------------------------------------------

/**
 * Move stop `index` to `wantedStart` and say what that does. The wanted time is snapped to `SNAP`, then held inside `pushRange`
 * (or inside `ownRange` when `options.push === false`: typed input that must not move neighbours); `clamped` says the hold changed it.
 * `options.step` is the grid the time is held to (`SNAP` = 5 minutes for a drag; 1 for a time typed in by hand, which is taken to the minute).
 *
 * - Later: every following stop that would now start before the one in front of it is over (start + length + travel) is pushed to
 *   exactly that time, and the next one is looked at the same way, until a stop is not touched.
 * - Earlier: the mirror image - a previous stop that would now run past the next one's start (minus travel) is pushed earlier to
 *   `next.start - travel - length`.
 * - A pushed stop keeps its length: `end` shifts by the same minutes as `start` (null stays null).
 * - Only what the move itself causes is pushed: stops that already overlap before the move stay as they are (the function does not
 *   tidy them up), and a push ends at the first stop that is not hit.
 * - A `fixed` stop is never moved. The range guarantees a push cannot reach one; the stop itself can only stay where it is.
 *
 * `changes` lists only the stops whose start actually changed, in day order (the moved stop included); empty when nothing moves. A `wantedStart` that is not a number moves nothing. An `index` with no stop throws a RangeError.
 */
export function moveStop(
  stops: readonly TimedStop[],
  legs: readonly TimedLeg[],
  index: number,
  wantedStart: number,
  options: { push?: boolean; step?: number } = {},
): MoveResult {
  const stop = stopAt(stops, index);
  const step = options.step ?? SNAP;
  const { min, max } = options.push === false ? ownRange(stops, legs, index, step) : pushRange(stops, legs, index, step);
  if (!Number.isFinite(wantedStart)) return { start: stop.start, changes: [], clamped: false, min, max };

  const wanted = snap(wantedStart, step);
  const start = Math.min(max, Math.max(min, wanted));
  const clamped = start !== wanted;
  const delta = start - stop.start;
  if (delta === 0) return { start, changes: [], clamped, min, max };

  const leg = legLookup(legs);
  const starts = stops.map((s) => s.start);
  starts[index] = start;
  if (delta > 0) {
    for (let k = index + 1; k < stops.length; k++) {
      const earliest = starts[k - 1] + occupancy(stops[k - 1]) + leg(stops[k - 1].id, stops[k].id);
      if (starts[k] >= earliest) break;
      starts[k] = earliest;
    }
  } else {
    for (let k = index - 1; k >= 0; k--) {
      const latest = starts[k + 1] - leg(stops[k].id, stops[k + 1].id) - occupancy(stops[k]);
      if (starts[k] <= latest) break;
      starts[k] = latest;
    }
  }

  const changes: Retime[] = [];
  stops.forEach((s, k) => {
    const shift = starts[k] - s.start;
    if (shift !== 0) changes.push({ id: s.id, start: starts[k], end: s.end === null ? null : s.end + shift });
  });
  return { start, changes, clamped, min, max };
}

/**
 * The day with `changes` applied: same order, every other field kept, stops that are not named stay the very same objects.
 * For the screen's live preview while a stop is being dragged. A change for an id the day does not have is ignored.
 */
export function settledAfter<T extends TimedStop>(stops: readonly T[], changes: readonly Retime[]): T[] {
  const byId = new Map(changes.map((change) => [change.id, change]));
  return stops.map((stop) => {
    const change = byId.get(stop.id);
    return change ? { ...stop, start: change.start, end: change.end } : stop;
  });
}

// ---------------------------------------------------------------------------------------------------------------------------------
// Free time first, then pushing: the stop at the end of the free time, and moving the END of a stop (the time of leaving)
// ---------------------------------------------------------------------------------------------------------------------------------

/**
 * `[2026-10-05 사용자 지시]` A drag that reaches the end of the free time (so far nobody else is pushed) is held there for this many more minutes of dragging; only a drag
 * that goes on past it pushes the stops behind (or in front). The stop has a place the finger can feel, and the screen says once that the free time is used up.
 */
export const DETENT_MINUTES = 10;

/** Which end of the free time a drag is being held at: `"max"` = the later end, `"min"` = the earlier end, null = not held. */
export type Held = "min" | "max" | null;

/**
 * Where a drag lands: free inside `own` (the range that moves nobody), held at its end for `DETENT_MINUTES` of further dragging, then on into `reach` (the range that may push).
 * With nothing to push into (`reach` ends where `own` ends) it is simply the end of the range.
 */
export function holdAtLimit(wanted: number, own: TimeRange, reach: TimeRange): { value: number; held: Held } {
  if (wanted > own.max) {
    if (reach.max <= own.max) return { value: own.max, held: null };
    const over = wanted - own.max;
    return over <= DETENT_MINUTES ? { value: own.max, held: "max" } : { value: Math.min(reach.max, own.max + over - DETENT_MINUTES), held: null };
  }
  if (wanted < own.min) {
    if (reach.min >= own.min) return { value: own.min, held: null };
    const over = own.min - wanted;
    return over <= DETENT_MINUTES ? { value: own.min, held: "min" } : { value: Math.max(reach.min, own.min - over + DETENT_MINUTES), held: null };
  }
  return { value: wanted, held: null };
}

/** What moving the END of one stop does (see `moveEnd`). */
export interface EndMove { end: number; changes: Retime[]; clamped: boolean; min: number; max: number }

/**
 * The END times a stop can have - the time the traveller leaves for the next place (`withTimes` draws the leg's departure at `start + length`). `own` moves nobody: from one step
 * after the start to the next stop's start minus the travel (the day's end for the last stop); `reach` lets the stops after it be pushed, but never across a `fixed` stop or out
 * of the day. A `fixed` stop keeps its end. Both are snapped inwards to `step`, and a stop already standing outside keeps its own place in them (see `inwards`).
 */
export function endRanges(stops: readonly TimedStop[], legs: readonly TimedLeg[], index: number, step: number = SNAP): { own: TimeRange; reach: TimeRange } {
  const stop = stopAt(stops, index);
  const current = stop.start + occupancy(stop);
  if (stop.fixed) return { own: { min: current, max: current }, reach: { min: current, max: current } };
  const leg = legLookup(legs);
  const next = stops[index + 1];
  const min = stop.start + step;
  const ownMax = next ? next.start - leg(stop.id, next.id) : DAY_END;
  let packedAfter = 0;
  let ceiling = DAY_END;
  for (let k = index + 1; k < stops.length; k++) {
    packedAfter += leg(stops[k - 1].id, stops[k].id);
    if (stops[k].fixed) { ceiling = stops[k].start; break; }
    packedAfter += occupancy(stops[k]);
  }
  return { own: inwards(min, ownMax, current, step), reach: inwards(min, ceiling - packedAfter, current, step) };
}

/**
 * Move the END of stop `index` (leave later or earlier). Leaving later uses the free time first: nothing else moves while `end` is inside `own`; past it each stop behind is pushed
 * to exactly the time it would need (start + length + travel of the one in front), one after the other, until a stop is not hit - the same push as `moveStop`. Leaving earlier
 * only makes the free time longer. `changes` has the stop itself first (its start unchanged, its new end) and then the pushed ones in day order.
 */
export function moveEnd(
  stops: readonly TimedStop[],
  legs: readonly TimedLeg[],
  index: number,
  wantedEnd: number,
  options: { push?: boolean; step?: number } = {},
): EndMove {
  const stop = stopAt(stops, index);
  const step = options.step ?? SNAP;
  const { own, reach } = endRanges(stops, legs, index, step);
  const range = options.push === false ? own : reach;
  const current = stop.start + occupancy(stop);
  if (!Number.isFinite(wantedEnd)) return { end: current, changes: [], clamped: false, min: range.min, max: range.max };
  const wanted = snap(wantedEnd, step);
  const end = Math.min(range.max, Math.max(range.min, wanted));
  const clamped = end !== wanted;
  if (end === current) return { end, changes: [], clamped, min: range.min, max: range.max };

  const leg = legLookup(legs);
  const starts = stops.map((s) => s.start);
  const lengths = stops.map((s) => occupancy(s));
  lengths[index] = end - stop.start;
  if (end > current) {
    for (let k = index + 1; k < stops.length; k++) {
      const earliest = starts[k - 1] + lengths[k - 1] + leg(stops[k - 1].id, stops[k].id);
      if (starts[k] >= earliest) break;
      starts[k] = earliest;
    }
  }
  const changes: Retime[] = [{ id: stop.id, start: stop.start, end }];
  stops.forEach((s, k) => {
    if (k === index) return;
    const shift = starts[k] - s.start;
    if (shift !== 0) changes.push({ id: s.id, start: starts[k], end: s.end === null ? null : s.end + shift });
  });
  return { end, changes, clamped, min: range.min, max: range.max };
}
