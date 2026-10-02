import { describe, expect, it } from "vitest";
import type { IntakeItem, IntakeView } from "@/lib/live/intake";
import { readingOf } from "./from-intake";

const field = (value: unknown) => ({ value, method: "rule" as const, evidence: {}, needs_review: false, note: null });
const item = (index: number, line: number, day: number | null, fields: IntakeItem["fields"]): IntakeItem => ({ index, line, day, date: null, fields });

function intake(stage: string, status: IntakeView["status"], sources: IntakeView["sources"]): IntakeView {
  return { intake_id: "i1", status, stage, stage_label: "", revision: 1, fatal: null, trip_id: null, sources, check: null, needs_review: [] };
}

const text = (lines: [string, boolean][], items: IntakeItem[] = []) => ({
  source_id: "s1", kind: "text", filename: null, transcribed: false, items, trip: {}, reading: null,
  lines: lines.map(([value, read], at) => ({ no: at + 1, text: value, read })),
});

describe("plan check reading, from the server's intake", () => {
  it("maps the server's stage: received stays received, transcribing and reading are reading, a finished read stays reading", () => {
    expect(readingOf(intake("received", "reading", [])).stage).toBe("received");
    expect(readingOf(intake("transcribing", "reading", [])).stage).toBe("reading");
    expect(readingOf(intake("reading", "reading", [])).stage).toBe("reading");
    expect(readingOf(intake("review", "review", [])).stage).toBe("reading");     // the review screen takes over from here
  });

  it("keeps each line and whether the server read it, and the stop a read line became — day or time only when the server has one", () => {
    const view = readingOf(intake("reading", "reading", [text([["10/1 09:00 경복궁 관람", true], ["점심은 광장시장", true], ["메모: 우산", false]], [
      item(0, 1, 1, { title: field("경복궁 관람"), starts_at: field("09:00") }),
      item(1, 2, null, { title: field("광장시장") }),
    ])]));
    expect(view.lines).toEqual([
      { no: 1, text: "10/1 09:00 경복궁 관람", read: true, found: { kind: "item", day: 1, startsAt: "09:00", title: "경복궁 관람" } },
      { no: 2, text: "점심은 광장시장", read: true, found: { kind: "item", day: null, startsAt: null, title: "광장시장" } },
      { no: 3, text: "메모: 우산", read: false, found: null },
    ]);
    expect(view.items).toEqual([]);                                                 // places and checks are not mapped yet
  });

  it("numbers lines across sources and leaves out a stop the customer removed", () => {
    const photo = { ...text([["11:00 올리브영", true]], [item(0, 1, 1, { title: field("올리브영"), removed: field(true) })]), source_id: "s2", kind: "image" };
    const view = readingOf(intake("reading", "reading", [text([["10/1 09:00 경복궁", true]]), photo]));
    expect(view.lines.map((line) => [line.no, line.text, line.found])).toEqual([[1, "10/1 09:00 경복궁", null], [2, "11:00 올리브영", null]]);
  });
});
