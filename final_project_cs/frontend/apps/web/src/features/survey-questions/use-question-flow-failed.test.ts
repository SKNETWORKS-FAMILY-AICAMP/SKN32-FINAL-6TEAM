import { afterEach, describe, expect, it, vi } from "vitest";
import type { SurveyQuestion } from "./model";
import { useQuestionFlow } from "./use-question-flow";

// ★`[2026-10-26 사용자 보고 — 「이거 이렇게 완료가 안 되었는데 다음 화면 뜨는 버그」]` x600 접수 cba8a775 는 `status: fatal`(`reading_model_failed`)로 끝났는데,
//   질문에 답하던 고객의 읽기 화면은 막대 「일정 읽기 8/9줄 · 15초째」인 채로 「✓ 계획을 다 읽었어요」와 켜진 「읽어 온 계획 확인하기」를 보였다.
//   읽기 실패(`fatal`)는 「다 읽었어요」가 아니다 — 화면을 붙잡지 않고(`hold` 없음) 실패 화면(「이 계획을 읽지 못했어요」 · `fatal.detail`)으로 간다(web-intakes 125 · 129행).
const harness = vi.hoisted(() => ({
  slots: [] as { value?: unknown; deps?: readonly unknown[]; cleanup?: () => void }[], cursor: 0,
  effects: [] as (() => void)[], submit: vi.fn(),
}));
vi.mock("@/lib/live/intake", () => ({ submitSurveyAnswers: harness.submit }));
vi.mock("react", () => ({
  useState: (value: unknown) => {
    const at = harness.cursor++, slot = harness.slots[at] ??= { value };
    return [slot.value, (next: unknown) => { slot.value = typeof next === "function" ? next(slot.value) : next; }];
  },
  useRef: (value: unknown) => (harness.slots[harness.cursor++] ??= { value: { current: value } }).value,
  useCallback: (run: unknown) => { harness.cursor++; return run; },
  useEffect: (run: () => void | (() => void), deps?: readonly unknown[]) => {
    const slot = harness.slots[harness.cursor++] ??= {};
    if (deps && slot.deps && deps.every((value, index) => Object.is(value, slot.deps![index]))) return;
    slot.deps = deps;
    harness.effects.push(() => { slot.cleanup?.(); const cleanup = run(); slot.cleanup = typeof cleanup === "function" ? cleanup : undefined; });
  },
}));

const party: SurveyQuestion = { id: "party", kind: "single", title: "누구와 함께 떠나나요?", why: "", options: [{ id: "friends", label: "친구" }],
  allowCustom: false, customMaxLength: 0, customLabel: "", answer: null };
const pace: SurveyQuestion = { id: "pace", kind: "single", title: "일정은 어느 정도로 채울까요?", why: "", options: [{ id: "relaxed", label: "여유 있게" }],
  allowCustom: false, customMaxLength: 0, customLabel: "", answer: null };
const questions = [party, pace];

type Outcome = "reading" | "read" | "failed";
function draw(outcome: Outcome) {
  harness.cursor = 0; harness.effects = [];
  // A render may set state while it runs (the hook decides the phase once the reading ends); React renders again until it settles.
  let flow = render(outcome);
  for (let pass = 0; pass < 3; pass += 1) { harness.cursor = 0; harness.effects = []; flow = render(outcome); }
  for (const run of harness.effects) run();
  return flow;
}
function render(outcome: Outcome) {
  // eslint-disable-next-line react-hooks/rules-of-hooks -- Controlled React storage in this Node harness.
  return useQuestionFlow({ intakeId: "intake-failed", language: "ko", questions, fresh: true,
    loadingDone: outcome !== "reading", loadingFailed: outcome === "failed" });
}

afterEach(() => {
  for (const slot of harness.slots) slot.cleanup?.();
  harness.slots = []; harness.cursor = 0; harness.effects = []; harness.submit.mockReset();
});

describe("읽기 화면 질문 흐름 — 읽기 실패(fatal)는 「다 읽었어요」가 아니다", () => {
  it("읽는 중에는 「읽는 중」(read)이고, 성공으로 끝나면 질문을 건드리지 않은 고객에게 「다 읽었어요」(done)", () => {
    expect(draw("reading").phase).toBe("read");
    const done = draw("read");
    expect(done.phase).toBe("done");
    expect(done.hold).toBe(true);
  });

  it("질문에 손대지 않은 채 읽기가 실패하면 화면을 붙잡지 않는다(「다 읽었어요」 · 확인 단추 없음)", () => {
    expect(draw("reading").phase).toBe("read");
    const failed = draw("failed");
    expect(failed.phase).toBe("gone");
    expect(failed.hold).toBe(false);
    expect(failed.shown).toBe(false);
  });

  it("「자동으로 넘어가지 않기」로 붙잡은 고객(사용자 화면)도 실패하면 붙잡지 않는다", () => {
    expect(draw("reading").phase).toBe("read");
    const flow = draw("read");
    flow.stop();
    const held = draw("read");
    expect(held.phase).toBe("late");
    expect(held.stopAuto).toBe(true);
    const failed = draw("failed");
    expect(failed.phase).toBe("gone");
    expect(failed.hold).toBe(false);
  });

  it("질문에 답하던 중(late)에 읽기가 실패해도 붙잡지 않는다", () => {
    const reading = draw("reading");
    reading.touchQuestions();
    expect(draw("reading").phase).toBe("read");
    const failed = draw("failed");
    expect(failed.phase).toBe("gone");
    expect(failed.hold).toBe(false);
  });
});
