import { describe, expect, it } from "vitest";
import { exampleDone, exampleSnapshots } from "./test-views";
import { nextStep, type PlanCheckView } from "./model";
import { backlog, REVEAL_BUDGET_MS, REVEAL_MIN_MS, REVEAL_MS, REVEAL_TICK_COST_MS, revealBatch, revealPause, stepMany } from "./use-reveal";

const received = exampleSnapshots[0].view;

describe("how fast the plan check draws what the server sent", () => {
  it("counts what is waiting to be drawn, and none once everything is drawn", () => {
    expect(backlog(exampleDone, exampleDone)).toBe(0);
    // One drawn change per step: the count falls as the screen walks to the target and ends at zero.
    let shown: PlanCheckView = received;
    let last = backlog(shown, exampleDone);
    expect(last).toBeGreaterThan(30);
    for (let step = nextStep(shown, exampleDone); step; step = nextStep(shown, exampleDone)) {
      shown = step;
      const now = backlog(shown, exampleDone);
      expect(now).toBeLessThanOrEqual(last);
      last = now;
    }
    expect(last).toBe(0);
  });

  it("keeps the full pause for a small plan and when nothing is waiting", () => {
    expect(revealPause(0)).toBe(REVEAL_MS);
    expect(revealPause(10)).toBe(REVEAL_MS);                                // a handful of changes: the longest pause (4 s / 10 = 400 ms)
    expect(revealPause(backlog(received, exampleDone))).toBeLessThan(REVEAL_MS);   // ~43 changes: the whole is drawn in about 4 s
  });

  it("shortens the pause for a big plan so it is not drawn a minute behind the server, but never below the least a change needs to be seen", () => {
    const big: PlanCheckView = { ...exampleDone, items: Array.from({ length: 40 }, (_, at) => ({ ...exampleDone.items[0], id: `x${at}` })) };
    const waiting = backlog(received, big);
    expect(waiting).toBeGreaterThan(150);
    const pause = revealPause(waiting);
    expect(pause).toBeLessThan(REVEAL_MS);
    expect(pause).toBeGreaterThanOrEqual(REVEAL_MIN_MS);
    // The whole backlog, drawn a batch at a time with what each draw costs, takes about the budget (not a multiple of it).
    const ticks = Math.ceil(waiting / revealBatch(waiting));
    expect(ticks * (pause + REVEAL_TICK_COST_MS)).toBeLessThanOrEqual(REVEAL_BUDGET_MS * 1.2);
    expect(revealPause(100_000)).toBe(REVEAL_MIN_MS);
  });

  it("draws one change a tick while the backlog fits the budget, and more at a time when it does not", () => {
    expect(revealBatch(0)).toBe(1);
    expect(revealBatch(40)).toBe(1);
    expect(revealBatch(150)).toBeGreaterThan(1);
    expect(revealBatch(300)).toBeGreaterThan(revealBatch(150));
  });

  it("steps several changes toward the target at once, stopping at the target, and says nothing is left when it is there", () => {
    const one = stepMany(received, exampleDone, 1);
    const many = stepMany(received, exampleDone, 5);
    expect(one).toEqual(nextStep(received, exampleDone));
    expect(backlog(many!, exampleDone)).toBeLessThan(backlog(one!, exampleDone));
    expect(stepMany(received, exampleDone, 100_000)).toEqual(exampleDone);          // never past the target
    expect(stepMany(exampleDone, exampleDone, 5)).toBeNull();
  });
});
