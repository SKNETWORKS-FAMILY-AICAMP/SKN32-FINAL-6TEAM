import { afterEach, describe, expect, it, vi } from "vitest";
import { exampleDone, exampleSnapshots } from "./test-views";
import { nextStep, STAGES, type PlanCheckView } from "./model";
import { FIRST_CARD_MS, FOLD_MS, linesBacklog, pauseBefore, READ_BUDGET_MS, READ_MIN_MS, readPause, REVEAL_MS, ROW_MS, ROWS_LEAD_MS, STAGE_MIN_MS, stepMany, useReveal, VERDICT_MS } from "./use-reveal";

// Exercise the hook's timer/state boundary in Node; the live tests cover React and browser rendering.
const hooks = vi.hoisted(() => ({
  slots: [] as { value?: unknown; deps?: readonly unknown[]; cleanup?: () => void }[],
  pending: [] as { slot: number; run: () => void | (() => void) }[],
  cursor: 0, again: false, skip: false,
}));
vi.mock("@/lib/settings", () => ({ useSettings: () => ({ skipAnimation: hooks.skip }) }));
vi.mock("react", () => ({
  useState: <T>(initial: T) => {
    const at = hooks.cursor++;
    hooks.slots[at] ??= { value: initial };
    return [hooks.slots[at].value, (value: T | ((current: T) => T)) => {
      const next = typeof value === "function" ? (value as (current: T) => T)(hooks.slots[at].value as T) : value;
      if (Object.is(next, hooks.slots[at].value)) return;
      hooks.slots[at].value = next;
      hooks.again = true;
    }];
  },
  useRef: <T>(initial: T) => {
    const at = hooks.cursor++;
    hooks.slots[at] ??= { value: { current: initial } };
    return hooks.slots[at].value;
  },
  useMemo: <T>(make: () => T) => make(),
  useEffect: (run: () => void | (() => void), deps: readonly unknown[]) => {
    const at = hooks.cursor++;
    const slot = hooks.slots[at] ??= {};
    if (slot.deps && deps.length === slot.deps.length && deps.every((value, index) => Object.is(value, slot.deps![index]))) return;
    // Discarded renders do not commit effect dependencies in React.
    hooks.pending.push({ slot: at, run: () => { slot.deps = deps; return run(); } });
  },
}));

function draw(target: PlanCheckView, paused = false) {
  let result: ReturnType<typeof useReveal>;
  do {
    hooks.again = false;
    hooks.cursor = 0;
    hooks.pending = [];
    // eslint-disable-next-line react-hooks/rules-of-hooks -- Node test harness replays renders with mocked hooks; this is not a React component.
    result = useReveal(target, paused);
  } while (hooks.again);
  for (const effect of hooks.pending) {
    hooks.slots[effect.slot].cleanup?.();
    const cleanup = effect.run();
    hooks.slots[effect.slot].cleanup = typeof cleanup === "function" ? cleanup : undefined;
  }
  return result;
}

afterEach(() => {
  for (const slot of hooks.slots) slot.cleanup?.();
  hooks.slots = [];
  hooks.pending = [];
  hooks.cursor = 0;
  hooks.again = false;
  hooks.skip = false;
  vi.useRealTimers();
});

const received = exampleSnapshots[0].view;

