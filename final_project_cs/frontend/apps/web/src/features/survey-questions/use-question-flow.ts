"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Language } from "@/lib/i18n";
import { submitSurveyAnswers } from "@/lib/live/intake";
import { allAnswered, nextOpen, openIndexes, unanswered, type Answers, type SurveyQuestion } from "./model";

/** Times of the loading-time questions (mockup v9 `TIMING`; the movement times live in the CSS). */
export const TIMING = {
  /** Loading is done and questions are left: this long without a touch and the 20-second warning opens. */
  idleMs: 30_000,
  /** The warning counts down this many seconds, then the plan check opens. */
  countdownS: 20,
  /**
   * The plan is read and nothing is left to wait for: the notice is shown and the plan check opens after this long, unless the customer touches a question or stops it. ★`[2026-10-06 사용자 지시]` 5 s
   * (there is a button to go on at once): long enough to see that the reading is done and what is left, whether every question was answered or none was touched.
   */
  doneMs: 5_000,
  /** After an answer is saved the next open question comes after this long (long enough to see 「저장했어요」). */
  advanceMs: 400,
} as const;

/**
 * `read`  - the server is still reading: the questions are shown under the progress, the big button says 「계획 읽는 중…」.
 * `late`  - reading is done and the customer is in the middle of answering: the screen stays (the question must not be taken away) and the button is on.
 * `idle`  - `late`, but nobody touched anything for `idleMs`: the 20-second warning (an `alertdialog`) counts down to the plan check.
 * `done`  - the plan is read and the customer is not in the middle of answering (all answered, OR no question was touched): the notice and a 5-second bar, then the plan check. A touch on a question turns it into `late`.
 * `gone`  - nothing more is asked, the screen goes on to the plan check (or never held it).
 */
export type Phase = "read" | "late" | "idle" | "done" | "gone";

type Slide = "" | "from-right" | "from-left";

