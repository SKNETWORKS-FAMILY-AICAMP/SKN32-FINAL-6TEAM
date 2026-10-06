import { describe, expect, it } from "vitest";
import { beginWait, CALL_STEPS, TASK_STEPS, waitLevel, worstWait } from "./waiting";

describe("when the server is told to be slow", () => {
  it("says nothing before the first step, then gets stronger at each step (a plain call: 8 s · 30 s · 60 s)", () => {
    expect(CALL_STEPS).toEqual([8_000, 30_000, 60_000]);
    expect([0, 7_999].map((ms) => waitLevel(ms, CALL_STEPS))).toEqual([0, 0]);
    expect([8_000, 29_999].map((ms) => waitLevel(ms, CALL_STEPS))).toEqual([1, 1]);
    expect([30_000, 59_999].map((ms) => waitLevel(ms, CALL_STEPS))).toEqual([2, 2]);
    expect([60_000, 600_000].map((ms) => waitLevel(ms, CALL_STEPS))).toEqual([3, 3]);
  });

  it("is slower to speak for a streamed task, which shows its own progress (30 s · 60 s · 120 s)", () => {
    expect(waitLevel(29_000, TASK_STEPS)).toBe(0);
    expect(waitLevel(30_000, TASK_STEPS)).toBe(1);
    expect(waitLevel(119_000, TASK_STEPS)).toBe(2);
    expect(waitLevel(120_000, TASK_STEPS)).toBe(3);
  });
});

describe("the call that has waited longest", () => {
  const entry = (id: number, since: number, steps = CALL_STEPS) => ({ id, since, steps });

  it("is none when no call has reached its first step", () => {
    expect(worstWait(5_000, [entry(1, 0)])).toBeNull();
    expect(worstWait(5_000, [])).toBeNull();
  });

  it("is the one with the highest level, then the longest wait; the seconds are whole seconds", () => {
    const now = 70_500;
    expect(worstWait(now, [entry(1, 60_000), entry(2, 5_000), entry(3, 40_000)])).toEqual({ id: 2, level: 3, seconds: 65 });
    // a task at 35 s is level 1; a plain call at 10 s is level 1 too - the longer wait is told
    expect(worstWait(35_000, [entry(1, 25_000), entry(2, 0, TASK_STEPS)])).toEqual({ id: 2, level: 1, seconds: 35 });
  });
});

describe("the calls that are counted", () => {
  it("joins when it starts, starts over on a sign of life, and leaves when it ends", () => {
    let clock = 1_000;
    const now = () => clock;
    const first = beginWait(CALL_STEPS, now);
    clock = 12_000;
    expect(worstWait(clock)).toMatchObject({ level: 1, seconds: 11 });
    first.touch();                                                   // a new stage arrived: the count starts over
    expect(worstWait(clock)).toBeNull();
    clock = 45_000;
    expect(worstWait(clock)).toMatchObject({ level: 2, seconds: 33 });
    first.end();
    expect(worstWait(clock)).toBeNull();
    first.end();                                                     // ending twice is harmless
  });
});
