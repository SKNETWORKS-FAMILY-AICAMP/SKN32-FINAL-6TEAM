import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import { emptyStream, reduceStream, type IntakeStreamEvent, type StreamState } from "@/lib/live/intake-events";
import { currentStep, foundCount, foundTag, progressPercent, readingLines, stepStates, STEPS } from "./reading-model";

const ko = translator("ko");
const en = translator("en");

const lines = [
  { no: 1, text: "10월 1일 서울 여행", read: false },
  { no: 2, text: "10시 경복궁 관람 1시간 반", read: false },
  { no: 3, text: "11시 올리브영", read: false },
];

function heard(...events: IntakeStreamEvent[]): StreamState { return events.reduce(reduceStream, emptyStream()); }
const lineEvent = (no: number, found: object | null = null): IntakeStreamEvent => ({
  type: "line", line: { source_id: "s1", no, text: lines[no - 1].text, found: found as never },
});

describe("which step the server is on", () => {
  it("maps the server's stages to the four steps, and everything after reading to all done", () => {
    expect(STEPS).toHaveLength(4);
    expect(currentStep("received", "reading")).toBe(0);
    expect(currentStep("transcribing", "reading")).toBe(0);
    expect(currentStep("reading", "reading")).toBe(1);
    expect(currentStep("checking", "reading")).toBe(2);
    expect(currentStep("review", "reading")).toBe(3);
    expect(currentStep("review", "review")).toBe(4);
    expect(currentStep("anything", "confirmed")).toBe(4);
  });

  it("counts a stage it does not know as reading — the line never jumps back or goes blank", () => {
    expect(currentStep("some_new_stage", "reading")).toBe(1);
  });

  it("marks steps before the current one done and after it waiting", () => {
    expect(stepStates(2)).toEqual(["done", "done", "cur", "todo"]);
    expect(stepStates(0)).toEqual(["cur", "todo", "todo", "todo"]);
    expect(stepStates(4)).toEqual(["done", "done", "done", "done"]);
  });
});

describe("how far the progress line is filled", () => {
  const base = { readLines: 0, totalLines: 0 };

  it("is empty when received and full at the end", () => {
    expect(progressPercent({ ...base, step: 0 })).toBe(0);
    expect(progressPercent({ ...base, step: 3 })).toBe(100);
    expect(progressPercent({ ...base, step: 4 })).toBe(100);
  });

  it("fills the first third by the share of lines read", () => {
    expect(progressPercent({ step: 1, readLines: 0, totalLines: 5 })).toBe(0);
    expect(progressPercent({ step: 1, readLines: 5, totalLines: 5 })).toBeCloseTo(33.333, 2);
    expect(progressPercent({ step: 1, readLines: 1, totalLines: 5 })).toBeCloseTo(6.667, 2);
  });

  it("does not make up a share when it does not know the total", () => {
    expect(progressPercent({ step: 1, readLines: 3, totalLines: 0 })).toBe(0);
    expect(progressPercent({ step: 2, readLines: 3, totalLines: 3, checked: 2, totalChecks: 0 })).toBeCloseTo(33.333, 2);
  });

  it("fills the second third by the share of places and legs checked, and never past the ends", () => {
    expect(progressPercent({ step: 2, readLines: 5, totalLines: 5, checked: 3, totalChecks: 6 })).toBeCloseTo(50, 2);
    expect(progressPercent({ step: 2, readLines: 5, totalLines: 5, checked: 9, totalChecks: 6 })).toBeCloseTo(66.667, 2);
    expect(progressPercent({ step: 1, readLines: 9, totalLines: 5 })).toBeCloseTo(33.333, 2);
  });
});

describe("the original, line by line", () => {
  const source = [{ source_id: "s1", lines }];

  it("shows the first line not read yet as the one being read, the rest waiting", () => {
    const result = readingLines(source, emptyStream(), true, ko);
    expect(result.map((line) => line.state)).toEqual(["cur", "todo", "todo"]);
  });

  it("shows nothing as being read when the server is not reading (before it started, or after it ended)", () => {
    expect(readingLines(source, emptyStream(), false, ko).map((line) => line.state)).toEqual(["todo", "todo", "todo"]);
  });

  it("turns a line to read when the stream says so, with what was found on it", () => {
    const stream = heard(lineEvent(1), lineEvent(2, { id: "0-0", index: 0, day: 1, date: "2026-10-01", starts_at: "10:00", title: "경복궁" }));
    const result = readingLines(source, stream, true, ko);
    expect(result.map((line) => line.state)).toEqual(["read", "read", "cur"]);
    expect(result[0].tag).toBeNull();                       // the date line gave no stop
    expect(result[1].tag).toBe("1일차 10:00 · 경복궁");
    expect(result[2].tag).toBeNull();
  });

  it("takes a line the GET already marked read, even without a stream event", () => {
    const result = readingLines([{ source_id: "s1", lines: lines.map((line) => ({ ...line, read: line.no === 1 })) }], emptyStream(), true, ko);
    expect(result.map((line) => line.state)).toEqual(["read", "cur", "todo"]);
  });

  it("keeps the lines of several uploads apart, each with its own numbers", () => {
    const result = readingLines([{ source_id: "s1", lines: [lines[0]] }, { source_id: "s2", lines: [lines[0]] }], heard(lineEvent(1)), true, ko);
    expect(result.map((line) => [line.key, line.state])).toEqual([["s1:1", "read"], ["s2:1", "cur"]]);
  });

  it("shows a line the stream read that the plan read does not list yet, in the order the server read it", () => {
    const stream = heard(lineEvent(2, { id: "0-0", index: 0, day: 1, date: null, starts_at: "10:00", title: "경복궁" }), lineEvent(3));
    const result = readingLines([], stream, true, ko);
    expect(result.map((line) => [line.no, line.text, line.state])).toEqual([[2, "10시 경복궁 관람 1시간 반", "read"], [3, "11시 올리브영", "read"]]);
    expect(result[0].tag).toBe("1일차 10:00 · 경복궁");
  });

  it("does not list a line twice when both the plan read and the stream know it", () => {
    const stream = heard(lineEvent(1));
    expect(readingLines(source, stream, true, ko).filter((line) => line.no === 1)).toHaveLength(1);
  });

  it("says the tag in English too", () => {
    expect(foundTag({ id: "0-0", index: 0, day: 2, date: null, starts_at: "15:00", title: "N서울타워" }, en)).toBe("Day 2 15:00 · N서울타워");
    expect(foundTag({ id: "0-0", index: 0, day: null, date: null, starts_at: null, title: "경복궁" }, ko)).toBe("경복궁");
  });

  it("counts the stops found so far from the tags, or from the stops the stream listed if that is more", () => {
    const stream = heard(lineEvent(2, { id: "0-0", index: 0, day: 1, date: null, starts_at: "10:00", title: "경복궁" }));
    expect(foundCount(readingLines(source, stream, true, ko), stream)).toBe(1);
    const item = { id: "0-1", source_id: "s1", index: 1, title: "올리브영", kind: null, day: 1, date: null, starts_at: "11:00", ends_at: null, locked: false, status: null, can_lock: false, place_state: "searching", place: null, candidates_hint: null } as const;
    const more = reduceStream(stream, { type: "item", item: { ...item, place_state: "searching" } });
    expect(foundCount(readingLines(source, more, true, ko), more)).toBe(1);
    const two = reduceStream(more, { type: "item", item: { ...item, id: "0-2", index: 2 } });
    expect(foundCount(readingLines(source, two, true, ko), two)).toBe(2);
  });
});