export interface QuestionFlow {
  phase: Phase;
  /** The reading screen is held for the questions though the server has finished (`late` · `idle` · `done`). */
  hold: boolean;
  /** The questions are on the screen (there are some and the flow has not ended). */
  shown: boolean;
  questions: readonly SurveyQuestion[];
  /** The question on view. */
  at: number;
  answers: Answers;
  skipped: ReadonlySet<string>;
  open: readonly number[];
  allDone: boolean;
  /** How many have no answer (skipped ones included) - what is left for later. */
  left: number;
  busy: boolean;
  /** 「저장했어요」 is up for the question on view. */
  saved: boolean;
  /** An answer the server did not take: the question and the option the customer picked (kept picked, with 「다시 시도하기」). */
  failed: { id: string; option: string } | null;
  slide: Slide;
  /** Raised when the focus should go to the title of the question on view (a move the customer asked for). */
  focusNonce: number;
  seconds: number;
  stopAuto: boolean;
  navigate: (delta: 1 | -1) => void;
  choose: (optionId: string) => void;
  retry: () => void;
  skip: () => void;
  /** Go on to the plan check now. */
  release: () => void;
  /** 「자동으로 넘어가지 않기」: the screen stays until the customer presses the button. */
  stop: () => void;
  /** 「계속 답하기」 on the warning. */
  keepAnswering: () => void;
  /** Anything touched on the screen: the customer is there (restarts the idle count, and counts as having touched the questions). */
  touch: () => void;
  /** A touch on the questions themselves: also stops the countdown bar. */
  touchQuestions: () => void;
}

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계 · 목업 v9 `finishLoading` · `answer` · `navigate`]` The state of the questions asked while the server reads, and what happens to the screen
 * when the reading is done: it goes straight on when nothing was touched (or nothing is open), waits in `late` while the customer answers, and in `done` shows a 3-second bar once all are answered.
 *
 * ★An answer is saved at once, one question at a time (`POST …/trip-intakes/{id}/survey`); the server keeps the last value of a question, so going back to correct it is just another answer.
 *   A save that fails keeps the picked option picked, says so with 「다시 시도하기」 and does not move on.
 */
export function useQuestionFlow({ intakeId, language, questions, loadingDone }: { intakeId: string; language: Language; questions: readonly SurveyQuestion[]; loadingDone: boolean }): QuestionFlow {
  const [phase, setPhase] = useState<Phase>("read");
  const [at, setAt] = useState(0);
  const [answers, setAnswers] = useState<Answers>({});
  const [skippedIds, setSkippedIds] = useState<readonly string[]>([]);
  const [touched, setTouched] = useState(false);
  const [stopAuto, setStopAuto] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [failed, setFailed] = useState<{ id: string; option: string } | null>(null);
  const [slide, setSlide] = useState<Slide>("");
  const [focusNonce, setFocusNonce] = useState(0);
  const [seconds, setSeconds] = useState<number>(TIMING.countdownS);
  const [activity, setActivity] = useState(0);
  const skipped = new Set(skippedIds);
  const open = openIndexes(questions, answers, skipped);
  const allDone = allAnswered(questions, answers);

  // Reading is done (the server has finished): decide ONCE what the screen does (mockup `finishLoading`).
  // ★`[2026-10-06 사용자 지적]` Untouched questions no longer send the customer straight on: the notice is shown and the screen waits `doneMs`, then goes (it used to jump at once).
  if (loadingDone && phase === "read") {
    if (questions.length === 0) setPhase("gone");
    else if (allDone || !touched) setPhase("done");
    else if (open.length === 0) setPhase("gone");                      // some were answered, the rest skipped: nothing left to ask
    else { setPhase("late"); setAt(open[0]); }
  }
  // The warning ran out.
  if (phase === "idle" && seconds <= 0) setPhase("gone");

  const latest = useRef({ phase, stopAuto, skippedIds, answers, questions, at });
  useEffect(() => { latest.current = { phase, stopAuto, skippedIds, answers, questions, at }; });
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  // 30 s without a touch while the customer is answering after the reading: the warning.
  useEffect(() => {
    if (phase !== "late" || stopAuto) return;
    const id = setTimeout(() => { setSeconds(TIMING.countdownS); setPhase("idle"); }, TIMING.idleMs);
    return () => clearTimeout(id);
  }, [phase, stopAuto, activity]);
  // Everything answered: the plan check opens after the bar.
  useEffect(() => {
    if (phase !== "done") return;
    const id = setTimeout(() => setPhase("gone"), TIMING.doneMs);
    return () => clearTimeout(id);
  }, [phase]);
  // The warning counts down.
  useEffect(() => {
    if (phase !== "idle") return;
    const id = setInterval(() => setSeconds((value) => value - 1), 1000);
    return () => clearInterval(id);
  }, [phase]);

  const touch = useCallback(() => { setTouched(true); setActivity((value) => value + 1); }, []);
  const touchQuestions = useCallback(() => {
    touch();
    setPhase((value) => value === "done" ? "late" : value);
  }, [touch]);

  const move = useCallback((to: number, delta: 1 | -1) => {
    setAt(to);
    setSaved(false);
    setSlide(delta > 0 ? "from-right" : "from-left");
    setFocusNonce((value) => value + 1);
  }, []);

  const navigate = useCallback((delta: 1 | -1) => {
    const to = Math.min(questions.length - 1, Math.max(0, at + delta));
    if (to === at || busy) return;
    touchQuestions();
    move(to, delta);
  }, [questions.length, at, busy, touchQuestions, move]);

  const choose = useCallback((optionId: string) => {
    const question = questions[at];
    if (!question || busy) return;
    touchQuestions();
    const wasAll = allAnswered(questions, answers);
    setFailed(null);
    setSaved(false);
    setBusy(true);
    void submitSurveyAnswers(intakeId, { [question.id]: optionId }, language).then(() => {
      const next: Answers = { ...answers, [question.id]: optionId };
      setAnswers(next);
      setSaved(true);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        setBusy(false);
        const now = latest.current;
        if (now.phase === "late" && !now.stopAuto && !wasAll && allAnswered(now.questions, next)) { setPhase("done"); return; }
        const target = nextOpen(openIndexes(now.questions, next, new Set(now.skippedIds)), at);
        if (target !== null) move(target, 1);
      }, TIMING.advanceMs);
    }, () => {
      setFailed({ id: question.id, option: optionId });
      setBusy(false);
    });
  }, [questions, at, busy, answers, intakeId, language, touchQuestions, move]);

  const retry = useCallback(() => { if (failed) choose(failed.option); }, [failed, choose]);

  const skip = useCallback(() => {
    const question = questions[at];
    if (!question || busy) return;
    touchQuestions();
    const nextSkipped = [...skippedIds, question.id];
    setSkippedIds(nextSkipped);
    setSaved(false);
    setFailed(null);
    const stillOpen = openIndexes(questions, answers, new Set(nextSkipped));
    if (phase === "late" && !stopAuto && stillOpen.length === 0) { setPhase("gone"); return; }
    const target = nextOpen(stillOpen, at);
    if (target !== null) move(target, 1);
  }, [questions, at, busy, skippedIds, answers, phase, stopAuto, touchQuestions, move]);

  const release = useCallback(() => setPhase("gone"), []);
  const stop = useCallback(() => { setStopAuto(true); setPhase("late"); setActivity((value) => value + 1); }, []);
  const keepAnswering = useCallback(() => { setSeconds(TIMING.countdownS); setPhase("late"); setActivity((value) => value + 1); }, []);

  return {
    phase, hold: phase === "late" || phase === "idle" || phase === "done", shown: questions.length > 0 && phase !== "gone",
    questions, at, answers, skipped, open, allDone, left: unanswered(questions, answers), busy, saved, failed, slide, focusNonce, seconds, stopAuto,
    navigate, choose, retry, skip, release, stop, keepAnswering, touch, touchQuestions,
  };
}
