import { describe, expect, it } from "vitest";
import { dampStep, settled } from "./damped-scroll";

/** Run the spring for `seconds` at 60 frames a second. */
function run(from: number, target: number, seconds: number, omega = 6) {
  let state = { position: from, speed: 0 };
  const path = [from];
  for (let step = 0; step < Math.round(seconds * 60); step += 1) { state = dampStep(state.position, state.speed, target, omega, 1 / 60); path.push(state.position); }
  return { ...state, path };
}

describe("a damped scroll", () => {
  it("never overshoots the target (critically damped) and settles within about a second and a half", () => {
    const { path, position, speed } = run(0, 400, 1.8);
    expect(Math.max(...path)).toBeLessThanOrEqual(400.5);
    expect(settled(position, speed, 400)).toBe(true);
  });

  it("starts softly: the first frame moves much less than the fastest frame of the run", () => {
    const { path } = run(0, 400, 1);
    const steps = path.slice(1).map((value, at) => value - path[at]);
    expect(steps[0]).toBeGreaterThan(0);
    expect(Math.max(...steps)).toBeGreaterThan(steps[0] * 3);
  });

  it("keeps going from where it is when the target moves (no restart): the speed carries over", () => {
    let state = { position: 0, speed: 0 };
    for (let i = 0; i < 20; i += 1) state = dampStep(state.position, state.speed, 300, 6, 1 / 60);
    const before = state.speed;
    const after = dampStep(state.position, state.speed, 450, 6, 1 / 60);       // the target moved down: it does not stop and start over
    expect(before).toBeGreaterThan(0);
    expect(after.speed).toBeGreaterThan(before * 0.9);
  });

  it("works upward too", () => {
    const { path, position, speed } = run(500, 0, 1.8);
    expect(Math.min(...path)).toBeGreaterThanOrEqual(-0.5);
    expect(settled(position, speed, 0)).toBe(true);
  });
});
