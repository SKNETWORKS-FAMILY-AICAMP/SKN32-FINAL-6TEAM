import { describe, expect, it } from "vitest";
import { retimeEdits } from "./retime-edits";

const stop = { source_id: "s1", index: 2, starts_at: "09:00" as string | null, ends_at: "11:00" as string | null };

describe("the edits that retime a stop", () => {
  it("sends both times when both change, pointed at the stop by its source and position", () => {
    expect(retimeEdits(stop, { start: "10:00", end: "12:00" })).toEqual([
      { source_id: "s1", field: "items[2].starts_at", value: "10:00" },
      { source_id: "s1", field: "items[2].ends_at", value: "12:00" },
    ]);
  });

  it("sends only the time that changes — a stop whose times stay is nothing to send", () => {
    expect(retimeEdits(stop, { start: "09:00", end: "12:00" })).toEqual([{ source_id: "s1", field: "items[2].ends_at", value: "12:00" }]);
    expect(retimeEdits(stop, { start: "10:00", end: "11:00" })).toEqual([{ source_id: "s1", field: "items[2].starts_at", value: "10:00" }]);
    expect(retimeEdits(stop, { start: "09:00", end: "11:00" })).toEqual([]);
  });

  it("clears the end time with an empty string, the way the stop editor does", () => {
    expect(retimeEdits(stop, { start: "09:00", end: "" })).toEqual([{ source_id: "s1", field: "items[2].ends_at", value: "" }]);
  });

  it("treats a stop with no end as '' — no end stays no end, a new end is set", () => {
    const open = { ...stop, ends_at: null };
    expect(retimeEdits(open, { start: "09:00", end: "" })).toEqual([]);
    expect(retimeEdits(open, { start: "09:00", end: "10:00" })).toEqual([{ source_id: "s1", field: "items[2].ends_at", value: "10:00" }]);
  });

  it("never takes the start away: an empty start leaves it alone", () => {
    expect(retimeEdits(stop, { start: "", end: "12:00" })).toEqual([{ source_id: "s1", field: "items[2].ends_at", value: "12:00" }]);
    expect(retimeEdits({ ...stop, starts_at: null }, { start: "09:30", end: "11:00" })).toEqual([{ source_id: "s1", field: "items[2].starts_at", value: "09:30" }]);
  });
});
