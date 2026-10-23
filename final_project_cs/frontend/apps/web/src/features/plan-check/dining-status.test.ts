import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import type { IntakeDiningJudge, ReviewItem, ReviewedIntakeView } from "@/lib/live/intake-review";
import { currentDiningJudge, diningRegistrationProblems, diningRegistrationReason, diningStatusText, intakeRefetchInterval, intakeRegistrationReady, refreshIntakeAfter, registrationIntentDecision } from "./dining-status";

const judge = (status: IntakeDiningJudge["status"], patch: Partial<IntakeDiningJudge> = {}): IntakeDiningJudge => ({
  status, revision: 3, run_id: "run-a", started_at: null, deadline_at: null, completed_at: null, error_code: null, ...patch,
});
const meal = (rows: ReviewItem["rows"]): ReviewItem => ({
  id: "0-0", source_id: "s1", index: 0, title: "점심 식사", kind: "dining", day: 1, date: "2026-10-20", starts_at: "12:00", ends_at: "13:00",
  locked: false, status: "keep", can_lock: true, place_state: "found", place: null, candidates_hint: null, rows,
});
const intake = (dining: IntakeDiningJudge | null = null, patch: Partial<ReviewedIntakeView> = {}): ReviewedIntakeView => ({
  intake_id: "i1", revision: 3, status: "review", stage: "review", stage_label: "", fatal: null, trip_id: null,
  sources: [], check: null, needs_review: [],
  review: { revision: 3, dining_judge: dining, built_at: "", engine: null, items: [], moves: [], needs: { items: 0, moves: 0, total: 0 }, ready: true }, ...patch,
});

describe("following the current restaurant check after reading", () => {
  it.each(["pending", "running"] as const)("polls %s without a reading SSE or its fallback flag", (status) => {
    expect(intakeRefetchInterval(intake(judge(status)), false, null)).toBe(1500);
  });

  it.each(["completed", "failed", "disabled"] as const)("stops polling at %s", (status) => {
    expect(intakeRefetchInterval(intake(judge(status)), true, null)).toBe(false);
  });

  it("stops on GET errors, confirmed/fatal plans, old revisions and old servers", () => {
    expect(intakeRefetchInterval(intake(judge("running")), false, new Error("offline"))).toBe(false);
    expect(intakeRefetchInterval(intake(judge("running"), { status: "confirmed" }), true, null)).toBe(false);
    expect(intakeRefetchInterval(intake(judge("running"), { status: "fatal" }), true, null)).toBe(false);
    expect(intakeRefetchInterval(intake(judge("running", { revision: 2 })), true, null)).toBe(false);
    expect(intakeRefetchInterval(intake(), true, null)).toBe(false);
    expect(intakeRefetchInterval(undefined, true, null)).toBe(false);
  });

  it("keeps the old reading fallback and never polls an unsaved dry run", () => {
    expect(intakeRefetchInterval(intake(null, { status: "reading" }), false, null)).toBe(false);
    expect(intakeRefetchInterval(intake(null, { status: "reading" }), true, null)).toBe(1500);
    const preview = intake(judge("pending"), { preview: true });
    expect(currentDiningJudge(preview)).toBeNull();
    expect(intakeRefetchInterval(preview, true, null)).toBe(false);
    expect(intakeRegistrationReady(preview)).toBe(true);
  });
});

