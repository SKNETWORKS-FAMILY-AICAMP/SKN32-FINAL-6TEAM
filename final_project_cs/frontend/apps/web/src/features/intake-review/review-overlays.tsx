"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import { useT } from "@/lib/settings";
import { ActionButton } from "./action-button";
import { cx } from "./cx";
import styles from "./review-overlays.module.css";

export interface ToastState { id: number; message: string; sub?: string; /** Present when the action can be taken back. */ undo?: () => void }

/**
 * The small message at the bottom after something was done. It is a status line (read out politely), disappears by itself,
 * and carries 「되돌리기」 when the action can be taken back. The caller keeps the timer (it knows how long is long enough).
 */
export function ReviewToast({ toast, onUndo }: { toast: ToastState | null; onUndo: () => void }) {
  const t = useT();
  return <div className={cx(styles.toast, toast && styles.show)} role="status" aria-live="polite">
    {toast && <>
      <span className={styles.text}>{toast.message}{toast.sub && <small>{toast.sub}</small>}</span>
      {toast.undo && <button type="button" className={styles.undo} onClick={onUndo}>{t("되돌리기", "Undo")}</button>}
    </>}
  </div>;
}

/**
 * The question before something that is hard to take back. Focus starts on 「취소」; Escape, a press outside the box and
 * 「취소」 all mean no; Tab stays between the two buttons. (mockup `.alert`)
 */
export function ConfirmDialog({ title, detail, confirmLabel, cancelLabel, onConfirm, onCancel }: {
  title: string; detail?: string; confirmLabel: string; cancelLabel: string; onConfirm: () => void; onCancel: () => void;
}) {
  const cancel = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { cancel.current?.focus({ preventScroll: true }); }, []);

  function keys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onCancel(); return; }
    if (event.key !== "Tab" || !box.current) return;
    const buttons = [...box.current.querySelectorAll<HTMLButtonElement>("button")];
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    event.preventDefault();
    buttons[(at + (event.shiftKey ? buttons.length - 1 : 1)) % buttons.length]?.focus();
  }

  return <div className={styles.alert} onClick={(event) => { if (event.target === event.currentTarget) onCancel(); }} onKeyDown={keys}>
    <div ref={box} className={styles.box} role="alertdialog" aria-modal="true" aria-labelledby="review-dialog-title" aria-describedby={detail ? "review-dialog-detail" : undefined}>
      <p className={styles.title} id="review-dialog-title">{title}</p>
      {detail && <p className={styles.detail} id="review-dialog-detail"><b>{detail}</b></p>}
      <div className={styles.buttons}>
        <ActionButton ref={cancel} onClick={onCancel}>{cancelLabel}</ActionButton>
        <ActionButton variant="danger" onClick={onConfirm}>{confirmLabel}</ActionButton>
      </div>
    </div>
  </div>;
}
