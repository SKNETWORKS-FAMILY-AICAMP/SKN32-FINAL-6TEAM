import { useEffect, useRef } from "react";
import { onToast, type BusToast } from "@/lib/toast-bus";
import type { Translate } from "@/lib/i18n";

/** A header action takes priority over the delayed first completed-plan introduction. */
export function usePlanIntroToast(done: boolean, show: (toast: BusToast) => void, t: Translate) {
  const introduced = useRef(false);
  const received = useRef(false);
  // Subscribe first: pending header notices may be delivered synchronously at registration.
  useEffect(() => onToast((toast) => {
    received.current = true;
    show(toast);
  }), [show]);
  useEffect(() => {
    if (!done || introduced.current) return;
    introduced.current = true;
    if (received.current) return;
    show({ text: t("계획 확인 화면이에요", "Check your plan"), sub: t("일정을 수정하거나 권장 수정안을 확인해 주세요.", "Edit stops or view the proposed plan."), ms: 3_500 });
  }, [done, show, t]);
}
