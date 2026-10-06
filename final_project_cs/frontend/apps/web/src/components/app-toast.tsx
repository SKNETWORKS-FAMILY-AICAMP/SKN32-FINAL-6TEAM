"use client";

import { useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useT } from "@/lib/settings";
import { pushToast, type BusToast } from "@/lib/toast-bus";
import { OverlayRoot } from "./layout/overlay-root";
import styles from "./app-toast.module.css";

/** How long a notice stays: longer when it has a button to press. The same times as the plan check's own notices. */
const WITH_ACTION_MS = 4_500;
const PLAIN_MS = 2_800;

/**
 * `[2026-10-06 사용자 지시]` 알림: the plan check's notice bar where that screen is up, else this one - the same dark bar, in the phone frame when the screen is inside one (`OverlayRoot`), at the top of the page otherwise,
 * gone by itself after a few seconds. Returns `show` and the element to put in the tree.
 */
export function useAppToast(): { show: (toast: BusToast) => void; node: ReactNode } {
  const t = useT();
  const root = useContext(OverlayRoot);
  const [toast, setToast] = useState<BusToast | null>(null);
  const show = useCallback((next: BusToast) => { if (!pushToast(next)) setToast(next); }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), toast.action ? WITH_ACTION_MS : PLAIN_MS);
    return () => clearTimeout(timer);
  }, [toast]);
  const node = toast && typeof document !== "undefined" ? createPortal(
    <div className={styles.toast} data-in-frame={root ? true : undefined} role="status">
      <span className={styles.text}>{toast.text}{toast.sub && <small>{toast.sub}</small>}</span>
      {toast.action && <button type="button" className={styles.action} onClick={() => { const run = toast.action?.run; setToast(null); run?.(); }}>{toast.action.label}</button>}
      <button type="button" className={styles.close} onClick={() => setToast(null)} aria-label={t("닫기", "Close")}>×</button>
    </div>, root ?? document.body) : null;
  return { show, node };
}
