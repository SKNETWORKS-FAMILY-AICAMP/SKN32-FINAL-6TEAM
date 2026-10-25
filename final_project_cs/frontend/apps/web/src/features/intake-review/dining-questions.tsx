"use client";

import { useState } from "react";
import type { DiningAnswer, DiningQuestion, ReviewedIntakeView } from "@/lib/live/intake-review";
import { useT } from "@/lib/settings";
import styles from "./dining-questions.module.css";

export function diningAnswer(revision: number, runId: string, question: DiningQuestion, selected: string[], excluded: boolean): DiningAnswer {
  const known = new Set(question.choices.map((choice) => choice.item_id));
  if (selected.some((id) => !known.has(id)) || (excluded ? selected.length > 0 : selected.length === 0)) {
    throw new Error("적용할 식사를 선택하거나 조건 취소를 골라 주세요.");
  }
  return { revision, run_id: runId, question_id: question.id, item_ids: [...new Set(selected)], excluded };
}

export function canApplyDiningAnswer(current: ReviewedIntakeView | undefined, next: ReviewedIntakeView, sent: DiningAnswer): boolean {
  return current?.status === "review" && next.status === "review" && current.intake_id === next.intake_id
    && !current.preview && !next.preview && current.revision === sent.revision && next.revision === sent.revision
    && current.review?.dining_judge?.run_id === sent.run_id;
}

interface Props {
  questions: DiningQuestion[];
  busy: boolean;
  status: string | null;
  error?: string | null;
  onAnswer: (question: DiningQuestion, selected: string[], excluded: boolean) => Promise<void>;
}

function Question({ question, busy, onAnswer }: Pick<Props, "busy" | "onAnswer"> & { question: DiningQuestion }) {
  const t = useT();
  const [selected, setSelected] = useState(question.answer?.item_ids ?? []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (excluded: boolean) => {
    setSaving(true); setError(null);
    try { await onAnswer(question, excluded ? [] : selected, excluded); }
    catch (cause) { setError(cause instanceof Error ? cause.message : t("답변을 저장하지 못했어요.", "Could not save your answer.")); }
    finally { setSaving(false); }
  };
  return <form className={styles.question} onSubmit={(event) => { event.preventDefault(); void submit(false); }}>
    <blockquote className={styles.quote}>{question.quote}</blockquote>
    <fieldset disabled={busy || saving}>
      <legend>{t("어느 식사에 적용할까요? 여러 개를 골라도 돼요.", "Which meals does this apply to? You can choose several.")}</legend>
      {question.choices.map((choice) => <label className={styles.choice} key={choice.item_id}>
        <input type="checkbox" value={choice.item_id} checked={selected.includes(choice.item_id)}
          onChange={(event) => setSelected((previous) => event.target.checked ? [...previous, choice.item_id] : previous.filter((id) => id !== choice.item_id))} />
        <span>{[choice.date, choice.starts_at, choice.title].filter(Boolean).join(" · ")}</span>
      </label>)}
      {question.answer && <p className={styles.saved}>{question.answer.excluded
        ? t("이 조건을 취소했어요. 다시 적용하려면 식사를 골라 주세요.", "This condition was cancelled. Select meals to apply it again.")
        : t("선택한 식사에 적용했어요. 선택을 바꿔 다시 저장할 수 있어요.", "Applied to your selected meals. You can change and save it again.")}</p>}
      <div className={styles.actions}>
        <button type="submit" disabled={!selected.length}>{t("선택한 식사에 적용", "Apply to selected meals")}</button>
        <button type="button" onClick={() => void submit(true)}>{t("이 조건 취소", "Cancel this condition")}</button>
      </div>
    </fieldset>
    {error && <p role="alert">{error}</p>}
  </form>;
}

export function DiningQuestions({ questions, busy, onAnswer, status, error }: Props) {
  const t = useT();
  if (!questions.length && !status && !error) return null;
  return <section className={styles.panel} aria-label={t("식사 조건 확인", "Meal conditions")}>
    {questions.length > 0 && <h2>{t("식사 조건을 조금 더 알려 주세요", "Tell us which meals these conditions apply to")}</h2>}
    {status && <p role="status">{status}</p>}
    {error && <p role="alert">{error}</p>}
    {questions.map((question) => <Question key={question.id} question={question} busy={busy} onAnswer={onAnswer} />)}
  </section>;
}
