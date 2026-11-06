import { describe, expect, it } from "vitest";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { readingOf } from "./from-intake";
import { reviewResultOf } from "./from-review";

function checks(risk: unknown) {
  const intake = {
    intake_id: "i1", status: "review", stage: "review", stage_label: "", fatal: null, trip_id: null,
    revision: 1, sources: [], needs_review: [], check: null,
    review: { revision: 1, built_at: "", engine: "estimate", ready: true, moves: [], needs: { items: 0, moves: 0, total: 0 },
      items: [{ id: "0-0", source_id: "s1", index: 0, title: "방문", kind: "activity", day: 1, date: "2030-01-10",
        starts_at: "09:00", ends_at: "10:00", locked: false, status: "keep", can_lock: true,
        place_state: "found", place: null, candidates_hint: null, rows: [], risk }] },
  } as ReviewedIntakeView;
  return reviewResultOf(intake, readingOf(intake))!.items[0].checks;
}

describe("date risk checks", () => {
  it("omits deferred timing-only checks but keeps problems and real unknowns", () => {
    expect(checks({ status: "unknown", deferred: true })).toEqual([]);
    expect(checks({ status: "problem", deferred: true, problems: [{ message: "통제" }] })).toMatchObject([{ kind: "risk", result: "warn" }]);
    expect(checks({ status: "unknown", unknown_categories: [{ label: "교통" }] })).toMatchObject([{ kind: "risk", result: "unknown" }]);
    expect(checks({ status: "unknown", deferred: true, unknown_categories: [{ label: "교통" }] })).toMatchObject([{ result: "unknown" }]);
  });
});
