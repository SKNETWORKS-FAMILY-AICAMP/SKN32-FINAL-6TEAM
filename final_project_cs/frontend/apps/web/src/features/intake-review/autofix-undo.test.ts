import { describe, expect, it } from "vitest";
import type { AutofixChange } from "@/lib/live/intake-review";
import { autofixUndo } from "./autofix-undo";

const place = (name: string) => ({ name, latitude: 37.57, longitude: 126.98, source: "kakao" });
const change = (patch: Partial<AutofixChange>): AutofixChange => ({
  id: "0-1", source_id: "s1", index: 1, title: "올리브영", reason: "place_and_time",
  from: { place: place("올리브영 인사동점"), starts_at: "11:00", ends_at: "12:00" },
  to: { place: place("올리브영 광화문점"), starts_at: "11:45", ends_at: "12:15" }, ...patch,
});

describe("putting back what 「전체 자동 추천」 changed", () => {
  it("sends the old place with its coordinates and the old times", () => {
    expect(autofixUndo([change({})])).toEqual([
      { source_id: "s1", field: "items[1].place", value: { name: "올리브영 인사동점", latitude: 37.57, longitude: 126.98, source: "kakao" } },
      { source_id: "s1", field: "items[1].starts_at", value: "11:00" },
      { source_id: "s1", field: "items[1].ends_at", value: "12:00" },
    ]);
  });

  it("puts back only what the change touched — a time change leaves the place alone", () => {
    const only = autofixUndo([change({ reason: "time", to: { place: place("올리브영 인사동점"), starts_at: "11:30", ends_at: "12:00" } })]);
    expect(only).toEqual([{ source_id: "s1", field: "items[1].starts_at", value: "11:00" }]);
  });

  it("offers no undo when the stop had no place before — it cannot be taken back, and half of it must not be said to be", () => {
    expect(autofixUndo([change({ from: { place: null, starts_at: "11:00", ends_at: "12:00" } })])).toBeNull();
  });

  it("offers no undo when one of several changes cannot be put back — all or nothing", () => {
    expect(autofixUndo([change({}), change({ id: "0-2", index: 2, from: { place: null, starts_at: "13:00", ends_at: "14:00" } })])).toBeNull();
  });

  it("offers no undo when a time that changed was not known before", () => {
    expect(autofixUndo([change({ reason: "time", from: { place: place("a"), starts_at: null, ends_at: "12:00" }, to: { place: place("a"), starts_at: "11:30", ends_at: "12:00" } })])).toBeNull();
  });

  it("offers no undo when nothing changed", () => {
    expect(autofixUndo([])).toBeNull();
  });
});
