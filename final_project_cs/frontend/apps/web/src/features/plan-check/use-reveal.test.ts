import { afterEach, describe, expect, it, vi } from "vitest";
import { exampleDone, exampleSnapshots, readAgain } from "./test-views";
import { nextStep, stopKind, STAGES, type PlanCheckView } from "./model";
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
    hooks.slots[at] ??= { value: typeof initial === "function" ? (initial as () => T)() : initial };
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

function draw(target: PlanCheckView, paused = false, stops = false) {
  let result: ReturnType<typeof useReveal>;
  do {
    hooks.again = false;
    hooks.cursor = 0;
    hooks.pending = [];
    // eslint-disable-next-line react-hooks/rules-of-hooks -- Node test harness replays renders with mocked hooks; this is not a React component.
    result = useReveal(target, paused, stops);
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
    expect(draw(saved)).toMatchObject({ view: saved, settled: true });
    expect(vi.getTimerCount()).toBe(0);
    // A paused next update must keep the saved times, not revive the original snapshot stored before the edit.
    const paused = draw(exampleDone, true);
    expect(paused.view.items.map((item) => item.startsAt)).toEqual(saved.items.map((item) => item.startsAt));
    expect(paused.settled).toBe(false);
    vi.advanceTimersByTime(5_000);
    expect(draw(exampleDone, true).view.items).toEqual(saved.items);
    expect(draw(exampleDone)).toMatchObject({ view: exampleDone, settled: true });
  });

  it("keeps the first checking-to-done transition paced until its stage hold ends", () => {
    vi.useFakeTimers();
    const checking: PlanCheckView = { ...exampleDone, stage: "checking" };
    draw(checking);
    expect(draw(exampleDone).view.stage).toBe("checking");
    vi.advanceTimersByTime(STAGE_MIN_MS - 1);
    expect(draw(exampleDone).settled).toBe(false);
    vi.advanceTimersByTime(1);
    expect(draw(exampleDone)).toMatchObject({ view: exampleDone, settled: true });
  });

  it("reveals the first map cards after a survey without replaying completed reading", () => {
    vi.useFakeTimers();
    draw(received);
    expect(draw(exampleDone, true)).toMatchObject({ view: received, settled: false });
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
    expect(draw(exampleDone)).toMatchObject({ view: exampleDone, settled: true });
  });

  it("respects explicit animation skipping when questions release", () => {
    vi.useFakeTimers();
    draw(received);
    draw(exampleDone, true);
    hooks.skip = true;
    expect(draw(exampleDone)).toMatchObject({ view: exampleDone, settled: true });
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
    expect(draw(exampleDone)).toMatchObject({ view: exampleDone, settled: true });
    hooks.skip = false;
    expect(draw(exampleDone, true).view).toBe(exampleDone);
    expect(draw(exampleDone)).toMatchObject({ view: exampleDone, settled: true });
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

describe("`[2026-10-20 C안]` stopping at a card that needs a look, and going on after a pick", () => {
  const checking: PlanCheckView = { ...exampleDone, stage: "checking", title: null, items: [], moves: [] };
  /** Let the timers run until `until` holds (or give up). */
  function run(target: PlanCheckView, until: (result: ReturnType<typeof useReveal>) => boolean) {
    let result = draw(target, false, true);
    for (let step = 0; step < 200 && !until(result); step += 1) { vi.advanceTimersByTime(100); result = draw(target, false, true); }
    return result;
  }

  it("continues after an explicit hours caution acknowledgement, retains warnings, and asks again after time changes", () => {
    vi.useFakeTimers();
    hooks.skip = true;
    draw(checking, false, true);
    const item = { ...exampleDone.items[0], verdict: "review" as const, placeState: "found", checks: [
      { kind: "place" as const, result: "ok" as const, text: "고객 선택" },
      { kind: "hours" as const, result: "warn" as const, text: "마지막 주문 확인", canAcknowledge: true },
    ] };
    const target = { ...exampleDone, items: [item], moves: [] };
    const before = draw(target, false, true);
    expect(before.stop?.id).toBe(item.id);
    before.recheck.acknowledgeHours(item.id);
    const after = draw(target, false, true);
    expect(after.stop).toBeNull();
    expect(after.settled).toBe(true);
    expect(after.view.items[0]).toEqual(item);
    const changed = draw({ ...target, items: [{ ...item, startsAt: "11:15" }] }, false, true);
    expect(changed.recheck.isHoursAcknowledged(changed.view.items[0])).toBe(false);
  });

  it("keeps a late arrival blocking after hours are acknowledged", () => {
    vi.useFakeTimers();
    hooks.skip = true;
    draw(checking, false, true);
    const item = { ...exampleDone.items[1], place: "566라멘", coordinates: { lat: 37.57, lng: 126.98 }, placeState: "found", checks: [
      { kind: "place" as const, result: "ok" as const, text: "고객 선택" },
      { kind: "hours" as const, result: "warn" as const, text: "마지막 주문 확인", canAcknowledge: true },
    ] };
    const target = { ...exampleDone, items: [exampleDone.items[0], item], moves: [exampleDone.moves[0]] };
    draw(target, false, true).recheck.acknowledgeHours(item.id);
    const result = draw(target, false, true);
    expect(result.stop?.id).toBe(item.id);
    expect(result.settled).toBe(false);
    expect(stopKind(result.view, item.id, result.recheck.isHoursAcknowledged)).toBe("arrival");
  });

  it("stops at the card that needs a look: nothing past it is drawn, and it is not settled", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    const stopped = run(exampleDone, (result) => result.stop !== null);
    expect(stopped.stop).toEqual({ id: "b", settling: false });
    expect(stopped.settled).toBe(false);
    vi.advanceTimersByTime(10_000);
    const still = draw(exampleDone, false, true);
    expect(still.view.items.map((item) => item.id)).toEqual(["a", "b"]);
    expect(still.settled).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("waits for the server after a pick, ticks the card's new checks in where it stands, and goes on when it passes", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    run(exampleDone, (result) => result.stop !== null).recheck.begin("b");
    const asked = draw(exampleDone, false, true);
    expect(asked.stop).toEqual({ id: "b", settling: true });
    expect(asked.view.items.find((item) => item.id === "b")!.checks.every((row) => row.result === "pending" && row.text)).toBe(true);
    vi.advanceTimersByTime(5_000);
    expect(draw(exampleDone, false, true).view.items.find((item) => item.id === "b")!.checks[0].result).toBe("pending");   // not before the answer
    const fixed: PlanCheckView = { ...exampleDone, revision: 2, items: exampleDone.items.map((item) => item.id !== "b" ? item
      : { ...item, verdict: "keep", checks: item.checks.map((row) => ({ ...row, result: "ok" as const })) }),
      moves: exampleDone.moves.map((move) => move.id === "a-b" ? { ...move, slackMin: 3, verdict: "keep" as const } : move) };    // the way in on time too (a late one stops again)
    const done = run(fixed, (result) => result.settled);
    expect(done.view).toEqual(fixed);
    expect(done.stop).toBeNull();
  });

  it("puts the card back as the server has it when the pick is refused", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    run(exampleDone, (result) => result.stop !== null).recheck.begin("b");
    draw(exampleDone, false, true).recheck.fail("b");
    const back = draw(exampleDone, false, true);
    expect(back.view.items.find((item) => item.id === "b")).toEqual(exampleDone.items[1]);
    expect(back.stop).toEqual({ id: "b", settling: false });
  });

  it("`[2026-10-21 ST4F-703]` keeps asking when the server is read again while stopped: the drawn cards take its values, the stop stays and is not 「다시 확인하는 중」", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    run(exampleDone, (result) => result.stop !== null);
    // The 3-minute re-read: every stop's risk check stamped anew (the plan itself unchanged) — it used to hold the replay on card a and hide the question for good.
    const reread = readAgain(exampleDone, "2026-10-21T13:45:00+09:00");
    const after = draw(reread, false, true);
    expect(after.stop).toEqual({ id: "b", settling: false });
    expect(after.view.items).toEqual(reread.items.slice(0, 2));
    vi.advanceTimersByTime(10_000);
    const again = draw(readAgain(exampleDone, "2026-10-21T13:48:00+09:00"), false, true);
    expect(again.stop).toEqual({ id: "b", settling: false });
    expect(again.view.items.map((item) => item.id)).toEqual(["a", "b"]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("`[2026-10-21 ST4F-703]` goes on when a new read has the stopped card passed (fixed in another tab) — no pick needed", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    run(exampleDone, (result) => result.stop !== null);
    const elsewhere: PlanCheckView = readAgain({ ...exampleDone, revision: 2, items: exampleDone.items.map((item) => item.id !== "b" ? item
      : { ...item, title: "올리브영 광화문점", verdict: "keep", checks: item.checks.map((row) => ({ ...row, result: "ok" as const })) }),
      moves: exampleDone.moves.map((move) => move.id === "a-b" ? { ...move, slackMin: 3, verdict: "keep" as const } : move) }, "2026-10-21T13:45:00+09:00");
    expect(draw(elsewhere, false, true).stop).toBeNull();
    const done = run(elsewhere, (result) => result.settled);
    expect(done.view).toEqual(elsewhere);
  });

  it("`[2026-10-21 ST4F-703]` still ticks the picked card's checks in one by one when the server is read again meanwhile", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    run(exampleDone, (result) => result.stop !== null).recheck.begin("b");
    draw(exampleDone, false, true);
    const fixed: PlanCheckView = { ...exampleDone, revision: 2, items: exampleDone.items.map((item) => item.id !== "b" ? item
      : { ...item, verdict: "keep", checks: item.checks.map((row) => ({ ...row, result: "ok" as const })) }),
      moves: exampleDone.moves.map((move) => move.id === "a-b" ? { ...move, slackMin: 3, verdict: "keep" as const } : move) };
    const answered = draw(fixed, false, true);
    expect(answered.stop).toEqual({ id: "b", settling: true });
    const reread = readAgain(fixed, "2026-10-21T13:45:00+09:00");
    const meanwhile = draw(reread, false, true);
    expect(meanwhile.stop).toEqual({ id: "b", settling: true });
    expect(meanwhile.view.items[0]).toEqual(reread.items[0]);                                  // card a takes the new read at once
    expect(meanwhile.view.items[1].checks.some((row) => row.result === "pending")).toBe(true);  // card b keeps stepping
    const results: string[] = [];
    const done = run(reread, (result) => { results.push(result.view.items[1]?.checks.map((row) => row.result).join(",")); return result.settled; });
    expect(new Set(results).size).toBeGreaterThan(2);                                          // its checks came in one at a time
    expect(done.view).toEqual(reread);
  });

  it("`[2026-10-22 문제 줄에서 멈추기]` draws the stopped card down to its stop row only, keeps it while the card is checked again, and lets go once it passes", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    const seen: (string | null)[] = [];
    const stopped = run(exampleDone, (result) => { seen.push(result.rowCut ? JSON.stringify(result.rowCut) : null); return result.stop !== null; });
    expect(stopped.rowCut).toEqual({ id: "b", row: 0, hide: true });
    expect(stopped.view.items.find((item) => item.id === "b")).toEqual(exampleDone.items[1]);      // the server's own rows and words, only not drawn below row 0
    expect(seen.filter(Boolean).every((cut) => cut === JSON.stringify({ id: "b", row: 0, hide: true }))).toBe(true);   // before the verdict too: no row below comes and goes
    stopped.recheck.begin("b");
    expect(draw(exampleDone, false, true).rowCut).toEqual({ id: "b", row: 0, hide: false });
    const fixed: PlanCheckView = { ...exampleDone, revision: 2, items: exampleDone.items.map((item) => item.id !== "b" ? item
      : { ...item, verdict: "keep", checks: item.checks.map((row) => ({ ...row, result: "ok" as const })) }),
      moves: exampleDone.moves.map((move) => move.id === "a-b" ? { ...move, slackMin: 3, verdict: "keep" as const } : move) };
    expect(draw(fixed, false, true).rowCut).toEqual({ id: "b", row: 0, hide: false });
    expect(run(fixed, (result) => result.settled).rowCut).toBeNull();
  });

  it("`[2026-10-22]` after a pick keeps only the rows the new plan has again in the same place — a row of another check comes as a new one", () => {
    vi.useFakeTimers();
    draw(checking, false, true);
    run(exampleDone, (result) => result.stop !== null).recheck.begin("b");
    draw(exampleDone, false, true);
    const reshaped: PlanCheckView = { ...exampleDone, revision: 2, items: exampleDone.items.map((item) => item.id !== "b" ? item
      : { ...item, verdict: "keep", checks: [{ kind: "arrival", result: "ok", text: "제때 닿아요" }, { kind: "place", result: "ok", text: "고른 곳이에요" }] }),
      moves: exampleDone.moves.map((move) => move.id === "a-b" ? { ...move, slackMin: 3, verdict: "keep" as const } : move) };
    expect(draw(reshaped, false, true).rowCut).toEqual({ id: "b", row: -1, hide: false });
  });

  it("does not stop where the page cannot change places", () => {
    vi.useFakeTimers();
    draw(checking);
    let result = draw(exampleDone);
    for (let step = 0; step < 300 && !result.settled; step += 1) { vi.advanceTimersByTime(100); result = draw(exampleDone); }
    expect(result).toMatchObject({ view: exampleDone, settled: true, stop: null });
  });
});

