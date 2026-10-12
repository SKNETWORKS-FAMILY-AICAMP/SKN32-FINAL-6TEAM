"use client";

import { Check } from "lucide-react";
import { useT } from "@/lib/settings";
import { PagerStatus, QuestionPager } from "./question-pager";
import type { QuestionFlow } from "./use-question-flow";
import styles from "./survey-questions.module.css";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 2단계 · 목업 v9 `loadingBody`]` What stands under the reading screen's heading while questions are asked: the line that says why (while the server reads) or that the
 * plan has been read (once it has and the screen is held for the questions), the question card, and what happens next. The whole is shown only while `flow.shown`.
 */
export function ReadingQuestions({ flow }: { flow: QuestionFlow }) {
  const t = useT();
  const reading = flow.phase === "read";
  return <>
    {reading
      ? <p className={styles.notice}>{t("기다리는 동안 하나씩 여쭤볼게요. 원하는 답을 직접 적어도 좋아요.", "While you wait, choose an answer or write your own.")}</p>
      : <p className={styles.successLine}><Check size={16} strokeWidth={1.8} aria-hidden="true" />{t("계획을 다 읽었어요", "We have read your plan")}</p>}
    {flow.stopAuto && !reading && <p className={styles.notice}>{t("이제 자동으로 넘어가지 않아요.", "It will not go on by itself now.")}</p>}
    <QuestionPager flow={flow} />
    <PagerStatus flow={flow} />
  </>;
}