describe("registration follows verified restaurant results", () => {
  it.each(["pending", "running"] as const)("refuses %s even if an older ready flag remains true", (status) => {
    const view = intake(judge(status));
    expect(intakeRegistrationReady(view)).toBe(false);
    expect(diningRegistrationReason(view, translator("ko"))).toBeTruthy();
    expect(diningStatusText(currentDiningJudge(view), translator("ko"))).not.toContain("완료했어요");
  });

  it.each(["completed", "failed", "disabled"] as const)("uses ordinary readiness after %s", (status) => {
    expect(intakeRegistrationReady(intake(judge(status)))).toBe(true);
    expect(intakeRegistrationReady(intake(judge(status)), false)).toBe(false);
  });

  it("keeps an unsuccessful check advisory and offers an optional recheck", () => {
    const view = intake(judge("failed", { blocks_registration: false, error_code: "dining_judge_execution_failed" }));
    expect(intakeRegistrationReady(view)).toBe(true);
    expect(diningRegistrationReason(view, translator("ko"))).toBeNull();
    expect(diningStatusText(currentDiningJudge(view), translator("ko"))).toContain("확인하지 못했어요");
    expect(diningStatusText(currentDiningJudge(view), translator("ko"))).toContain("원하시면");
    expect(diningStatusText(currentDiningJudge(view), translator("en"))).toContain("if you wish");
  });

  it("keeps old-server readiness and the server's aggregate blocking flag", () => {
    expect(intakeRegistrationReady(intake())).toBe(true);
    expect(intakeRegistrationReady(intake(judge("completed", { blocks_registration: true })))).toBe(false);
    expect(diningRegistrationReason(intake(judge("completed", { blocks_registration: true })), translator("ko"))).toContain("필수 조건");
  });

  it.each(["completed", "failed"] as const)("blocks explicit required bad evidence after %s while preserving warning and unknown meanings", (status) => {
    const view = intake(judge(status));
    view.review!.items = [meal([
      { row: "dietary", result: "unknown", text: "채식 여부 미확인", requirement: "required", blocks_registration: true },
      { row: "kids", result: "warn", text: "아이 동반 선호", requirement: "preference", blocks_registration: false },
      { row: "payment", result: "bad", text: "현금 결제", requirement: "preference", blocks_registration: false },
    ])];
    expect(diningRegistrationProblems(view)).toEqual([]);
    expect(intakeRegistrationReady(view)).toBe(true);
    view.review!.items[0].rows!.push({ row: "business", result: "bad", text: "폐업으로 확인됐어요", requirement: "required", blocks_registration: true });
    expect(diningRegistrationProblems(view)).toEqual(["점심 식사: 폐업으로 확인됐어요"]);
    expect(intakeRegistrationReady(view)).toBe(false);
    expect(diningRegistrationReason(view, translator("ko"))).toContain("필수 조건");
  });

  it.each(["stale_revision", "intake_dining_check_pending", "intake_dining_check_failed", "intake_dining_conditions_unmet"])("refreshes the current view after %s", (code) => {
    expect(refreshIntakeAfter(new LiveError(code, "다시 확인해 주세요"))).toBe(true);
  });

  it("does not retry unrelated or network errors as restaurant-state conflicts", () => {
    expect(refreshIntakeAfter(new LiveError("item_locked", "고정 항목"))).toBe(false);
    expect(refreshIntakeAfter(new Error("offline"))).toBe(false);
  });
});

describe("the combined preview apply and registration intent", () => {
  const intent = { intakeId: "i1", revision: 3, runId: "run-a" };

  it("waits on the real revision then registers after its current check completes", () => {
    expect(registrationIntentDecision(intent, intake(judge("pending")), null)).toBe("wait");
    expect(registrationIntentDecision(intent, intake(judge("running")), null)).toBe("wait");
    expect(registrationIntentDecision(intent, intake(judge("completed")), null)).toBe("register");
  });

  it("registers the existing intent when a failed check has no verified blocking result", () => {
    expect(registrationIntentDecision(intent, intake(judge("failed", { blocks_registration: false })), null)).toBe("register");
    expect(registrationIntentDecision(intent, intake(judge("failed")), null)).toBe("register");
  });

  it.each(["completed", "failed"] as const)("cancels rather than confirming verified bad results after %s", (status) => {
    expect(registrationIntentDecision(intent, intake(judge(status, { blocks_registration: true })), null)).toBe("cancel");
    const view = intake(judge(status, { blocks_registration: false }));
    view.review!.items = [meal([{ row: "business", result: "bad", text: "폐업으로 확인됐어요", requirement: "required", blocks_registration: true }])];
    expect(registrationIntentDecision(intent, view, null)).toBe("cancel");
  });

  it("cancels on read errors without retrying a save", () => {
    expect(registrationIntentDecision(intent, intake(judge("completed")), new Error("offline"))).toBe("cancel");
  });

  it("drops intent when an edit, another worker, a confirmed view or a missing status supersedes it", () => {
    expect(registrationIntentDecision(intent, intake(judge("completed"), { revision: 4 }), null)).toBe("cancel");
    expect(registrationIntentDecision(intent, intake(judge("completed", { run_id: "run-b" })), null)).toBe("cancel");
    expect(registrationIntentDecision(intent, intake(judge("completed"), { intake_id: "i2" }), null)).toBe("cancel");
    expect(registrationIntentDecision(intent, intake(judge("completed"), { status: "confirmed" }), null)).toBe("cancel");
    expect(registrationIntentDecision(intent, intake(), null)).toBe("cancel");
  });
});
