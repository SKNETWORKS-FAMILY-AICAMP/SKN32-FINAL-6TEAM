"use client";

import { useEffect, useRef } from "react";
import { useT } from "@/lib/settings";
import { legLines } from "./place-change";
import { Act, kindLabel } from "./parts";
import type { StopAsk, StopOption } from "./stop-questions";
import styles from "./stop-question.module.css";

/**
 * ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` The question inside the card the first check stopped at (flow mockup `mockups/tripilot-plan-flow-register.html` 4단계): what kind of
 * check it is, the question, the options (each with 「이유:」, the way in and out for a place, 「고르면:」) and 「직접 수정」 (the stop's own change screen). No 「삭제」 —
 * adding and taking out stops is for the edit after registering (2026-10-20). `leaving` folds it away (the pick was made; the card is checked again where it stands).
 */
export function StopQuestion({ id, ask, loading, failed, again, leaving, why, explain, onPick, onEdit }: {
  id: string;
  ask: StopAsk;
  /** The alternatives are still coming (the question is there already). */
  loading: boolean;
  /** Why they could not be read, said as the server said it. */
  failed: string | null;
  /** The card still needs a look after a pick: asked again. */
  again: boolean;
  leaving: boolean;
  /** Why nothing here can act now — null when it can. */
  why: string | null;
  explain: (why: string) => void;
  onPick: (option: StopOption) => void;
  onEdit: () => void;
}) {
  const t = useT();
  const titleId = `plan-stop-question-${id}`;
  const box = useRef<HTMLElement>(null);
  // The question takes the focus once (not the scroll: the list keeps the card where it stands).
  useEffect(() => { box.current?.focus({ preventScroll: true }); }, [id, again]);
  return <section ref={box} tabIndex={-1} className={styles.box} aria-labelledby={titleId} data-stop-question={id} data-leaving={leaving || undefined} data-details>
    <span className={styles.kind}>{kindLabel("place", t)}</span>
    {again && <p className={styles.again}>{t("고른 뒤에도 확인이 필요해요 · 다시 골라 주세요", "It still needs a look after the pick · please choose again")}</p>}
    <p id={titleId} className={styles.question}>{ask.question}</p>
    {loading && <p className={styles.note} role="status">{t("후보를 찾는 중…", "Finding candidates…")}</p>}
    {failed && <p className={styles.note} role="alert">{failed}</p>}
    {ask.options.length > 0 && <div className={styles.options}>{ask.options.map((option) =>
      <Act key={option.key} className={styles.option} why={why} explain={explain} onPress={() => onPick(option)}>
        <span className={styles.optionTop}>{option.label}</span>
        {option.reason && <span className={styles.line}>{t("이유:", "Why:")} {option.reason}</span>}
        {option.act.type === "pick" && legLines(option.act.candidate, t).map((line) =>
          <span key={line.side} className={styles.line} data-leg data-pending={line.pending || undefined}>{line.text}</span>)}
        <span className={styles.line}>{t("고르면:", "If picked:")} {option.effect}</span>
      </Act>)}</div>}
    <div className={styles.buttons}>
      <Act className={styles.button} why={why} explain={explain} onPress={onEdit}>{t("직접 수정", "Edit myself")}</Act>
    </div>
  </section>;
}
