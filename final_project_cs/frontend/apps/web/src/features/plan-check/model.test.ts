import { describe, expect, it } from "vitest";
import { exampleDone, exampleSnapshots } from "./test-views";
import { askStopId, beginRecheck, cutAtStop, nextStep, onlyCard, progress, rebase, stopAt, stopKind, tally, timeline, withArrivalRows, withAskSlot, type PlanAsk, type PlanCheckView } from "./model";

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
    // 1 reading + 5 lines + 1 days + 1 checking + done + title, and along the day (`[2026-10-20 C안]` a card appears, each of its lines is ticked in — the red and grey
    // ones too —, then its verdict; a move comes whole with the card it leads to): a 1+3+1 · b (with a-b) 1+4+1 · c (with b-c) 1+4+1 · d 1+3+1
    expect(steps).toHaveLength(1 + 5 + 1 + 1 + (5 + 6 + 6 + 5) + 1 + 1);
    expect(steps[0].stage).toBe("reading");
    expect(steps[0].lines.every((line) => !line.read)).toBe(true);           // reading starts before the first line is read
    expect(steps.slice(1, 6).map((view) => view.lines.filter((line) => line.read).length)).toEqual([1, 2, 3, 4, 5]);
    expect(steps[6]).toMatchObject({ stage: "reading", days: exampleDone.days });
    expect(steps[7].stage).toBe("checking");
    // A place appears with every check waiting, then each check comes in, then the verdict on its own.
    const firstPlace = steps.find((view) => view.items.length === 1)!;
    expect(firstPlace.items[0]).toMatchObject({ id: "a", verdict: null });
    expect(firstPlace.items[0].checks.every((row) => row.result === "pending")).toBe(true);
    const secondTick = steps[steps.indexOf(firstPlace) + 1];
    expect(secondTick.items[0].checks.map((row) => row.result)).toEqual(["ok", "pending", "pending"]);
    expect(secondTick.items[0].verdict).toBeNull();
    expect(steps[steps.indexOf(firstPlace) + 3].items[0].verdict).toBeNull();                 // every line in, the verdict not yet
    expect(steps[steps.indexOf(firstPlace) + 4].items[0].verdict).toBe("keep");               // the verdict, a step of its own
    const added = steps.map((view, index) => {
      const before = index ? steps[index - 1] : received;
      return [...view.moves.filter((move) => !before.moves.some((other) => other.id === move.id)).map((move) => move.id),
        ...view.items.filter((item) => !before.items.some((other) => other.id === item.id)).map((item) => item.id)];
    });
    expect(added.flat()).toEqual(["a", "a-b", "b", "b-c", "c", "d"]);
    // `[2026-10-20 C안]` The leg to a place comes in the same step as that place.
    expect(added.filter((ids) => ids.length > 1)).toEqual([["a-b", "b"], ["b-c", "c"]]);
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

  it("`[2026-10-20 C안]` ticks the red and grey lines in like the others — the card comes with every line waiting, so it does not grow while it is checked", () => {
    const steps = walk(received, exampleDone);
    const appear = steps.find((view) => view.items.some((item) => item.id === "b"))!;
    const rows = (view: PlanCheckView) => view.items.find((item) => item.id === "b")!.checks.map((row) => row.result);
    const at = steps.indexOf(appear);
    expect(rows(appear)).toEqual(["pending", "pending", "pending", "pending"]);
    expect(steps.slice(at + 1, at + 5).map(rows)).toEqual([
      ["bad", "pending", "pending", "pending"], ["bad", "warn", "pending", "pending"], ["bad", "warn", "unknown", "pending"], ["bad", "warn", "unknown", "unknown"]]);
    expect(steps[at + 4].items.find((item) => item.id === "b")!.verdict).toBeNull();
    expect(steps[at + 5].items.find((item) => item.id === "b")!.verdict).toBe("review");
  });

  it("`[2026-10-04]` draws a move whole — only its mark is on show, so no pretended search is replayed after the server has answered", () => {
    const steps = walk(received, exampleDone);
    const appear = steps.find((view) => view.moves.length === 1)!;
    expect(appear.moves[0]).toEqual(exampleDone.moves[0]);
  });

  it("`[2026-10-20 C안]` draws a leg the server sent after its place alone, where it stands", () => {
    const noLegs: PlanCheckView = { ...exampleDone, moves: [] };
    const drawn = walk(received, noLegs).at(-1)!;
    const steps = walk(drawn, exampleDone);
    expect(steps.map((view) => view.moves.length)).toEqual([1, 2]);
    expect(steps.every((view) => JSON.stringify(view.items) === JSON.stringify(exampleDone.items))).toBe(true);
  });
});

