import { describe, expect, it } from "vitest";
import type { IntakeField, IntakeView } from "@/lib/live/intake";
import { draftOf, editsFor, placeOf, rows, statusOf, type ReviewRow } from "./model";

const field = (value: unknown, extra: Partial<IntakeField> = {}): IntakeField => ({ value, method: "rule", needs_review: false, evidence: {}, note: null, ...extra });
function row(key = "s1:0"): ReviewRow {
  return { key, source: { source_id: key.split(":")[0], kind: "text", filename: null, transcribed: false, lines: [], items: [], trip: {}, reading: null },
    item: { index: Number(key.split(":")[1]), line: 1, day: 1, date: "2026-10-12", fields: { title: field("경복궁"), starts_at: field("09:00"), ends_at: field("10:00"), place: field({ name: "경복궁", latitude: 37.5796, longitude: 126.977 }) } }, problems: [] };
}

describe("intake review data and edit boundaries", () => {
  it("sends only edited fields with their original source and item index", () => {
    const r = row("s2:10");
    expect(editsFor(r, { ...draftOf(r), start: "10:30", end: "11:30", place: " 광장시장 " })).toEqual([
      { source_id: "s2", field: "items[10].starts_at", value: "10:30" },
      { source_id: "s2", field: "items[10].ends_at", value: "11:30" },
      { source_id: "s2", field: "items[10].place", value: { name: "광장시장" } },
    ]);
    expect(editsFor(r, draftOf(r))).toEqual([]);
  });
  it("distinguishes a customer-selected no-place from an unresolved place", () => {
    const r = row();
    r.item.fields.place = field(null);
    expect(draftOf(r).noPlace).toBe(false);
    expect(editsFor(r, { ...draftOf(r), noPlace: true })[0].value).toEqual({ none: true });
    r.item.fields.place.method = "customer";
    expect(draftOf(r).noPlace).toBe(true);
    expect(editsFor(r, { ...draftOf(r), noPlace: false, place: "경복궁" })[0].value).toEqual({ name: "경복궁" });
  });
  it("does not treat customer edits as a passed server check", () => {
    const r = row(); r.item.fields.starts_at!.method = "customer";
    expect(statusOf(r)).toBe("edited");
    r.problems = [{ code: "place_missing", field: "items[0].place", source_id: "s1", message: "장소 확인" }];
    expect(statusOf(r)).toBe("review");
  });
  it("keeps explicit review flags while suppressing the separate year assumption notice", () => {
    const r = row();
    r.item.fields.date = field("2026-10-12", { needs_review: true, evidence: { how: "year_filled" } });
    expect(statusOf(r)).toBe("ready");
    r.item.fields.title = field("경복궁", { needs_review: true, method: "llm_span" });
    expect(statusOf(r)).toBe("review");
  });
  it("never invents or coerces coordinates", () => {
    const r = row(), missing = row("s1:1");
    expect(placeOf(r)?.coordinates).toEqual({ lat: 37.5796, lng: 126.977 });
    missing.item.fields.place = field({ name: "영업점", latitude: null, longitude: "127" });
    expect(placeOf(missing)).toEqual({ name: "영업점" });
    missing.item.fields.place = field({ name: "영업점", latitude: 100, longitude: 127 });
    expect(placeOf(missing)?.coordinates).toBeUndefined();
  });
  it("groups in chronological order, excludes removals, and scopes problems by source/index", () => {
    const a = row(), b = row("s2:10"), removed = row("s1:1");
    b.item.date = "2026-10-11"; removed.item.fields.removed = field(true, { method: "customer" });
    const problem = { source_id: "s2", field: "items[10].place", code: "place_missing", message: "미확인" };
    const view = { sources: [{ ...a.source, items: [a.item, removed.item] }, { ...b.source, items: [b.item] }],
      check: { problems: [problem], filled: [{ source_id: "s2", field: "items[10].ends_at", value: "12:00" }] } } as IntakeView;
    const result = rows(view);
    expect(result.map((r) => r.key)).toEqual(["s2:10", "s1:0"]);
    expect(result[0].problems).toEqual([problem]); expect(result[1].problems).toEqual([]);
    expect(result[0].filledEnd).toBe("12:00");
  });
});

describe("opening hours the customer tells (2026-10-13)", () => {
  const box = { open: "10:00", close: "19:00", closedDays: ["sun" as const] };
  it("sends the hours in the server's shape, midnight as 24:00, and nothing when they did not change", () => {
    const r = row();
    expect(editsFor(r, { ...draftOf(r), hours: box })).toEqual([{ source_id: "s1", field: "items[0].hours", value: { open: "10:00", close: "19:00", closed_days: ["sun"] } }]);
    expect(editsFor(r, { ...draftOf(r), hours: { ...box, close: "00:00" } })[0].value).toEqual({ open: "10:00", close: "24:00", closed_days: ["sun"] });
    r.item.fields.hours = field({ open: "10:00", close: "19:00", closed_days: ["sun"] }, { method: "customer" });
    expect(editsFor(r, { ...draftOf(r), hours: box })).toEqual([]);
  });
  it("clears told hours with both times empty, and does not send hours with a place change (the server clears them)", () => {
    const r = row();
    r.item.fields.hours = field({ open: "10:00", close: "19:00", closed_days: [] }, { method: "customer" });
    expect(editsFor(r, { ...draftOf(r), hours: { open: "", close: "", closedDays: [] } })).toEqual([{ source_id: "s1", field: "items[0].hours", value: null }]);
    expect(editsFor(r, { ...draftOf(r), place: "광장시장", hours: box }).map((edit) => edit.field)).toEqual(["items[0].place"]);
    expect(editsFor(row(), { ...draftOf(row()), hours: { open: "", close: "", closedDays: [] } })).toEqual([]);
  });
});
