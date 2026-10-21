import { useEffect, useRef } from "react";
import { onToast, pushToast, type BusToast } from "@/lib/toast-bus";
import type { Translate } from "@/lib/i18n";

/** 읽기 판의 안내를 결과 판의 소유자에게 넘긴다. */
export function useReadingToastHandoff(reading: boolean, notice: { toast: BusToast } | null, hide: () => void) {
  const active = useRef({ reading, notice, since: 0 });
  useEffect(() => {
    active.current = { reading, notice, since: active.current.notice === notice && active.current.since > 0 ? active.current.since : Date.now() };
  }, [reading, notice]);
  // The starting route is replaced by a different PlanCheck instance. Its reading
  // owner has already unsubscribed when this cleanup runs; the next owner takes
  // the pending notice, with the original expiry and Undo callback intact.
  useEffect(() => () => {
    const held = active.current;
    if (!held.reading || !held.notice) return;
    const toast = held.notice.toast;
    // A completed request must not carry its obsolete sending/progress text.
    if (!toast.action && !toast.stay) return;
    const remaining = (toast.ms ?? (toast.action ? 4_500 : 2_800)) - (Date.now() - held.since);
    if (toast.stay || remaining > 0) pushToast({ ...toast, ...(toast.stay ? {} : { ms: remaining }) });
  }, []);
  useEffect(() => {
    if (!reading && notice) { pushToast(notice.toast); hide(); }
  }, [reading, notice, hide]);
}

/**
 * A header action takes priority over the delayed first completed-plan introduction. `intro` replaces the plan check's own words (`[2026-10-13]` the edit of a registered trip says what it is).
 */
export function usePlanIntroToast(done: boolean, show: (toast: BusToast) => void, t: Translate, intro?: BusToast,
  /** `[2026-10-20 C안]` The 5-second 「여행 등록」 bar says what happens instead: no introduction then. */
  skip = false) {
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
    if (received.current || skip) return;
    show(intro ?? { text: t("계획 확인 화면이에요", "Check your plan"), sub: t("일정을 수정하거나 권장 수정안을 확인해 주세요.", "Edit stops or view the proposed plan."), ms: 3_500 });
  }, [done, show, t, intro, skip]);
}