describe("`[2026-10-20 C안]` the first check stops at a card that needs a look", () => {
  const steps = walk(received, exampleDone);
  /** The first drawn state where card b's verdict 「확인 필요」 is in. */
  const atB = steps.find((view) => view.items.find((item) => item.id === "b")?.verdict === "review")!;

  it("stops at the first drawn card that needs a look, once the server's check is final", () => {
    expect(stopAt(atB, exampleDone)).toBe("b");
    expect(stopAt(atB, { ...exampleDone, stage: "checking" })).toBeNull();
    expect(stopAt(steps[steps.indexOf(atB) - 1], exampleDone)).toBeNull();      // b's checks are in, not its verdict yet
  });

  it("does not draw a 「확인 필요」 verdict before the check is final (the page stops there to ask)", () => {
    const streaming: PlanCheckView = { ...exampleDone, stage: "checking", title: null };
    const drawn = walk(steps.find((view) => view.stage === "checking")!, streaming);
    const b = drawn.at(-1)!.items.find((item) => item.id === "b")!;
    expect(b.checks.map((row) => row.result)).toEqual(["bad", "warn", "unknown", "unknown"]);
    expect(b.verdict).toBeNull();
    expect(drawn.at(-1)!.items.map((item) => item.id)).toEqual(["a", "b"]);
  });

  it("tells a step that changes only the stopped card from one that draws past it", () => {
    const next = nextStep(atB, exampleDone)!;
    expect(onlyCard(atB, next, "b")).toBe(false);                               // the leg to c and card c
    expect(onlyCard(atB, beginRecheck(atB, "b"), "b")).toBe(true);
  });

  it("checks the picked card again where it stands: its checks wait with their words kept, then take the new plan's", () => {
    const asked = beginRecheck(atB, "b");
    const b = asked.items.find((item) => item.id === "b")!;
    expect(b.checks.every((row) => row.result === "pending")).toBe(true);
    expect(b.checks.map((row) => row.text)).toEqual(exampleDone.items[1].checks.map((row) => row.text));
    expect(b.verdict).toBe("review");
    const fixed: PlanCheckView = { ...exampleDone, revision: 2, items: exampleDone.items.map((item) => item.id !== "b" ? item
      : { ...item, title: "올리브영 광화문점", place: "올리브영 광화문점", verdict: "keep", checks: [{ kind: "place", result: "ok", text: "고른 곳이에요" }, { kind: "time", result: "ok", text: "겹치지 않아요" }] }),
      moves: exampleDone.moves.map((move) => move.id === "a-b" ? { ...move, slackMin: 3, verdict: "keep" as const } : move) };
    const based = rebase(asked, fixed, "b");
    const nb = based.items.find((item) => item.id === "b")!;
    expect(nb).toMatchObject({ title: "올리브영 광화문점", verdict: "review" });
    expect(nb.checks).toEqual([{ kind: "place", result: "pending", text: "지점이 여러 곳이라 정하지 못했어요" }, { kind: "time", result: "pending", text: "경복궁 관람과 30분 겹쳐요 · 등록 때 막힐 수 있어요" }]);
    expect(based.items.map((item) => item.id)).toEqual(["a", "b"]);              // c and d are not drawn yet
    expect(based.moves.map((move) => move.id)).toEqual(["a-b"]);
    // Then each check is ticked in, the verdict last — and the check goes on past b.
    const more = walk(based, fixed);
    const passed = more.findIndex((view) => view.items.find((item) => item.id === "b")!.verdict === "keep");
    expect(more.slice(0, passed).map((view) => view.items.find((item) => item.id === "b")!.checks.map((row) => row.result))).toEqual([["ok", "pending"], ["ok", "ok"]]);
    expect(stopAt(more[passed], fixed)).toBeNull();
    expect(more.at(-1)).toEqual(fixed);
  });
});

describe("`[2026-10-20 C안 · 이동 확인 C안]` a late way in is asked in the stop's own card", () => {
  it("stops at a card whose way in arrives late — after its place, in the same card", () => {
    const late: PlanCheckView = { ...exampleDone, items: exampleDone.items.map((item) => item.id === "b" ? { ...item, verdict: "keep" as const } : item) };
    const steps = walk(received, late);
    const at = steps.find((view) => view.items.find((item) => item.id === "b")?.verdict === "keep")!;
    expect(stopAt(at, late)).toBe("b");
    expect(stopKind(at, "b")).toBe("arrival");
    expect(stopKind(steps.at(-1)!, "b")).toBe("arrival");
    expect(stopKind(exampleDone, "b")).toBe("place");                              // a place that needs a look is asked first
  });

  it("puts the 「도착」 line of the way in on each stop's card (none where there is no way in)", () => {
    const view = withArrivalRows(exampleDone);
    expect(view.items.find((item) => item.id === "b")!.checks.at(-1)).toEqual(exampleDone.moves[0].checks.find((row) => row.kind === "arrival"));
    expect(view.items.find((item) => item.id === "a")!.checks).toEqual(exampleDone.items[0].checks);
    expect(withArrivalRows({ ...exampleDone, moves: [] })).toEqual({ ...exampleDone, moves: [] });
  });

  it("opens a checked plan at the first stop: everything up to it drawn, nothing after", () => {
    const cut = cutAtStop(exampleDone);
    expect(cut.stage).toBe("checking");
    expect(cut.items.map((item) => item.id)).toEqual(["a", "b"]);
    expect(cut.moves.map((move) => move.id)).toEqual(["a-b"]);
    const calm: PlanCheckView = { ...exampleDone, items: exampleDone.items.map((item) => ({ ...item, verdict: "keep" as const })), moves: exampleDone.moves.map((move) => ({ ...move, slackMin: 5 })) };
    expect(cutAtStop(calm)).toBe(calm);
  });
});

