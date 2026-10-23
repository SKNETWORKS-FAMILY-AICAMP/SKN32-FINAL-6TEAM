import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { DiningAnswer, DiningQuestion, ReviewedIntakeView } from "@/lib/live/intake-review";
import { DiningQuestions, diningAnswer, canApplyDiningAnswer } from "./dining-questions";

const question: DiningQuestion = { id: "q1", quote: "그 식당은 할랄이어야 해요.", attribute: "halal", required: true,
  choices: [{ item_id: "lunch", date: "2026-10-25", starts_at: "12:00", title: "점심" },
    { item_id: "dinner", date: "2026-10-25", starts_at: "18:00", title: "저녁" }], answer: null };

describe("restaurant condition clarification", () => {
  it("shows the original quote and actual meal choices separately from the reading survey", () => {
    const html = renderToStaticMarkup(createElement(DiningQuestions, {
      questions: [question], busy: false, onAnswer: async () => {}, status: null,
    }));
    expect(html).toContain(question.quote);
    expect(html).toContain("12:00");
    expect(html).toContain("18:00");
    expect(html).toContain("이 조건 취소");
    expect(html).not.toContain("박물관");
  });
  it("sends selected ids with the current revision and run token, keeping source fields server owned", () => {
    expect(diningAnswer(2, "run-1", question, ["dinner"], false)).toEqual({
      revision: 2, run_id: "run-1", question_id: "q1", item_ids: ["dinner"], excluded: false,
    });
    expect(diningAnswer(2, "run-1", question, [], true).excluded).toBe(true);
  });
  it("does not allow empty active scopes or foreign choices", () => {
    expect(() => diningAnswer(2, "run-1", question, [], false)).toThrow();
    expect(() => diningAnswer(2, "run-1", question, ["museum"], false)).toThrow();
    expect(() => diningAnswer(2, "run-1", question, ["dinner"], true)).toThrow();
  });
  it("keeps the saved answer selected and disables controls while rechecking", () => {
    const html = renderToStaticMarkup(createElement(DiningQuestions, {
      questions: [{ ...question, answer: { item_ids: ["dinner"], excluded: false } }],
      busy: true, onAnswer: async () => {}, status: "선택하신 조건을 다시 확인하고 있어요",
    }));
    expect(html).toContain("checked");
    expect(html).toContain("disabled");
    expect(html).toContain("선택하신 조건을 다시 확인하고 있어요");
  });
  it("rejects an answer response after a newer revision or run already reached the cache", () => {
    const snapshot = (revision: number, run: string) => ({ intake_id: "i1", status: "review", revision,
      review: { dining_judge: { revision, run_id: run, status: "pending" } } }) as ReviewedIntakeView;
    const sent: DiningAnswer = { revision: 2, run_id: "old", question_id: "q1", item_ids: ["dinner"], excluded: false };
    expect(canApplyDiningAnswer(snapshot(2, "old"), snapshot(2, "answer-run"), sent)).toBe(true);
    expect(canApplyDiningAnswer(snapshot(3, "new"), snapshot(2, "answer-run"), sent)).toBe(false);
    expect(canApplyDiningAnswer(snapshot(2, "already-newer"), snapshot(2, "answer-run"), sent)).toBe(false);
    expect(canApplyDiningAnswer({ ...snapshot(2, "old"), status: "confirmed" }, snapshot(2, "answer-run"), sent)).toBe(false);
  });
});
