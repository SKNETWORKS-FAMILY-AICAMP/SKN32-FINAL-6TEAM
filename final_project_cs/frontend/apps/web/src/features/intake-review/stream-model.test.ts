import { describe, expect, it } from "vitest";
import { emptyStream, reduceStream, toIntakeEvent, type IntakeStreamEvent, type StreamState } from "@/lib/live/intake-events";
import { compareItems, streamedReview } from "./stream-model";

const ev = (name: string, body: object): IntakeStreamEvent => toIntakeEvent(name, JSON.stringify(body)) as IntakeStreamEvent;
const item = (id: string, patch: object = {}) => ev("item", { id, source_id: "s1", index: Number(id.split("-")[1]), title: id, day: 1, date: "2026-10-01", starts_at: "10:00", place_state: "found", status: "keep", ...patch });
const check = (itemId: string, row: string, result = "ok") => ev("check", { item: itemId, row, result, text: `${itemId} ${row}` });
const move = (from: string, to: string) => ev("move", { from, to, status: "keep", summary: "도보", rows: [] });
const play = (...events: IntakeStreamEvent[]): StreamState => events.reduce(reduceStream, emptyStream());
const DONE = ev("done", { revision: 1, needs: { items: 0, moves: 0 }, ready: true });

describe("the check screen while the server is still checking", () => {
  it("lists the stops in the finished screen's order, whatever order they came in", () => {
    const result = streamedReview(play(item("0-2", { starts_at: "13:00" }), item("0-0", { starts_at: "09:00" }), item("0-1", { starts_at: "11:00" }), item("0-3", { day: 2, date: "2026-10-02", starts_at: "08:00" })));
    expect(result.items.map((entry) => entry.id)).toEqual(["0-0", "0-1", "0-2", "0-3"]);
  });

  it("sorts a stop with no time or day after the ones that have them, and equal times by the server's numbering", () => {
    expect(compareItems(item2("a", { starts_at: null }), item2("b", { starts_at: "10:00" }))).toBeGreaterThan(0);
    expect(compareItems(item2("0-2", {}), item2("0-10", {}))).toBeLessThan(0);
    expect(compareItems(item2("a", { day: null, date: null }), item2("b", { day: 1 }))).toBeGreaterThan(0);
  });

  it("gives each stop the check lines that came for it, in the order they came", () => {
    const result = streamedReview(play(item("0-0"), item("0-1"), check("0-0", "place"), check("0-0", "hours", "warn"), check("0-1", "place")));
    expect(result.items[0].rows?.map((row) => [row.row, row.result])).toEqual([["place", "ok"], ["hours", "warn"]]);
    expect(result.items[1].rows?.map((row) => row.row)).toEqual(["place"]);
  });

  it("keeps a stop 'checking' until the server moves on to the next one", () => {
    const first = streamedReview(play(item("0-0"), item("0-1"), check("0-0", "place")));
    expect([...first.checking].sort()).toEqual(["0-0", "0-1"]);        // 0-0 may still get more lines; 0-1 has none yet
    const second = streamedReview(play(item("0-0"), item("0-1"), check("0-0", "place"), check("0-1", "place")));
    expect([...second.checking]).toEqual(["0-1"]);                      // the server went on to 0-1, so 0-0 is complete
  });

  it("counts a stop complete once a leg has come after its lines, and every stop once the check is done", () => {
    const withMove = streamedReview(play(item("0-0"), item("0-1"), check("0-0", "place"), check("0-1", "place"), move("0-0", "0-1")));
    expect(withMove.checking.size).toBe(0);
    const done = streamedReview(play(item("0-0"), check("0-0", "place"), DONE));
    expect(done.checking.size).toBe(0);
  });

  it("keeps a stop that is still being looked up as checking even after the others are done", () => {
    const result = streamedReview(play(item("0-0"), item("0-1", { status: null, place_state: "searching" }), check("0-0", "place"), move("0-0", "0-1")));
    expect(result.checking.has("0-1")).toBe(true);
  });

  it("measures the progress line by stops checked plus legs shown, out of the stops plus the legs the days allow", () => {
    const early = streamedReview(play(item("0-0"), item("0-1"), item("0-2")));
    expect(early.progress).toEqual({ checked: 0, total: 5 });           // 3 stops + 2 legs the day allows
    const mid = streamedReview(play(item("0-0"), item("0-1"), item("0-2"), check("0-0", "place"), check("0-1", "place")));
    expect(mid.progress).toEqual({ checked: 1, total: 5 });
    const finished = streamedReview(play(item("0-0"), item("0-1"), item("0-2"), DONE));
    expect(finished.progress).toEqual({ checked: 5, total: 5 });
  });

  it("does not count a leg across two days as one the days allow", () => {
    const result = streamedReview(play(item("0-0"), item("0-1", { day: 2, date: "2026-10-02" })));
    expect(result.progress.total).toBe(2);
  });

  it("is empty before anything came in", () => {
    expect(streamedReview(emptyStream())).toMatchObject({ items: [], moves: [], progress: { checked: 0, total: 0 } });
  });
});

function item2(id: string, patch: object) {
  return (item(id, patch) as Extract<IntakeStreamEvent, { type: "item" }>).item;
}
