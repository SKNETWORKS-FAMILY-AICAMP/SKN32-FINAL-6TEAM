"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui";
import dialogStyles from "@/features/trip/trip-list.module.css";
import { useT } from "@/lib/settings";
import { legLines } from "./place-change";
import { Act, kindLabel } from "./parts";
import type { StopAsk, StopOption } from "./stop-questions";
import styles from "./stop-question.module.css";

/**
 * ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` The question inside the card the first check stopped at (flow mockup `mockups/tripilot-plan-flow-register.html` 4단계): what kind of
 * check it is, the question, the options (each with 「이유:」, the way in and out for a place, 「고르면:」), 「직접 수정」 (the stop's own change screen) and, for a place, 「삭제」
 * (`[2026-10-20 사용자 재결정]` back in the question, asked once in a dialog — `StopDeleteDialog`). `leaving` folds it away (the pick was made; the card is checked again where it stands).
 */
export function StopQuestion({ id, kind, ask, loading, failed, again, leaving, why, explain, onPick, onEdit, onDelete, takeFocus = true }: {
  id: string;
  /**
   * What the card stopped for: its place (or what else needs a look), or the way into it arriving late (`[2026-10-20 이동 확인 C안]`).
   * `[2026-10-21 P6]` `interpretation`: what a line of the plan means — no card; its last button is 「직접 선택」 (put the stop in and pick its place).
   */
  kind: "place" | "arrival" | "interpretation";
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
  /** Take the stop out (asked first); none for a late arrival (the way in is fixed, not the stop). */
  onDelete?: () => void;
  /** `[2026-10-21]` The check stopped here: the question takes the focus. Not on the result screen's cards (nothing stopped there — the focus stays where the customer is). */
  takeFocus?: boolean;
}) {
  const t = useT();
  const titleId = `plan-stop-question-${id}`;
  const box = useRef<HTMLElement>(null);
  // The question takes the focus once (not the scroll: the list keeps the card where it stands).
  useEffect(() => { if (takeFocus) box.current?.focus({ preventScroll: true }); }, [id, again, takeFocus]);
  return <section ref={box} tabIndex={-1} className={styles.box} aria-labelledby={titleId} data-stop-question={id} data-leaving={leaving || undefined} data-details>
    <span className={styles.kind}>{kind === "interpretation" ? t("읽은 뜻", "Reading") : kindLabel(kind, t)}</span>
    {again && <p className={styles.again}>{t("고른 뒤에도 확인이 필요해요 · 다시 골라 주세요", "It still needs a look after the pick · please choose again")}</p>}
    <p id={titleId} className={styles.question}>{ask.question}</p>
    {loading && <p className={styles.note} role="status">{kind === "arrival" ? t("찾는 중…", "Looking…") : t("후보를 찾는 중…", "Finding candidates…")}</p>}
    {failed && <p className={styles.note} role="alert">{failed}</p>}
    {ask.options.length > 0 && <div className={styles.options}>{ask.options.map((option) =>
      <Act key={option.key} className={styles.option} why={why ?? option.why ?? null} explain={explain} onPress={() => onPick(option)}>
        <span className={styles.optionTop}>{option.label}{option.tag && <small className={styles.tag} data-basis={option.tag.basis}>{option.tag.text}</small>}{option.recommended && <small className={styles.recommended}>{t("추천", "Recommended")}</small>}</span>
        {option.reason && <span className={styles.line}>{t("이유:", "Why:")} {option.reason}</span>}
        {option.act.type === "pick" && legLines(option.act.candidate, t).map((line) =>
          <span key={line.side} className={styles.line} data-leg data-pending={line.pending || undefined}>{line.text}</span>)}
        <span className={styles.line}>{t("고르면:", "If picked:")} {option.effect}</span>
      </Act>)}</div>}
    <div className={styles.buttons} data-two={onDelete ? true : undefined}>
      <Act className={styles.button} why={why} explain={explain} onPress={onEdit}>{kind === "interpretation" ? t("직접 선택", "Choose myself") : t("직접 수정", "Edit myself")}</Act>
      {onDelete && <Act className={styles.button} data-danger why={why} explain={explain} onPress={onDelete}>{t("삭제", "Delete")}</Act>}
    </div>
  </section>;
}

/**
 * `[2026-10-20 사용자 재결정 — 질문 칸에도 삭제 · 확인 창 뒤 빼기]` Asked once before the stopped stop is taken out: it then goes at once (with its check) and the check goes on with the stop after it.
 * The app's confirm dialog (`trip-list.tsx` · `trip-edit.tsx`): focus starts on Cancel and stays inside, Escape cancels, the backdrop does nothing.
 */
export function StopDeleteDialog({ title, onCancel, onConfirm }: { title: string; onCancel: () => void; onConfirm: () => void }) {
  const t = useT();
  const cancel = useRef<HTMLButtonElement>(null);
  const remove = useRef<HTMLButtonElement>(null);
  useEffect(() => { cancel.current?.focus(); }, []);
  function keys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.preventDefault(); onCancel(); return; }
    if (event.key !== "Tab") return;
    if (event.shiftKey && document.activeElement === cancel.current) { event.preventDefault(); remove.current?.focus(); }
    else if (!event.shiftKey && document.activeElement === remove.current) { event.preventDefault(); cancel.current?.focus(); }
  }
  return createPortal(<div className={dialogStyles.overlay}>
    <div className={dialogStyles.dialog} role="alertdialog" aria-modal="true" aria-labelledby="plan-stop-delete-title" aria-describedby="plan-stop-delete-body" onKeyDown={keys}>
      <h2 id="plan-stop-delete-title">{t(`「${title}」 일정을 삭제할까요?`, `Delete “${title}”?`)}</h2>
      <p id="plan-stop-delete-body" className={dialogStyles.dialogBody}>{t("삭제하면 앞뒤 이동을 다시 확인하고 다음 일정을 이어서 확인해요.", "Once deleted, the moves around it are checked again and the check goes on with the next stop.")}</p>
      <div className={dialogStyles.dialogActions}>
        <Button ref={cancel} onClick={onCancel}>{t("취소", "Cancel")}</Button>
        <Button ref={remove} variant="danger" onClick={onConfirm}>{t("삭제", "Delete")}</Button>
      </div>
    </div>
  </div>, document.body);
}
