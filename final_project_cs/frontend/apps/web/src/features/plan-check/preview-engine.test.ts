import { describe, expect, it } from "vitest";
import { needs } from "./model";
import { applyPlace, candidatesFor, exampleState, recheckOrder, recommendAll, removeStop, searchPlaces, setLocked, waitingFor } from "./preview-engine";

const item = (state: ReturnType<typeof exampleState>, id: string) => state.view.items.find((entry) => entry.id === id)!;

describe("the preview's stand-in for the server (mockup rules, example data only)", () => {
  it("offers three places of the same kind, nearest to the stops around it, and names the first on the card", () => {
    const state = exampleState();
    const olive = candidatesFor(state, "b");
    expect(olive.map((candidate) => candidate.name)).toEqual(["올리브영 광화문점", "올리브영 인사동점", "올리브영 종각역점"]);
    expect(olive[0]).toMatchObject({ source: "candidate", rank: 1, distance: { from: "경복궁" } });
    expect(olive[0].distance!.km).toBeCloseTo(0.9, 1);
    expect(olive[0].info?.photos).toHaveLength(6);
    expect(item(state, "b").suggestion).toBe("올리브영 광화문점");
    // No neighbour with a place: measured from where it is now.
    expect(candidatesFor(state, "d")[0]).toMatchObject({ name: "낙산공원", distance: { from: "지금 장소" } });
  });

  it("searches example places by name or kind, nearest first", () => {
    const state = exampleState();
    expect(searchPlaces(state, "b", "올리브영").map((candidate) => candidate.name)[0]).toBe("올리브영 광화문점");
    expect(searchPlaces(state, "b", "전망대").every((candidate) => candidate.info?.category?.includes("전망대"))).toBe(true);
    expect(searchPlaces(state, "b", "  ")).toEqual([]);
  });

  it("changing a place checks it at the stop's time, works out the moves either side again and marks the plan changed", () => {
    const after = applyPlace(exampleState(), "b", "oyGwanghwamun", "pick");
    const olive = item(after, "b");
    expect(olive).toMatchObject({ title: "올리브영 광화문점", place: "올리브영 광화문점", verdict: "adjusted" });
    expect(olive.coordinates).not.toBeNull();
    expect(olive.checks.map((check) => [check.kind, check.result])).toEqual([["place", "ok"], ["time", "warn"], ["hours", "ok"], ["closed", "unknown"]]);
    expect(olive.checks[0].text).toBe("대체 후보에서 고른 곳 · 카카오 정보로 찾았어요");
    expect(after.view.dirty).toBe(true);
    const into = after.view.moves.find((move) => move.id === "a-b")!;
    expect(into.mode).toBe("도보");
    expect(into.summary).toMatch(/분 · 0\.\dkm$/);
    expect(needs(after.view).places).toBe(0);
  });

  it("a place shut on the visiting day needs a look", () => {
    // 2026-10-01 is a Thursday; 창덕궁 is shut on Mondays — open. Make the day a Monday instead.
    const monday = { ...exampleState(), view: { ...exampleState().view, items: exampleState().view.items.map((entry) => entry.id === "a" ? { ...entry, date: "2026-10-05" } : entry) } };
    const after = applyPlace(monday, "a", "changdeokgung", "pick");
    expect(item(after, "a").checks.find((check) => check.kind === "closed")).toMatchObject({ result: "bad", text: "월요일 휴무 · 방문일이 휴무예요" });
    expect(item(after, "a").verdict).toBe("review");
  });

  it("「전체 자동 추천」 changes what needs a look to an alternative that fits, keeps locked stops, and says what changed", () => {
    const outcome = recommendAll(exampleState());
    expect(outcome.changes).toHaveLength(1);
    expect(outcome.changes[0]).toMatch(/^올리브영 → 올리브영 \S+ \d\d:\d\d–\d\d:\d\d$/);
    expect(needs(outcome.state.view).total).toBe(0);
    expect(outcome.state.view.dirty).toBe(true);

    const locked = recommendAll(setLocked(exampleState(), "b", true));
    expect(locked.changes).toEqual([]);
    expect(locked.kept).toBeGreaterThan(0);
  });

  it("deleting a stop joins the stops either side with a new move", () => {
    const after = removeStop(exampleState(), "b");
    expect(after.view.items.map((entry) => entry.id)).toEqual(["a", "c", "d"]);
    expect(after.view.moves.map((move) => move.id)).toEqual(["a-c"]);
    expect(after.view.dirty).toBe(true);
  });

  it("a stop checked again waits — its checks and the moves either side — and a full re-check goes stop by stop", () => {
    const waiting = waitingFor(exampleState().view, ["b"]);
    expect(waiting.items.find((entry) => entry.id === "b")).toMatchObject({ verdict: null });
    expect(waiting.items.find((entry) => entry.id === "b")!.checks.every((check) => check.result === "pending")).toBe(true);
    expect(waiting.moves.every((move) => move.verdict === null)).toBe(true);
    expect(recheckOrder(exampleState().view)).toEqual(["a", "b", "c", "d"]);
  });
});