describe("saved edits and paused replay", () => {
  it("shows every saved time together and keeps that snapshot if a survey pauses the next update", () => {
    vi.useFakeTimers();
    draw(exampleDone);
    const saved = { ...exampleDone, items: exampleDone.items.map((item) => ({ ...item, startsAt: "08:35", endsAt: "10:05" })) };
    expect(draw(saved)).toEqual({ view: saved, settled: true });
    expect(vi.getTimerCount()).toBe(0);
    // A paused next update must keep the saved times, not revive the original snapshot stored before the edit.
    const paused = draw(exampleDone, true);
    expect(paused.view.items.map((item) => item.startsAt)).toEqual(saved.items.map((item) => item.startsAt));
    expect(paused.settled).toBe(false);
    vi.advanceTimersByTime(5_000);
    expect(draw(exampleDone, true).view.items).toEqual(saved.items);
    expect(draw(exampleDone)).toEqual({ view: exampleDone, settled: true });
  });

  it("keeps the first checking-to-done transition paced until its stage hold ends", () => {
    vi.useFakeTimers();
    const checking: PlanCheckView = { ...exampleDone, stage: "checking" };
    draw(checking);
    expect(draw(exampleDone).view.stage).toBe("checking");
    vi.advanceTimersByTime(STAGE_MIN_MS - 1);
    expect(draw(exampleDone).settled).toBe(false);
    vi.advanceTimersByTime(1);
    expect(draw(exampleDone)).toEqual({ view: exampleDone, settled: true });
  });

  it("reveals the first map cards after a survey without replaying completed reading", () => {
    vi.useFakeTimers();
    draw(received);
    expect(draw(exampleDone, true)).toEqual({ view: received, settled: false });
    vi.advanceTimersByTime(5_000);
    expect(draw(exampleDone, true).view).toBe(received);
    expect(vi.getTimerCount()).toBe(0);
    const first = draw(exampleDone);
    expect(first.view).toMatchObject({ stage: "checking", items: [], moves: [], lines: exampleDone.lines });
    expect(first.settled).toBe(false);
    const counts = [first.view.items.length];
    for (let step = 0; step < 100; step += 1) {
      vi.advanceTimersByTime(300);
      const next = draw(exampleDone);
      expect(["checking", "done"]).toContain(next.view.stage);
      counts.push(next.view.items.length);
      if (next.settled) break;
    }
    expect(counts.some((count) => count > 0 && count < exampleDone.items.length)).toBe(true);
    expect(draw(exampleDone)).toEqual({ view: exampleDone, settled: true });
  });

  it("respects explicit animation skipping when questions release", () => {
    vi.useFakeTimers();
    draw(received);
    draw(exampleDone, true);
    hooks.skip = true;
    expect(draw(exampleDone)).toEqual({ view: exampleDone, settled: true });
    expect(vi.getTimerCount()).toBe(0);
  });

  it("still paces unfinished progress after a survey releases its hold", () => {
    vi.useFakeTimers();
    draw(received);
    const checking = { ...exampleDone, stage: "checking" as const };
    draw(checking, true);
    expect(draw(checking).settled).toBe(false);
    expect(vi.getTimerCount()).toBe(1);
  });

  it("does not revive the old plan when animation skipping is turned off or a survey opens", () => {
    vi.useFakeTimers();
    draw(received);
    hooks.skip = true;
    expect(draw(exampleDone)).toEqual({ view: exampleDone, settled: true });
    hooks.skip = false;
    expect(draw(exampleDone, true).view).toBe(exampleDone);
    expect(draw(exampleDone)).toEqual({ view: exampleDone, settled: true });
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("how fast the plan check draws what the server sent", () => {
  it("`[2026-10-20 C안]` draws the first check at the chosen pace: the first card 0.7 s, its first line 0.65 s, each line 0.26 s, the verdict 0.28 s, the next card 0.45 s", () => {
    expect([FIRST_CARD_MS, ROWS_LEAD_MS, ROW_MS, VERDICT_MS, FOLD_MS]).toEqual([700, 650, 260, 280, 450]);
    let shown: PlanCheckView = { ...exampleDone, stage: "checking", title: null, items: [], moves: [] };
    const pauses: number[] = [];
    for (let next = nextStep(shown, exampleDone); next; next = nextStep(shown, exampleDone)) { pauses.push(pauseBefore(shown, next)); shown = next; }
    expect(pauses).toEqual([
      700, 650, 260, 260, 280,           // a: the card, its three lines, the verdict
      450, 650, 260, 260, 260, 280,      // b, with the leg to it: the card, its four lines, the verdict
      450, 650, 260, 260, 260, 280,      // c, with the leg to it
      450, 650, 260, 260, 280,           // d
      260, 260,                          // done, the title
    ]);
  });

  it("`[2026-10-20 C안]` keeps the same pace however long the plan is (no time budget, no card-by-card drawing)", () => {
    const many = (count: number): PlanCheckView => ({ ...exampleDone, items: Array.from({ length: count }, (_, at) => ({ ...exampleDone.items[0], id: `s${at}`, startsAt: `${String(8 + Math.floor(at / 4)).padStart(2, "0")}:${String((at % 4) * 15).padStart(2, "0")}` })), moves: [] });
    const pacesOf = (target: PlanCheckView) => {
      let shown: PlanCheckView = { ...target, stage: "checking", title: null, items: [], moves: [] };
      const out = new Set<number>();
      for (let next = nextStep(shown, target); next; next = nextStep(shown, target)) { out.add(pauseBefore(shown, next)); shown = next; }
      return [...out].sort((x, y) => x - y);
    };
    expect(pacesOf(many(40))).toEqual(pacesOf(many(3)));
  });

  it("reads the lines at a pace of their own — all of them in about the reading budget, one step at a time, never flashing by", () => {
    expect(readPause(0)).toBe(REVEAL_MS);                                   // nothing waiting: the longest pause
    expect(readPause(10)).toBe(REVEAL_MS);                                  // a short plan: each step is the full pause
    const work = 34;                                                         // 17 lines, each appearing and then read
    expect(readPause(work)).toBeLessThan(REVEAL_MS);
    expect(readPause(work) * work).toBeLessThanOrEqual(READ_BUDGET_MS * 1.05);
    expect(readPause(work)).toBeGreaterThan(READ_MIN_MS);
    expect(readPause(100_000)).toBe(READ_MIN_MS);
  });

  it("counts only the reading steps left: a line to appear, a line to tick off — none once the lines are drawn", () => {
    const unread: PlanCheckView = { ...received, lines: received.lines.map((line) => ({ ...line, read: false })) };
    expect(linesBacklog(exampleDone, exampleDone)).toBe(0);
    expect(linesBacklog({ ...unread, lines: [] }, exampleDone)).toBe(exampleDone.lines.length * 2);          // none drawn yet: appear, then read
    expect(linesBacklog(unread, exampleDone)).toBe(exampleDone.lines.filter((line) => line.read).length);      // all there, none read
  });

  it("steps several changes toward the target at once, stopping at the target, and says nothing is left when it is there", () => {
    const left = (from: PlanCheckView) => { let count = 0; for (let view = from, next = nextStep(view, exampleDone); next; view = next, next = nextStep(view, exampleDone)) count += 1; return count; };
    const one = stepMany(received, exampleDone, 1);
    const many = stepMany(received, exampleDone, 5);
    expect(one).toEqual(nextStep(received, exampleDone));
    expect(left(many!)).toBeLessThan(left(one!));
    // however many it is asked for, it goes on stage by stage and ends exactly at the target — never past it
    let view: PlanCheckView = received;
    for (let batch = stepMany(view, exampleDone, 100_000); batch; batch = stepMany(view, exampleDone, 100_000)) view = batch;
    expect(view).toEqual(exampleDone);
    expect(stepMany(exampleDone, exampleDone, 5)).toBeNull();
  });

  it("never carries a batch across a stage of the top bar: the change of stage is the first step of the next batch (which waits its minimum)", () => {
    let view: PlanCheckView = received;
    for (let batch = stepMany(view, exampleDone, 100_000); batch; batch = stepMany(view, exampleDone, 100_000)) {
      const crossings = STAGES.indexOf(batch.stage) - STAGES.indexOf(view.stage);
      expect(crossings).toBeLessThanOrEqual(1);                                   // at most one stage per batch
      view = batch;
    }
  });

  it("holds each stage of the top bar for at least the minimum before it moves on", () => {
    expect(STAGE_MIN_MS).toBeGreaterThanOrEqual(800);
  });
});
