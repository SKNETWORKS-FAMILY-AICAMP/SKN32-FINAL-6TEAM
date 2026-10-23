import { occupancy, slackAfter, settledAfter, type Retime, type TimedLeg, type TimedStop } from "./time-plan";

/**
 * `[2026-10-05 사용자 지시]` The whole day as a strip, while a time is being dragged: every stop of the day where it was (outline) and where it would stand now (filled), so the
 * customer sees how much of the day the drag moves. Pure (no React): the screen draws what this says.
 */
export interface MiniBlock {
  id: string;
  /** Where the stop stood and where it would stand, minutes since midnight. */
  before: { start: number; end: number };
  after: { start: number; end: number };
  /** Minutes the stop moves (negative = earlier); 0 = stays. */
  shift: number;
  fixed: boolean;
  /** The stop being dragged. */
  active: boolean;
}

export interface Minimap {
  /** The strip's first and last minute (half hours, a quarter of an hour of room around the stops). */
  from: number;
  to: number;
  blocks: MiniBlock[];
  /** How many OTHER stops move, and the largest move among them (minutes, sign kept; 0 when none). */
  pushed: number;
  largestPush: number;
  /** When the day's last stop ends: as it was and as it would be. */
  dayEnd: { before: number; after: number };
  /** Free minutes after the dragged stop once the change is in (null for the last stop of the day). */
  slackAfter: number | null;
}

/** Clamp a minute into the day. */
const inDay = (minutes: number) => Math.min(1440, Math.max(0, minutes));

export function minimap(stops: readonly TimedStop[], legs: readonly TimedLeg[], changes: readonly Retime[], activeId: string): Minimap {
  const byId = new Map(changes.map((change) => [change.id, change]));
  const blocks: MiniBlock[] = stops.map((stop) => {
    const change = byId.get(stop.id);
    const before = { start: stop.start, end: stop.start + occupancy(stop) };
    const after = change ? { start: change.start, end: change.end === null ? change.start + occupancy(stop) : change.end } : before;
    return { id: stop.id, before, after, shift: after.start - before.start, fixed: stop.fixed, active: stop.id === activeId };
  });
  const starts = blocks.flatMap((block) => [block.before.start, block.after.start]);
  const ends = blocks.flatMap((block) => [block.before.end, block.after.end]);
  const from = starts.length ? Math.floor(inDay(Math.min(...starts) - 15) / 30) * 30 : 0;
  const to = ends.length ? Math.max(from + 60, Math.ceil(inDay(Math.max(...ends) + 15) / 30) * 30) : from + 60;
  const others = blocks.filter((block) => !block.active && (block.shift !== 0 || block.after.end !== block.before.end));
  const largestPush = others.reduce((largest, block) => Math.abs(block.shift) > Math.abs(largest) ? block.shift : largest, 0);
  const last = blocks[blocks.length - 1];
  const index = stops.findIndex((stop) => stop.id === activeId);
  const settled = settledAfter(stops, changes);
  return {
    from, to, blocks, pushed: others.length, largestPush,
    dayEnd: { before: last ? last.before.end : 0, after: last ? last.after.end : 0 },
    slackAfter: index >= 0 ? slackAfter(settled, legs, index) : null,
  };
}