describe("`[2026-10-21 사용자 결정 — P6]` the first check stops at a line of the plan read as something other than a stop", () => {
  /** Nothing to fix on the cards: only the question stops the check. */
  const calm: PlanCheckView = { ...exampleDone, items: exampleDone.items.map((item) => ({ ...item, verdict: "keep" as const })), moves: exampleDone.moves.map((move) => ({ ...move, slackMin: 5, verdict: "keep" as const })) };
  const ask = (startsAt: string): PlanAsk => ({ id: "q-0-5", itemId: "e", day: 1, date: "2026-10-01", startsAt, title: "정도", question: "계획서의 「14시~16시 정도」를 어떻게 이해할까요?", quote: "14시~16시 정도",
    options: [{ id: "reading", label: "14:00~16:00 빈 시간", recommended: true, reason: "읽기 AI 가 빈 시간으로 읽었어요", effect: "일정에 넣지 않고 14:00~16:00 빈 시간으로 둬요", pickMyself: false, query: null }] });
  const asked: PlanCheckView = { ...calm, asks: [ask("14:00")] };

  it("draws every stop before the question's time, then stops there — nothing past it, not done", () => {
    const steps = walk(received, asked);
    const last = steps.at(-1)!;
    expect(last.items.map((item) => item.id)).toEqual(["a", "b", "c"]);              // d (day 2) is past it
    expect(last.items.every((item) => item.verdict === "keep")).toBe(true);
    expect(last.stage).toBe("checking");
    expect(nextStep(last, asked)).toBeNull();
    expect(stopAt(last, asked)).toBe(askStopId("q-0-5"));
    expect(stopAt(steps[steps.length - 2], asked)).toBeNull();                       // c's verdict still to come
    expect(stopAt(last, { ...asked, stage: "checking" })).toBeNull();                 // the server's check is not final yet
  });

  it("stands after the stops that start by then and before the leg into the next one", () => {
    const early: PlanCheckView = { ...calm, asks: [ask("11:30")] };
    const cut = cutAtStop(early);
    expect(cut.items.map((item) => item.id)).toEqual(["a", "b"]);
    expect(cut.moves.map((move) => move.id)).toEqual(["a-b"]);                       // the leg b → c comes with c, after the question
    expect(withAskSlot(cut, ask("11:30")).items.map((item) => item.id)).toEqual(["a", "b", askStopId("q-0-5")]);
    expect(withAskSlot(calm, ask("11:30")).items.map((item) => item.id)).toEqual(["a", "b", askStopId("q-0-5"), "c", "d"]);
    expect(withAskSlot(calm, ask("11:30")).items[2]).toMatchObject({ startsAt: "11:30", title: "14시~16시 정도", coordinates: null, ask: { id: "q-0-5" } });
  });

  it("goes on once it is answered: the AI's reading draws the rest, a stop put back is drawn in its place and checked", () => {
    const last = walk(received, asked).at(-1)!;
    expect(walk(last, calm).at(-1)).toEqual(calm);                                    // answered with the reading: the question is gone, the check finishes
    const e = { ...calm.items[2], id: "e", startsAt: "14:00", endsAt: "16:00", title: "정돈 대학로본점", place: "정돈 대학로본점" };
    const back: PlanCheckView = { ...calm, revision: 2, items: [...calm.items.slice(0, 3), e, calm.items[3]],
      moves: [...calm.moves, { ...calm.moves[1], id: "c-e", fromId: "c", toId: "e", departAt: "13:30" }] };
    const steps = walk(last, back);
    expect(steps[0].items.map((item) => item.id)).toEqual(["a", "b", "c", "e"]);      // the leg c → e and card e in one step, its checks waiting
    expect(steps[0].moves.map((move) => move.id)).toContain("c-e");
    expect(steps[0].items[3].checks.every((row) => row.result === "pending")).toBe(true);
    expect(steps.at(-1)).toEqual(back);
  });
});
