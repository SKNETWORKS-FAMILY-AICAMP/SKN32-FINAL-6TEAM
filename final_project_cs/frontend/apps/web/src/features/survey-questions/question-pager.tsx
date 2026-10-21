"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import { OnboardingIcon } from "@/features/onboarding/icons";
import startCard from "@/features/onboarding/onboarding.module.css";
import { useT } from "@/lib/settings";
import { answerOf, complete, draftOf, EMPTY_DRAFT, payloadOf, type Draft, type SurveyQuestion } from "./model";
import { QuestionCard } from "./question-card";
import type { QuestionFlow } from "./use-question-flow";
import styles from "./survey-questions.module.css";

/** Slide: at least this many px sideways and clearly more sideways than down (mockup v9). */
const SWIPE_PX = 50;
const SWIPE_DOMINANCE = 1.5;

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계 · 목업 v9 `questionCard`]` The questions asked while the server reads: one card, ‹ › buttons with `i / N`, swipe or the arrow keys to move,
 * dots, and the line under it. What is asked and what the options say is the server's (`questions[]`).
 * `[2026-10-20 ST4F-665]` Inside, the start survey's card (`question-card.tsx`): its chips, travelers row, area cards and dining / activities rows, under its rules, and its 「다음」 —
 * on only when the card is complete; pressing it saves the question and goes on. An answered question can be changed and sent again, or taken back.
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
      <div className={startCard.question}>
        <h3 ref={title} className={styles.title} tabIndex={-1}>{question.title}</h3>
        {question.why && <p className={startCard.helper}>{question.why}</p>}
        <Answering key={question.id} flow={flow} question={question} />
      </div>
      <div className={styles.saved} role="status" aria-live="polite">{note}</div>
      {failed?.id === question.id && <div className={styles.error} role="alert">
        <span>{t("답을 저장하지 못했어요. 연결을 확인하고 다시 시도해 주세요.", "We could not save your answer. Check the connection and try again.")}</span>
        <button type="button" onClick={flow.retry} disabled={busy}>{t("다시 시도하기", "Try again")}</button>
      </div>}
    </div>
    <div className={styles.dots} aria-hidden="true">{questions.map((entry, index) => <span key={entry.id} data-on={index === at || undefined} />)}</div>
    <p className={styles.hint}>{t("좌우로 밀면 이전 · 다음 질문을 볼 수 있어요", "Swipe left or right to see the previous or next question")}</p>
  </section>;
}

/**
 * The card being answered and its buttons. Its state starts from what was last left on it (a size picked stays), else from the answer held; 「다음」 sends it when complete
 * (「답변 저장」 when no other question is open), and 「답변 취소하고 다시 입력」 takes a held answer back.
 */
function Answering({ flow, question }: { flow: QuestionFlow; question: SurveyQuestion }) {
  const t = useT();
  const [draft, setDraft] = useState<Draft>(() => flow.drafts[question.id] ?? draftOf(question, answerOf(question, flow.answers)));
  const ready = complete(question, draft);
  const held = Boolean(answerOf(question, flow.answers));
  const last = flow.open.every((index) => flow.questions[index]?.id === question.id);
  const send = () => {
    if (!ready || flow.busy) return;
    const { answers, value } = payloadOf(question, draft);
    flow.commit(answers, value, draft);
  };
  return <>
    <div>
      <QuestionCard question={question} draft={draft} setDraft={setDraft} />
    </div>
    <div className={startCard.questionNav}>
      <button type="button" className={startCard.next} disabled={!ready || flow.busy} aria-busy={flow.busy} onClick={send}>
        {last ? t("답변 저장", "Save answer") : t("다음", "Next")}<OnboardingIcon name="arrow" size={15} />
      </button>
    </div>
    {held && <button type="button" className={styles.textButton} onClick={() => { setDraft(EMPTY_DRAFT); flow.clear(); }} disabled={flow.busy}>
      {t("답변 취소하고 다시 입력", "Clear answer and enter again")}</button>}
  </>;
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
