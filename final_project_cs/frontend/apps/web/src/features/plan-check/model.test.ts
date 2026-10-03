import { describe, expect, it } from "vitest";
import { exampleDone, exampleSnapshots } from "./test-views";
import { nextStep, progress, tally, timeline, type PlanCheckView } from "./model";

/** Every snapshot `nextStep` draws on the way from `from` to `to`, `to` included. */
function walk(from: PlanCheckView, to: PlanCheckView): PlanCheckView[] {
  const out: PlanCheckView[] = [];
  let shown = from;
  for (let guard = 0; guard < 500; guard += 1) {
    const next = nextStep(shown, to);
    if (!next) return out;
    out.push(next);
    shown = next;
  }
  throw new Error("nextStep did not reach the target");
}

const received = exampleSnapshots[0].view;

describe("plan check — what the screen draws, one change at a time", () => {
  it("lays a day out as lived: place, the move to the next place, place …", () => {
    expect(timeline(exampleDone, 1).map((entry) => entry.type === "item" ? entry.item.id : entry.move.id)).toEqual(["a", "a-b", "b", "b-c", "c"]);
    expect(timeline(exampleDone, 2).map((entry) => entry.type === "item" ? entry.item.id : entry.move.id)).toEqual(["d"]);
  });

  it("goes from received to done in order: reading, each line, the days, checking, each place or move with its checks, done, title", () => {
    const steps = walk(received, exampleDone);
    expect(steps.at(-1)).toEqual(exampleDone);
    // 1 reading + 5 lines + 1 days + 1 checking + places (a 1+3+1, b 1+4+1, c 1+4+1, d 1+3+1) + moves (2 × (1+3+1)) + done + title
    expect(steps).toHaveLength(1 + 5 + 1 + 1 + 22 + 10 + 1 + 1);
    expect(steps[0].stage).toBe("reading");
    expect(steps[0].lines.every((line) => !line.read)).toBe(true);           // reading starts before the first line is read
    expect(steps.slice(1, 6).map((view) => view.lines.filter((line) => line.read).length)).toEqual([1, 2, 3, 4, 5]);
    expect(steps[6]).toMatchObject({ stage: "reading", days: exampleDone.days });
    expect(steps[7].stage).toBe("checking");
    // A place appears with every check waiting, then each check comes in, then its verdict.
    const firstPlace = steps.find((view) => view.items.length === 1)!;
    expect(firstPlace.items[0]).toMatchObject({ id: "a", verdict: null });
    expect(firstPlace.items[0].checks.every((row) => row.result === "pending")).toBe(true);
    const order = steps.flatMap((view, index) => {
      const before = index ? steps[index - 1] : received;
      return [...view.items.filter((item) => !before.items.some((other) => other.id === item.id)).map((item) => item.id),
        ...view.moves.filter((move) => !before.moves.some((other) => other.id === move.id)).map((move) => move.id)];
    });
    expect(order).toEqual(["a", "a-b", "b", "b-c", "c", "d"]);
    // Done comes only after every check, and the title last.
    const doneAt = steps.findIndex((view) => view.stage === "done");
    expect(steps[doneAt].items.every((item) => item.verdict !== null)).toBe(true);
    expect(steps[doneAt].title).toBeNull();
    expect(steps.at(-1)!.title).toBe("10월 서울 여행");
  });

  it("draws the same changes whether the server sends them in one burst or in several snapshots", () => {
    const burst = walk(received, exampleDone).map((view) => JSON.stringify(view));
    let shown = received;
    const stepped: string[] = [];
    for (const { view } of exampleSnapshots.slice(1)) {
      const part = walk(shown, view);
      stepped.push(...part.map((step) => JSON.stringify(step)));
      shown = part.at(-1) ?? shown;
    }
    expect(stepped).toEqual(burst);
  });

  it("does not replay what it cannot step toward — a place gone, or an earlier stage — it jumps to the target", () => {
    const fewer = { ...exampleDone, items: exampleDone.items.filter((item) => item.id !== "d") };
    expect(nextStep(exampleDone, fewer)).toBe(fewer);
    expect(nextStep(exampleDone, received)).toBe(received);
    expect(nextStep(exampleDone, exampleDone)).toBeNull();
  });

  it("moves the bar with the lines read, then with the places and moves checked", () => {
    const steps = walk(received, exampleDone);
    expect(progress(received)).toBe(0);
    const twoLines = steps.find((view) => view.lines.filter((line) => line.read).length === 2 && view.stage === "reading")!;
    expect(progress(twoLines)).toBeCloseTo(100 / 3 * 2 / 5);
    const halfChecked = steps.find((view) => view.stage === "checking" && [...view.items, ...view.moves].filter((entity) => entity.verdict !== null).length === 3)!;
    expect(progress(halfChecked)).toBeCloseTo(100 / 3 + 100 / 3 * 3 / 6);
    expect(progress(exampleDone)).toBe(100);
    const values = steps.map(progress);
    expect(values).toEqual([...values].sort((a, b) => a - b));                 // never goes back
  });

  it("counts places and moves done and those to check", () => {
    expect(tally(exampleDone)).toEqual({ places: 4, placesDone: 4, moves: 2, movesDone: 2, placesReview: 1, movesReview: 1 });
    // Mid-check the totals are already known from the lines read: 4 places, and 2 moves (3 stops on day 1, 1 on day 2).
    const checking = walk(received, exampleDone).find((view) => view.items.length === 2)!;
    expect(tally(checking)).toMatchObject({ places: 4, placesDone: 1, moves: 2, movesDone: 1 });
  });
});
