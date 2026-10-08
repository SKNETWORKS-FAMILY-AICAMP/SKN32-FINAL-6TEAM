"use client";

import { useCallback, type ReactNode } from "react";
import { pushToast, type BusToast } from "@/lib/toast-bus";
import { ToastView, useToastState } from "./toast-view";

/**
 * `[2026-10-06 사용자 지시]` 알림: the plan check shows a notice in its own screen where it is up (it listens on `lib/toast-bus.ts`), else here - both with the SAME bar (`toast-view.tsx`), in the phone frame when the
 * screen is inside one. Returns `show` and the element to put in the tree.
 */
export function useAppToast(): { show: (toast: BusToast) => void; node: ReactNode } {
  const { shown, show: showHere, hide } = useToastState();
  const show = useCallback((next: BusToast) => { if (!pushToast(next)) showHere(next); }, [showHere]);
  const node = shown ? <ToastView key={shown.stamp} toast={shown.toast} onDone={hide} /> : null;
  return { show, node };
}
