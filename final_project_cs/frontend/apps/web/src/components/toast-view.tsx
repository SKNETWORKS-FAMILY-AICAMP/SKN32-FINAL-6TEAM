"use client";

import { useCallback, useContext, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useT } from "@/lib/settings";
import type { BusToast } from "@/lib/toast-bus";
import { OverlayRoot } from "./layout/overlay-root";
import styles from "./toast-view.module.css";

/** How long a notice stays: longer when it has a button to press. */
const WITH_ACTION_MS = 4_500;
const PLAIN_MS = 2_800;
/** The fade-out before it goes (the same length as `toastOut` in the CSS). */
const LEAVE_MS = 180;

let stamps = 0;

/**
 * `[2026-10-06 사용자 지시 — 알림은 하나의 포맷으로 · 하얀 카드, 강조는 다른 것으로]` ONE notice, for every screen: a white card under the header (a small badge, a title with a tinted chip, lines of detail, what to look at in the
 * warning colour, a pill button when there is something to press, ✕), the same place and size everywhere, gone by itself after a few seconds. White blends into the sheet and the chips, so it is picked out by other
 * means: a stripe of its tone at the edge, a light that runs once around its border when it arrives, and a soft ring that spreads once. The plan check's own notices, what the customer did in the header (the
 * Course Keeper on or off) and what a pin or a route line on the map says are all shown by this one component - nobody draws a notice of their own.
 */
export interface ShownToast { stamp: number; toast: BusToast }

/** The notice on show (or none), the way to show a new one (it replaces the one on show) and the way to let it go. */
export function useToastState(): { shown: ShownToast | null; show: (toast: BusToast) => void; hide: () => void } {
  const [shown, setShown] = useState<ShownToast | null>(null);
  const show = useCallback((toast: BusToast) => { stamps += 1; setShown({ stamp: stamps, toast }); }, []);
  const hide = useCallback(() => setShown(null), []);
  return { shown, show, hide };
}

/** The card itself. Put it in the tree with `key={shown.stamp}` so a new notice starts its own few seconds. */
export function ToastView({ toast, onDone }: { toast: BusToast; onDone: () => void }) {
  const t = useT();
  const root = useContext(OverlayRoot);
  const [leaving, setLeaving] = useState(false);
  const [paused, setPaused] = useState(false);
  // A notice stays while the customer is reading it (the pointer on its button or the focus in it), then goes after its few seconds.
  useEffect(() => {
    if (paused) return;
    const timer = setTimeout(() => setLeaving(true), toast.ms ?? (toast.action ? WITH_ACTION_MS : PLAIN_MS));
    return () => clearTimeout(timer);
  }, [toast, paused]);
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(onDone, LEAVE_MS);
    return () => clearTimeout(timer);
  }, [leaving, onDone]);
  if (typeof document === "undefined") return null;
  const stacked = Boolean(toast.sub || toast.note);
  return createPortal(
    <div className={styles.toast} role="status" data-tone={toast.chip?.tone} data-badge={toast.badge ? true : undefined} data-stacked={stacked || undefined}
      data-in-frame={root ? true : undefined} data-leaving={leaving || undefined}
      onPointerEnter={() => setPaused(true)} onPointerLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
      {toast.badge && <span className={styles.badge} data-route={toast.badge === "→" || undefined} aria-hidden="true">{toast.badge}</span>}
      <div className={styles.body}>
        <strong className={styles.title}>{toast.text}{toast.chip && <em data-tone={toast.chip.tone}>{toast.chip.text}</em>}</strong>
        {toast.sub && <span className={styles.sub}>{toast.sub}</span>}
        {toast.note && <span className={styles.note}>{toast.note}</span>}
      </div>
      {toast.action && <button type="button" className={styles.action} onClick={() => { const run = toast.action?.run; onDone(); run?.(); }}>{toast.action.label}</button>}
      <button type="button" className={styles.close} onClick={onDone} aria-label={t("닫기", "Close")}><X size={18} strokeWidth={1.8} aria-hidden="true" /></button>
    </div>, root ?? document.body);
}
