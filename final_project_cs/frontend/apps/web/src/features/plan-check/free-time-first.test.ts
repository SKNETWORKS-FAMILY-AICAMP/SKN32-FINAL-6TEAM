import { describe, expect, it } from "vitest";
import { minimap } from "./day-minimap";
import { DETENT_MINUTES, endRanges, holdAtLimit, moveEnd, moveStop, ownRange, pushRange, type TimedLeg, type TimedStop } from "./time-plan";

/**
 * `[2026-10-05 사용자 지시]` 「여유부터 줄이고 · 다 쓰면 한 번 멈춰 안내 · 더 끌면 다음 일정이 하나씩 밀린다」 and the same for the time of leaving (the end of a stop). Pure maths, no screen.
 * Minutes since midnight: 540 = 09:00, 630 = 10:30, 660 = 11:00.
 */
const stop = (id: string, start: number, end: number | null, fixed = false): TimedStop => ({ id, start, end, fixed });
const leg = (fromId: string, toId: string, minutes: number): TimedLeg => ({ fromId, toId, minutes });

/** The mock plan: 경복궁 09:00-10:30, 올리브영 11:00-12:00, 광장시장 12:30-13:30; the way between takes 9 and 16 minutes. */
const DAY = [stop("a", 540, 630), stop("b", 660, 720), stop("c", 750, 810)];
const LEGS = [leg("a", "b", 9), leg("b", "c", 16)];

describe("holdAtLimit: the end of the free time is a place the drag stops at", () => {
  const own = { min: 500, max: 561 };
  const reach = { min: 400, max: 700 };
  it("is free inside the free time", () => {
    expect(holdAtLimit(530, own, reach)).toEqual({ value: 530, held: null });
    expect(holdAtLimit(561, own, reach)).toEqual({ value: 561, held: null });
  });
  it("holds at the later end for DETENT_MINUTES of dragging, then goes on pushing", () => {
    expect(holdAtLimit(565, own, reach)).toEqual({ value: 561, held: "max" });
    expect(holdAtLimit(561 + DETENT_MINUTES, own, reach)).toEqual({ value: 561, held: "max" });
    expect(holdAtLimit(561 + DETENT_MINUTES + 1, own, reach)).toEqual({ value: 562, held: null });
    expect(holdAtLimit(600, own, reach)).toEqual({ value: 590, held: null });                  // 39 past the end: 10 held, 29 on
  });
  it("holds at the earlier end the same way", () => {
    expect(holdAtLimit(495, own, reach)).toEqual({ value: 500, held: "min" });
    expect(holdAtLimit(500 - DETENT_MINUTES - 5, own, reach)).toEqual({ value: 495, held: null });
  });
  it("never goes past what pushing can reach", () => {
    expect(holdAtLimit(900, own, reach)).toEqual({ value: 700, held: null });
    expect(holdAtLimit(100, own, reach)).toEqual({ value: 400, held: null });
  });
  it("is only the end of the range when nobody can be pushed (a booked stop stands there)", () => {
    expect(holdAtLimit(580, own, { min: 400, max: 561 })).toEqual({ value: 561, held: null });
    expect(holdAtLimit(480, { min: 500, max: 561 }, { min: 500, max: 600 })).toEqual({ value: 500, held: null });
  });
});

describe("a start moved later: free time first, then the next stops one after the other", () => {
  it("moves nobody while the free time lasts (21 minutes after 경복궁)", () => {
    const result = moveStop(DAY, LEGS, 0, 561, { step: 1 });
    expect(result.changes.map((change) => change.id)).toEqual(["a"]);
    expect(ownRange(DAY, LEGS, 0, 1).max).toBe(561);                                           // 11:00 - 9 min - 90 min stay = 09:21: the free time is gone there
  });
  it("pushes the next stop by exactly what is needed once it is gone, then the one after it", () => {
    const result = moveStop(DAY, LEGS, 0, 575, { step: 1 });                                    // 14 minutes past the end of the free time
    expect(result.changes.map((change) => [change.id, change.start])).toEqual([["a", 575], ["b", 674]]);   // b needs 575 + 90 + 9 = 674; c (12:30) still fits: 674 + 60 + 16 = 750
    const further = moveStop(DAY, LEGS, 0, 585, { step: 1 });
    expect(further.changes.map((change) => [change.id, change.start])).toEqual([["a", 585], ["b", 684], ["c", 760]]);
  });
  it("never pushes across a booked stop: its place is the end of what pushing reaches", () => {
    const booked = [stop("a", 540, 630), stop("b", 660, 720, true), stop("c", 750, 810)];
    expect(pushRange(booked, LEGS, 0, 1).max).toBe(ownRange(booked, LEGS, 0, 1).max);
  });
});

