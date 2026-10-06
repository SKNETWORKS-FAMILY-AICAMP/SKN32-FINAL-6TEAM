"use client";

import { X } from "lucide-react";
import { useT } from "@/lib/settings";
import styles from "./undo-toast.module.css";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 · 목업 v9 §3-4]` The line under the header after the Course Keeper icon was pressed. ★It does NOT go away by itself: reading it and reaching the button
 * must not be hurried (it stays until it is closed, undone, or the screen is left). `failed` is the version for a change the server did not take: the state stays as it was, and 「다시 시도하기」 is there.
 */
export function UndoToast({ kind = "off", failed = false, onUndo, onRetry, onClose }: { kind?: "off" | "on"; failed?: boolean; onUndo?: () => void; onRetry?: () => void; onClose: () => void }) {
  const t = useT();
  return <div className={styles.toast} data-failed={failed || undefined} role={failed ? "alert" : "status"}>
    <span className={styles.text}>{failed
      ? t("항로 지킴이를 바꾸지 못했어요. 연결을 확인하고 다시 시도해 주세요.", "Course Keeper could not be changed. Check the connection and try again.")
      : kind === "on" ? t("항로 지킴이를 켰어요.", "Course Keeper is on.")
        : t("항로 지킴이를 껐어요. 문제가 생기면 물어볼게요.", "Course Keeper is off. We will ask you when something goes wrong.")}</span>
    {failed
      ? onRetry && <button type="button" className={styles.action} onClick={onRetry}>{t("다시 시도하기", "Try again")}</button>
      : onUndo && <button type="button" className={styles.action} onClick={onUndo}>{t("되돌리기", "Undo")}</button>}
    <button type="button" className={styles.close} onClick={onClose} aria-label={t("닫기", "Close")}><X size={20} strokeWidth={1.8} aria-hidden="true" /></button>
  </div>;
}
