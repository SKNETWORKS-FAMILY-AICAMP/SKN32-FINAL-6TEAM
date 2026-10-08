"use client";

import { Hourglass, X } from "lucide-react";
import { useT } from "@/lib/settings";
import styles from "./wait-notice.module.css";

/**
 * `[2026-10-06 사용자 지적 — 서버가 1분 넘게 답이 없는데 아무 알림이 없다]` The notice that says the server is slow: a title, a line of what is going on, and how long it has been. Used floating at the top of
 * the page (`ServerWaitBanner`, any call that has not answered) and inline on a screen that waits for the server's own progress (the plan reading).
 * The seconds are drawn but not read out (`aria-hidden`), so a screen reader hears the notice once - when its level changes - and not every second.
 */
export function WaitNotice({ title, body, seconds, floating = false, onClose }: { title: string; body: string; seconds?: number; floating?: boolean; onClose?: () => void }) {
  const t = useT();
  return <div className={styles.notice} data-floating={floating || undefined} role="status" aria-live="polite">
    <Hourglass className={styles.icon} size={20} strokeWidth={1.8} aria-hidden="true" />
    <div className={styles.text}>
      <strong>{title}</strong>
      <p>{body}{seconds !== undefined && <span className={styles.timer} aria-hidden="true"> · {formatWait(seconds, t)}</span>}</p>
    </div>
    {onClose && <button type="button" className={styles.close} onClick={onClose} aria-label={t("닫기", "Close")}><X size={18} strokeWidth={1.8} aria-hidden="true" /></button>}
  </div>;
}

/** 「45초째」 · 「1분 5초째」. */
export function formatWait(seconds: number, t: ReturnType<typeof useT>): string {
  const minutes = Math.floor(seconds / 60), rest = seconds % 60;
  return minutes > 0 ? t(`${minutes}분 ${rest}초째`, `${minutes} min ${rest} s`) : t(`${rest}초째`, `${rest} s`);
}