describe("the time of leaving (the end of a stop)", () => {
  it("has a free range up to the next stop's start minus the way, and a reach that lets the stops behind be pushed", () => {
    const { own, reach } = endRanges(DAY, LEGS, 0, 1);
    expect(own).toEqual({ min: 541, max: 651 });                                                // leave between 09:01 and 10:51 (11:00 - 9 minutes)
    expect(reach.max).toBeGreaterThan(own.max);
    expect(reach.min).toBe(own.min);
  });
  it("leaving later uses the 21 free minutes first and moves nobody", () => {
    const result = moveEnd(DAY, LEGS, 0, 645, { step: 1 });                                    // 10:30 -> 10:45
    expect(result.changes).toEqual([{ id: "a", start: 540, end: 645 }]);
  });
  it("past the free time the next stops are pushed one after the other", () => {
    const result = moveEnd(DAY, LEGS, 0, 660, { step: 1 });                                    // leaving at 11:00: arrives 11:09, b starts 11:09
    expect(result.changes.map((change) => [change.id, change.start, change.end])).toEqual([["a", 540, 660], ["b", 669, 729]]);                 // c (12:30) still fits: nothing more is pushed
    const more = moveEnd(DAY, LEGS, 0, 690, { step: 1 });
    expect(more.changes.map((change) => [change.id, change.start])).toEqual([["a", 540], ["b", 699], ["c", 775]]);
  });
  it("leaving earlier only lengthens the free time", () => {
    const result = moveEnd(DAY, LEGS, 0, 600, { step: 1 });
    expect(result.changes).toEqual([{ id: "a", start: 540, end: 600 }]);
  });
  it("keeps the stop at least one step long and never moves a booked stop", () => {
    expect(moveEnd(DAY, LEGS, 0, 0, { step: 5 }).end).toBe(545);
    const booked = [stop("a", 540, 630, true), stop("b", 660, 720), stop("c", 750, 810)];
    expect(moveEnd(booked, LEGS, 0, 700, { step: 5 })).toMatchObject({ end: 630, changes: [] });
  });
  it("does not push when pushing is off: the end stays inside the free time", () => {
    expect(moveEnd(DAY, LEGS, 0, 700, { push: false, step: 1 }).end).toBe(651);
  });
  it("gives a stop with no end the length the maths assumes", () => {
    const open = [stop("a", 540, null), stop("b", 660, 720)];
    expect(moveEnd(open, [leg("a", "b", 9)], 0, 630, { step: 1 }).changes).toEqual([{ id: "a", start: 540, end: 630 }]);
  });
});

describe("minimap: the whole day while a time is dragged", () => {
  it("shows every stop where it was and where it would be, the stops it pushes, and what is left of the free time", () => {
    const moved = moveStop(DAY, LEGS, 0, 585, { step: 1 });
    const map = minimap(DAY, LEGS, moved.changes, "a");
    expect(map.blocks.map((block) => [block.id, block.shift, block.active])).toEqual([["a", 45, true], ["b", 24, false], ["c", 10, false]]);
    expect(map.pushed).toBe(2);
    expect(map.largestPush).toBe(24);
    expect(map.dayEnd).toEqual({ before: 810, after: 820 });
    expect(map.slackAfter).toBe(0);                                                             // b was pushed to exactly where it is reached: nothing free is left
    expect(map.from % 30).toBe(0);
    expect(map.to % 30).toBe(0);
    expect(map.from).toBeLessThan(540);
    expect(map.to).toBeGreaterThan(820);
  });
  it("says nothing moves when only free time is used", () => {
    const moved = moveStop(DAY, LEGS, 0, 555, { step: 1 });
    const map = minimap(DAY, LEGS, moved.changes, "a");
    expect(map.pushed).toBe(0);
    expect(map.largestPush).toBe(0);
    expect(map.slackAfter).toBe(6);                                                             // 21 minutes of free time, 15 used
  });
  it("counts a stop whose end alone changed for the time of leaving", () => {
    const moved = moveEnd(DAY, LEGS, 0, 645, { step: 1 });
    const map = minimap(DAY, LEGS, moved.changes, "a");
    expect(map.blocks[0]).toMatchObject({ id: "a", shift: 0, active: true, after: { start: 540, end: 645 } });
    expect(map.slackAfter).toBe(6);
  });
});
