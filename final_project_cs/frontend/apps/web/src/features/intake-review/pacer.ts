import type { IntakeStreamEvent } from "@/lib/live/intake-events";

/**
 * The screen's pace. The server only keeps the ORDER of what it found (lines → stops → check lines → legs → done) and may send a
 * burst at once; the screen lines the events up and shows each for a moment, so a burst still reads as "one after another"
 * (2026-10-02 mockup, 「서버는 순서, 화면은 속도」). Nothing here changes what is shown — only when.
 *
 * - An event that adds something new waits its `GAP` after the one before it; a repeat of something already shown
 *   (a stop whose place was just found, a line the reconnect replayed) is applied at once.
 * - A stop's check lines are moved up behind that stop's card, and a leg behind the card it leads to — the server sends
 *   every stop first and every check line after, but the mockup shows each card with its lines.
 * - A long backlog is shortened (never past `MAX_BACKLOG_MS` in all), so the pace never keeps the customer waiting after the
 *   server has finished.
 */

/** Milliseconds a new thing waits after the previous one — the mockup's timings (`T.lineGap` 500, `T.item` 800, `T.rowGap` 350 …). */
export const GAP_MS: Record<IntakeStreamEvent["type"], number> = {
  accepted: 0, stage: 0, beat: 0, result: 0, error: 0, line: 450, item: 700, check: 300, move: 600, done: 500,
};
/** The most a burst may take to show: a plan with fifty lines is not shown line by line for half a minute. */
export const MAX_BACKLOG_MS = 7_000;
/** How long the first event of a burst waits, so everything that arrived together is lined up before the first is shown. */
export const SETTLE_MS = 40;
const FLOOR = 0.2;

/** The key of what an event adds to the screen; the same key again is a repeat. */
export function newnessKey(event: IntakeStreamEvent): string | null {
  switch (event.type) {
    case "line": return `line:${event.line.source_id}:${event.line.no}`;
    case "item": return `item:${event.item.id}`;
    case "check": return `check:${event.item}:${event.line.row}`;
    case "move": return `move:${event.move.from}:${event.move.to}`;
    case "done": return "done";
    default: return null;
  }
}

/** The stop an event belongs to on the screen (a leg belongs to the stop it leads to), or null. */
function ownerOf(event: IntakeStreamEvent): string | null {
  switch (event.type) {
    case "item": return event.item.id;
    case "check": return event.item;
    case "move": return event.move.to;
    default: return null;
  }
}

export interface Timer { (run: () => void, ms: number): () => void }

export interface Pacer {
  push(event: IntakeStreamEvent): void;
  /** How many events are waiting to be shown. */
  readonly pending: number;
  /** Show everything waiting now (the customer asked for less motion, or the screen is leaving). */
  flush(): void;
  stop(): void;
}

export function createPacer({ show, onBusy, setTimer = (run, ms) => { const id = setTimeout(run, ms); return () => clearTimeout(id); }, now = () => Date.now(), instant = false }: {
  show: (event: IntakeStreamEvent) => void;
  /** Called with true when events start waiting and with false once the last one has been shown. */
  onBusy?: (busy: boolean) => void;
  setTimer?: Timer;
  now?: () => number;
  /** Less motion: every event is shown as it arrives. */
  instant?: boolean;
}): Pacer {
  const queue: { event: IntakeStreamEvent; gap: number }[] = [];
  const known = new Set<string>();                 // what has been queued or shown — a repeat of it waits for nothing
  let cancel: (() => void) | null = null;
  let lastShown = -Infinity;
  let busy = false;
  let readyAt = 0;                                 // the first event of a burst is not shown before this
  let burstStart = 0;

  const setBusy = (next: boolean) => {
    if (busy === next) return;
    busy = next;
    if (next) { burstStart = now(); readyAt = burstStart + SETTLE_MS; }
    onBusy?.(next);
  };

  /** What is left of the burst must fit in what is left of `MAX_BACKLOG_MS` since it began — so the pace speeds up as a long one goes on. */
  function backlogScale(): number {
    const total = queue.reduce((sum, entry) => sum + entry.gap, 0);
    const timeLeft = Math.max(0, burstStart + MAX_BACKLOG_MS - now());
    return total <= timeLeft ? 1 : Math.max(FLOOR, timeLeft / total);
  }

  function release() {
    cancel = null;
    const head = queue.shift();
    if (!head) { setBusy(false); return; }
    lastShown = now();
    show(head.event);
    next();
  }

  function next() {
    if (cancel) return;
    const head = queue[0];
    if (!head) { setBusy(false); return; }
    const wait = Math.max(0, Math.max(lastShown + head.gap * backlogScale(), readyAt) - now());
    if (wait <= 0) { release(); return; }
    cancel = setTimer(release, wait);
  }

  /** Where a new event goes in the queue: behind the last waiting event of the stop it belongs to, else at the end. */
  function slot(event: IntakeStreamEvent): number {
    const owner = event.type === "check" || event.type === "move" ? ownerOf(event) : null;
    if (!owner) return queue.length;
    for (let index = queue.length - 1; index >= 0; index -= 1) if (ownerOf(queue[index].event) === owner) return index + 1;
    return queue.length;
  }

  return {
    push(event) {
      if (instant) { show(event); return; }
      const key = newnessKey(event);
      const isNew = key !== null && !known.has(key);
      if (key) known.add(key);
      queue.splice(slot(event), 0, { event, gap: isNew ? GAP_MS[event.type] : 0 });
      setBusy(true);
      next();
    },
    get pending() { return queue.length; },
    flush() {
      cancel?.(); cancel = null;
      while (queue.length) show(queue.shift()!.event);
      setBusy(false);
    },
    stop() { cancel?.(); cancel = null; queue.length = 0; setBusy(false); },
  };
}
