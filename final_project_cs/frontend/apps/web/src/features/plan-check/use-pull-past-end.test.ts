import { describe, expect, it } from "vitest";
import { edgeFor, PULL_TO_OPEN, pullStep } from "./use-pull-past-end";

describe("pushing past an end of the list", () => {
  it("grows while the push keeps going the same way at the same end", () => {
    let pull = 0;
    for (const delta of [30, 40, 25]) pull = pullStep(pull, delta, "end");
    expect(pull).toBe(95);
    expect(pullStep(pull, 30, "end")).toBeGreaterThanOrEqual(PULL_TO_OPEN);
  });

  it("counts pushes up at the top as growing too, and lets go of anything else", () => {
    expect(pullStep(40, -30, "start")).toBe(70);
    expect(pullStep(70, 30, "start")).toBe(0);      // turned round
    expect(pullStep(70, 30, null)).toBe(0);         // not at an end
    expect(pullStep(70, -30, "end")).toBe(0);       // pulling back from the end
  });

  it("never grows past one and a half times what opens the next page", () => {
    expect(pullStep(PULL_TO_OPEN * 1.4, 500, "end")).toBe(PULL_TO_OPEN * 1.5);
  });
});

describe("which end of the list a push is against", () => {
  const list = (scrollTop: number, scrollHeight = 900, clientHeight = 300) => ({ scrollTop, scrollHeight, clientHeight });

  it("is the end at the bottom, the start at the top, none in the middle", () => {
    expect(edgeFor(list(600), 10)).toBe("end");
    expect(edgeFor(list(0), -10)).toBe("start");
    expect(edgeFor(list(200), 10)).toBeNull();
  });

  it("takes the direction of the push when the list has nothing to scroll (both ends at once)", () => {
    expect(edgeFor(list(0, 280, 300), -20)).toBe("start");
    expect(edgeFor(list(0, 280, 300), 20)).toBe("end");
    expect(edgeFor(list(0, 280, 300), 0)).toBe("end");
  });
});

