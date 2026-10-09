import { describe, expect, it } from "vitest";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { ReviewUndo } from "./review-undo";

function plan(id = "intake-a", revision = 1, title = "경복궁"): ReviewedIntakeView {
  return { intake_id: id, revision, status: "review", sources: [{ source_id: "source-a", trip: {}, items: [
    { index: 0, fields: { title: { value: title } } },
  ] }], review: { revision } } as ReviewedIntakeView;
}

describe("one intake's complete undo original", () => {
  it("keeps the first saved original across place/time/title/add/delete changes", () => {
    const undo = new ReviewUndo("intake-a");
    undo.remember(plan(), plan("intake-a", 2, "호텔"));
    undo.remember(plan("intake-a", 2, "호텔"), plan("intake-a", 3, "시장"));
    expect(undo.target(plan("intake-a", 3, "시장"))).toBe(1);
    // Nothing calls restored on a failed HTTP request, so retry has the same target.
    expect(undo.target(plan("intake-a", 3, "시장"))).toBe(1);
    undo.restored(plan("intake-a", 4));
    expect(undo.canRestore(plan("intake-a", 4))).toBe(false);
    undo.remember(plan("intake-a", 4), plan("intake-a", 5, "광장시장"));
    expect(undo.target(plan("intake-a", 5, "광장시장"))).toBe(1);
  });

  it("cannot carry an original into another intake or accept an expired request's response", () => {
    const a = new ReviewUndo("intake-a"), b = new ReviewUndo("intake-b");
    a.remember(plan(), plan("intake-a", 2, "호텔"));
    expect(a.canRestore(plan("intake-b", 2, "호텔"))).toBe(false);
    a.active = false;
    a.remember(plan(), plan("intake-a", 3, "시장"));
    expect(a.canRestore(plan("intake-a", 2, "호텔"))).toBe(false);
    expect(b.canRestore(plan("intake-b", 2, "호텔"))).toBe(false);
  });

  it.each(["reading", "preview", "missing-review"])("never invents an original from %s", (invalid) => {
    const undo = new ReviewUndo("intake-a");
    const before = plan();
    if (invalid === "reading") before.status = "reading";
    if (invalid === "preview") before.preview = true;
    if (invalid === "missing-review") before.review = null;
    undo.remember(before, plan("intake-a", 2, "호텔"));
    undo.remember(plan("intake-a", 2, "호텔"), plan("intake-a", 3, "시장"));
    expect(undo.canRestore(plan("intake-a", 3, "시장"))).toBe(false);
  });

  it("does not restore a plan changed elsewhere after the recorded save", () => {
    const undo = new ReviewUndo("intake-a");
    undo.remember(plan(), plan("intake-a", 2, "호텔"));
    expect(undo.canRestore(plan("intake-a", 3, "다른 화면 변경"))).toBe(false);
  });

  it("ignores provenance and validation-only updates when checking if values differ", () => {
    const undo = new ReviewUndo("intake-a");
    const next = plan("intake-a", 2);
    next.sources[0].items[0].fields.title!.method = "customer";
    undo.remember(plan(), next);
    expect(undo.canRestore(next)).toBe(false);
  });
});
