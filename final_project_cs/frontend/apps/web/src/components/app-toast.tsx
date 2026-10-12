"use client";

import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { clearPendingToast, pushToast, takePendingToast, type BusToast } from "@/lib/toast-bus";
import { ToastView, useToastState } from "./toast-view";

/**
 * `[2026-10-06 사용자 지시]` 알림: the plan check shows a notice in its own screen where it is up (it listens on `lib/toast-bus.ts`), else here - both with the SAME bar (`toast-view.tsx`), in the phone frame when the
 * screen is inside one. Returns `show` and the element to put in the tree.
 */
export function useAppToast(): { show: (toast: BusToast) => void; node: ReactNode } {
  const { shown, show: showHere, hide } = useToastState();
  const local = useRef<BusToast | null>(null);
  useEffect(() => {
    const held = takePendingToast();
    if (held) { local.current = held; showHere(held); }
  }, [showHere]);
  const show = useCallback((next: BusToast) => {
    if (!pushToast(next)) { local.current = next; showHere(next); }
  }, [showHere]);
  const dismiss = useCallback(() => {
    if (local.current) clearPendingToast(local.current);
    local.current = null;
    hide();
  }, [hide]);
  const node = shown ? <ToastView key={shown.stamp} toast={shown.toast} onDone={dismiss} /> : null;
  return { show, node };
}
