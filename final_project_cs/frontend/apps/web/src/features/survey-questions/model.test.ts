import { describe, expect, it } from "vitest";
import type { IntakeQuestion } from "@/lib/live/intake";
import { allAnswered, nextOpen, openIndexes, questionsOf, unanswered } from "./model";

const mobility: IntakeQuestion = { id: "preferred_mobility", kind: "single", title: "이동은 주로 어떻게 하세요?", why: "이유", options: [{ id: "public", label: "대중교통" }, { id: "taxi", label: "택시" }], answer: null };
const priority: IntakeQuestion = { id: "priority", kind: "single", title: "대체할 곳은?", why: "알 수 없어요", options: [{ id: "activity", label: "활동" }, { id: "mobility", label: "이동" }], answer: "activity" };

describe("the questions the page draws", () => {
  it("draws what the server sends, in its order, with the answer it already holds", () => {
    const drawn = questionsOf([mobility, priority], "ko");
    expect(drawn.map((question) => question.id)).toEqual(["preferred_mobility", "priority"]);
    expect(drawn[0]).toMatchObject({ title: "이동은 주로 어떻게 하세요?", answer: null });
    expect(drawn[1].answer).toBe("activity");
  });

  it("leaves out only the question it cannot draw: an unknown kind, a missing title, no usable option, a repeated id", () => {
    const bad: unknown[] = [
      { ...mobility, id: "a", kind: "multi" },
      { ...mobility, id: "b", title: "" },
      { ...mobility, id: "c", options: [] },
      { ...mobility, id: "d", options: [{ id: "x" }, { label: "y" }, null] },
      { ...priority, id: "preferred_mobility" },
      null, "text", 3,
    ];
    expect(questionsOf([mobility, ...(bad as IntakeQuestion[]), priority], "ko").map((question) => question.id)).toEqual(["preferred_mobility", "priority"]);
  });

  it("draws nothing for an older server (no list) and keeps an unknown answer out", () => {
    expect(questionsOf(undefined, "ko")).toEqual([]);
    expect(questionsOf(null, "ko")).toEqual([]);
    expect(questionsOf([{ ...mobility, answer: "car" }], "ko")[0].answer).toBeNull();
  });

  it("puts the known ids into English and leaves an id it does not know in the server's words", () => {
    const [first, other] = questionsOf([mobility, { ...priority, id: "future_question", options: [{ id: "x", label: "엑스" }] }], "en");
    expect(first.title).toBe("How do you usually get around?");
    expect(first.options.map((option) => option.label)).toEqual(["Public transport", "Taxi"]);
    expect(other.title).toBe("대체할 곳은?");
    expect(other.options[0].label).toBe("엑스");
  });
});

describe("what is left to ask", () => {
  const questions = questionsOf([mobility, priority, { ...mobility, id: "third" }], "ko");        // priority already answered by the server

  it("lists the open ones: not answered and not skipped; a saved answer counts", () => {
    expect(openIndexes(questions, {}, new Set())).toEqual([0, 2]);
    expect(openIndexes(questions, { preferred_mobility: "taxi" }, new Set())).toEqual([2]);
    expect(openIndexes(questions, {}, new Set(["third"]))).toEqual([0]);
    expect(unanswered(questions, {})).toBe(2);
    expect(unanswered(questions, { preferred_mobility: "taxi", third: "public" })).toBe(0);
  });

  it("is all answered only when every question has an answer (a skipped one does not count) and there is something to ask", () => {
    expect(allAnswered(questions, { preferred_mobility: "taxi", third: "public" })).toBe(true);
    expect(allAnswered(questions, { preferred_mobility: "taxi" })).toBe(false);
    expect(allAnswered([], {})).toBe(false);
  });

  it("goes to the next open one after the answered one, else the first open one before it, else nowhere", () => {
    expect(nextOpen([0, 2], 0)).toBe(2);
    expect(nextOpen([0, 2], 2)).toBe(0);
    expect(nextOpen([0, 1, 3], 1)).toBe(3);
    expect(nextOpen([1], 1)).toBeNull();
    expect(nextOpen([], 0)).toBeNull();
  });
});
