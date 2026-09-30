import { describe, expect, it } from "vitest";
import type { Notice, Proposal } from "@/lib/live/extras";
import { NOTICE_LIMIT, openChoices, recentNotices, undoableChange } from "./attention";
import type { TripStop } from "./model";

const stop = (id: string): TripStop => ({ id, date: "2026-09-28", time: "12:00", title: "황생가칼국수", booking: "unknown", notes: "" });
const proposal = (id: string, status: string): Proposal => ({ id, itemId: "i1", baseVersion: 1, reason: "closed", status, safety: false, expiresAt: null, options: [] });
const notice = (key: string, at: string, over: Partial<Notice> = {}): Notice => ({ key, type: "change_notice", kind: null, text: "t", version: 1, proposalId: null, delivery: "sent", at, rollback: null, ...over });

describe("what the trip screen asks the customer to decide", () => {
  it("lists only proposals that are still open, with the stop they are about", () => {
    const choices = openChoices([proposal("p1", "open"), proposal("p2", "kept"), proposal("p3", "chosen")], [], [stop("i1")]);
    expect(choices.map((choice) => choice.proposal.id)).toEqual(["p1"]);
    expect(choices[0].stop?.title).toBe("황생가칼국수");
  });

  it("takes the sentence from the notice that carries the proposal, and says nothing of its own when there is none", () => {
    const withText = openChoices([proposal("p1", "open")], [notice("n1", "2026-09-28T12:00:00+09:00", { type: "proposal_request", proposalId: "p1", text: "식당이 닫았어요." })], [stop("i1")]);
    expect(withText[0].text).toBe("식당이 닫았어요.");
    expect(openChoices([proposal("p1", "open")], [], [stop("i1")])[0].text).toBeNull();
  });

  it("keeps a choice whose stop is gone — the proposal is still open, hiding it would hide a decision", () => {
    expect(openChoices([proposal("p1", "open")], [], [])[0].stop).toBeNull();
  });
});

describe("the notice list", () => {
  it("shows the newest first and says how many it left out", () => {
    const many = Array.from({ length: NOTICE_LIMIT + 3 }, (_, index) => notice(`n${index}`, `2026-09-28T${String(10 + (index % 10)).padStart(2, "0")}:00:00+09:00`));
    const { shown, total, hidden } = recentNotices(many);
    expect(shown).toHaveLength(NOTICE_LIMIT);
    expect(total).toBe(NOTICE_LIMIT + 3);
    expect(hidden).toBe(3);
    expect(Date.parse(shown[0].at)).toBeGreaterThanOrEqual(Date.parse(shown[1].at));
  });

  it("offers an undo only for the automatic change that made the version the trip is on now", () => {
    const undo = (base: number) => ({ baseVersion: base, toVersion: base - 1, requestId: `rollback:v${base}->v${base - 1}` });
    const notices = [notice("n2", "2026-09-28T10:00:00+09:00", { rollback: undo(2) }), notice("n3", "2026-09-28T11:00:00+09:00", { rollback: undo(3) }),
      notice("n4", "2026-09-28T12:00:00+09:00")];                                   // a change without an undo
    expect(undoableChange(notices, 3)?.key).toBe("n3");
    expect(undoableChange(notices, 4)).toBeNull();                                   // the plan moved on — an older undo would be refused
    expect(undoableChange(notices, undefined)).toBeNull();
  });
});
