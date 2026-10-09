"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type PointerEvent } from "react";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import { useT } from "@/lib/settings";
import { answerOf } from "./model";
import type { QuestionFlow } from "./use-question-flow";
import styles from "./survey-questions.module.css";

/** Slide: at least this many px sideways and clearly more sideways than down (mockup v9). */
const SWIPE_PX = 50;
const SWIPE_DOMINANCE = 1.5;

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계 · 목업 v9 `questionCard`]` The questions asked while the server reads: one card, ‹ › buttons with `i / N`, swipe or the arrow keys to move,
 * options as 48 px buttons (the picked one shows a check), 「이 질문 건너뛰기」 for an unanswered one, dots, and the line under it.
 * What is asked and what the options say is the server's (`questions[]`); nothing is built into this card. An answered question can be picked again to correct it (saved at once).
 */
export function QuestionPager({ flow }: { flow: QuestionFlow }) {
  const t = useT();
  const { questions, at, busy, saved, failed } = flow;
  const question = questions[at];
  const title = useRef<HTMLHeadingElement>(null);
  const card = useRef<HTMLElement>(null);
  const swipe = useRef<{ x: number; y: number } | null>(null);
  // ★`[2026-10-06 사용자 지시 — 설문이 나오면 거기로 시선이 가게]` The questions take the focus and move in with a short attention pulse (twice), so the eye goes there; a screen that asks for less motion gets the focus only.
  const [attention, setAttention] = useState(true);
  useEffect(() => {
    title.current?.focus({ preventScroll: true });
    card.current?.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, []);

  // A move the customer asked for (a button, a swipe, an answer that went on) puts the focus on the new question's title - not on the first run.
  useEffect(() => { if (flow.focusNonce > 0) title.current?.focus({ preventScroll: true }); }, [flow.focusNonce]);

  if (!question) return null;
  const count = questions.length;
  const picked = failed?.id === question.id && failed.option !== null ? failed.option : answerOf(question, flow.answers);
  const note = saved && answerOf(question, flow.answers) ? <><Check size={16} strokeWidth={1.8} aria-hidden="true" /> {t("저장했어요", "Saved")}</>
    : saved ? t("답을 취소했어요. 다시 입력해 주세요.", "Answer cleared. You can answer again.") : null;

  const down = (event: PointerEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest("input, textarea, form")) return;
    swipe.current = { x: event.clientX, y: event.clientY };
  };
  const up = (event: PointerEvent<HTMLElement>) => {
    const from = swipe.current;
    swipe.current = null;
    if (!from) return;
    const dx = event.clientX - from.x, dy = event.clientY - from.y;
    if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy) * SWIPE_DOMINANCE) flow.navigate(dx < 0 ? 1 : -1);
  };
  const key = (event: KeyboardEvent<HTMLElement>) => {
    if ((event.target as HTMLElement).closest("input, textarea, select")) return;
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    flow.navigate(event.key === "ArrowRight" ? 1 : -1);
  };

  return <section ref={card} className={styles.pager} data-attention={attention || undefined} aria-roledescription="carousel" aria-label={t(`질문 ${count}개`, `${count} questions`)}
    onPointerDownCapture={flow.touchQuestions} onKeyDown={key}
    onAnimationEnd={(event) => { if (event.target === event.currentTarget && event.animationName.toLowerCase().includes("pulse")) setAttention(false); }}>
    <div className={styles.top}>
      <button type="button" className={styles.nav} onClick={() => flow.navigate(-1)} disabled={at === 0 || busy}
        aria-label={t("이전 질문 보기", "Previous question")} data-tip={t("이전 질문 보기", "Previous question")} data-kbd=" · ←"><ChevronLeft strokeWidth={1.8} aria-hidden="true" /></button>
      <p className={styles.count} aria-live="polite">{at + 1} / {count}</p>
      <button type="button" className={styles.nav} onClick={() => flow.navigate(1)} disabled={at === count - 1 || busy}
        aria-label={t("다음 질문 보기", "Next question")} data-tip={t("다음 질문 보기", "Next question")} data-kbd=" · →"><ChevronRight strokeWidth={1.8} aria-hidden="true" /></button>
    </div>
    <div key={question.id} className={styles.slide} data-slide={flow.slide || undefined} aria-roledescription="slide" aria-label={`${at + 1} / ${count}`} onPointerDown={down} onPointerUp={up} onPointerCancel={() => { swipe.current = null; }}>
      <h3 ref={title} className={styles.title} tabIndex={-1}>{question.title}</h3>
      {question.why && <p className={styles.reason}>{question.why}</p>}
      <div className={styles.choices}>
        {question.options.map((option) => {
          const on = picked === option.id;
          return <button key={option.id} type="button" className={styles.choice} aria-pressed={on} data-selected={on || undefined} disabled={busy} onClick={() => flow.choose(option.id)}>
            {on && <Check size={16} strokeWidth={1.8} aria-hidden="true" />}{option.label}</button>;
        })}
      </div>
      {question.allowCustom && <CustomAnswer key={`${question.id}:${answerOf(question, flow.answers) ?? ""}`}
        questionId={question.id} answer={picked ?? null} maxLength={question.customMaxLength ?? 1000} busy={busy}
        onSave={(value) => flow.choose(`custom:${value}`)} />}
      <div className={styles.saved} role="status" aria-live="polite">{note}</div>
      {failed?.id === question.id && <div className={styles.error} role="alert">
        <span>{t("답을 저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요.", "We could not save your answer. Check the connection and try again.")}</span>
        <button type="button" onClick={flow.retry} disabled={busy}>{t("다시 시도하기", "Try again")}</button>
      </div>}
      {answerOf(question, flow.answers) && <button type="button" className={styles.textButton} onClick={() => flow.choose(null)} disabled={busy}>{t("답변 취소하고 다시 입력", "Clear answer and enter again")}</button>}
    </div>
    <div className={styles.dots} aria-hidden="true">{questions.map((entry, index) => <span key={entry.id} data-on={index === at || undefined} />)}</div>
    <p className={styles.hint}>{t("좌우로 밀면 이전 · 다음 질문을 볼 수 있어요", "Swipe left or right to see the previous or next question")}</p>
  </section>;
}

function CustomAnswer({ questionId, answer, maxLength, busy, onSave }: {
  questionId: string; answer: string | null; maxLength: number; busy: boolean; onSave: (value: string) => void;
}) {
  const t = useT();
  const [draft, setDraft] = useState(answer?.startsWith("custom:") ? answer.slice(7) : "");
  const [problem, setProblem] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (!draft.trim()) { setProblem(t("원하는 답을 적어 주세요.", "Write your answer.")); input.current?.focus(); return; }
    onSave(draft.trim());
  };
  return <form className={styles.customAnswer} onSubmit={submit}>
    <label htmlFor={`survey-custom-${questionId}`}>{t("직접 입력", "Your own answer")}</label>
    <div><input ref={input} id={`survey-custom-${questionId}`} value={draft} maxLength={maxLength}
      placeholder={questionId === "preferred_mobility" ? t("예: 택시 + 버스", "e.g. taxi + bus") : t("원하는 답을 적어 주세요", "Write your preference")}
      aria-invalid={Boolean(problem)} aria-describedby={problem ? `survey-custom-${questionId}-error` : undefined}
      onBlur={() => { if (draft.length > 0 && !draft.trim()) setProblem(t("원하는 답을 적어 주세요.", "Write your answer.")); }}
      onFocus={() => setProblem("")} onChange={(event) => { setDraft(event.target.value); setProblem(""); }} />
      <button type="submit" aria-busy={busy}>{busy ? t("저장 중…", "Saving…") : t("답변 저장", "Save answer")}</button></div>
    {problem && <p id={`survey-custom-${questionId}-error`} role="alert">{problem}</p>}
  </form>;
}

/** The line under the card once nothing is open (mockup `pagerStatus`): what happens next. */
export function PagerStatus({ flow }: { flow: QuestionFlow }) {
  const t = useT();
  if (flow.open.length > 0) return null;
  if (flow.phase === "read") {
    return <p className={styles.status}>{flow.allDone ? t("질문에 모두 답했어요. 계획을 다 읽으면 계획 확인 화면으로 넘어가요.", "You have answered everything. The plan check opens when the plan is read.")
      : t("이번 질문은 여기까지예요. 아직 계획을 읽는 중이에요.", "That is all the questions for now. The plan is still being read.")}</p>;
  }
  if (flow.phase === "late" && flow.allDone) return <p className={styles.status}>{t("질문에 모두 답했어요. 아래 단추를 누르면 계획 확인 화면으로 가요.", "You have answered everything. Press the button below to open the plan check.")}</p>;
  return null;
}
