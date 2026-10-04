import { describe, expect, it } from "vitest";
import { exampleDone, exampleSnapshots } from "./test-views";
import { nextStep, STAGES, type PlanCheckView } from "./model";
import { backlog, cardBacklog, COARSE_MIN_MS, linesBacklog, READ_BUDGET_MS, READ_MIN_MS, readPause, REVEAL_BUDGET_MS, REVEAL_MIN_MS, REVEAL_MS, revealPlan, STAGE_MIN_MS, stepMany } from "./use-reveal";

const received = exampleSnapshots[0].view;

describe("how fast the plan check draws what the server sent", () => {
  it("counts what is waiting to be drawn, and none once everything is drawn", () => {
    expect(backlog(exampleDone, exampleDone)).toBe(0);
    expect(cardBacklog(exampleDone, exampleDone)).toBe(0);
    // One drawn change per step: the count falls as the screen walks to the target and ends at zero.
    let shown: PlanCheckView = received;
    let last = backlog(shown, exampleDone);
    expect(last).toBeGreaterThan(20);
    for (let step = nextStep(shown, exampleDone); step; step = nextStep(shown, exampleDone)) {
      shown = step;
      const now = backlog(shown, exampleDone);
      expect(now).toBeLessThanOrEqual(last);
      last = now;
    }
    expect(last).toBe(0);
  });

  it("counts about the steps nextStep takes (the days and the title are not counted), so the pace is worked out from the real number of draws", () => {
    let shown: PlanCheckView = received;
    let steps = 0;
    for (let step = nextStep(shown, exampleDone); step; step = nextStep(shown, exampleDone)) { shown = step; steps += 1; }
    expect(steps - backlog(received, exampleDone)).toBe(2);                    // the step that sets the days, and the one that sets the title
  });

  it("`[2026-10-04]` draws a small plan one check at a time, 300 ms between two — slow enough to see which check came in", () => {
    expect(REVEAL_MS).toBe(300);
    expect(revealPlan(0, 0)).toEqual({ pause: REVEAL_MS, coarse: false });
    expect(revealPlan(10, 5)).toEqual({ pause: REVEAL_MS, coarse: false });
    // The example plan (4 places, 2 moves): the whole replay is well inside the budget at the full pause.
    const plan = revealPlan(backlog(received, exampleDone), cardBacklog(received, exampleDone));
    expect(plan).toEqual({ pause: REVEAL_MS, coarse: false });
    expect(backlog(received, exampleDone) * REVEAL_MS).toBeLessThanOrEqual(REVEAL_BUDGET_MS);
  });

  it("shortens the pause only down to the least a check needs to be seen — a bigger plan is drawn card by card instead, never faster line by line", () => {
    const fine = revealPlan(60, 30);
    expect(fine.coarse).toBe(false);
    expect(fine.pause).toBeGreaterThanOrEqual(REVEAL_MIN_MS);
    expect(fine.pause).toBeLessThan(REVEAL_MS);
    const big = revealPlan(200, 40);
    expect(big.coarse).toBe(true);
    expect(big.pause).toBe(REVEAL_MS);                                       // 40 cards at 300 ms = 12 s, inside the budget
    expect(revealPlan(400, 400)).toEqual({ pause: COARSE_MIN_MS, coarse: true });   // a huge plan: the floor, never lower
    expect(revealPlan(400, 100).pause * 100).toBeLessThanOrEqual(REVEAL_BUDGET_MS * 1.05);
  });

  it("reads the lines at a pace of their own — all of them in about the reading budget, one step at a time, never flashing by", () => {
    expect(readPause(0)).toBe(REVEAL_MS);                                   // nothing waiting: the longest pause
    expect(readPause(10)).toBe(REVEAL_MS);                                  // a short plan: each step is the full pause
    const work = 34;                                                         // 17 lines, each appearing and then read
    expect(readPause(work)).toBeLessThan(REVEAL_MS);
    expect(readPause(work) * work).toBeLessThanOrEqual(READ_BUDGET_MS * 1.05);
    expect(readPause(work)).toBeGreaterThan(REVEAL_MIN_MS * 0.5);
    expect(readPause(100_000)).toBe(READ_MIN_MS);
  });

  it("counts only the reading steps left: a line to appear, a line to tick off — none once the lines are drawn", () => {
    const unread: PlanCheckView = { ...received, lines: received.lines.map((line) => ({ ...line, read: false })) };
    expect(linesBacklog(exampleDone, exampleDone)).toBe(0);
    expect(linesBacklog({ ...unread, lines: [] }, exampleDone)).toBe(exampleDone.lines.length * 2);          // none drawn yet: appear, then read
    expect(linesBacklog(unread, exampleDone)).toBe(exampleDone.lines.filter((line) => line.read).length);      // all there, none read
  });

  it("steps several changes toward the target at once, stopping at the target, and says nothing is left when it is there", () => {
    const one = stepMany(received, exampleDone, 1);
    const many = stepMany(received, exampleDone, 5);
    expect(one).toEqual(nextStep(received, exampleDone));
    expect(backlog(many!, exampleDone)).toBeLessThan(backlog(one!, exampleDone));
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
