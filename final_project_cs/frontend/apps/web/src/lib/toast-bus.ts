/**
 * `[2026-10-06 사용자 지시]` 「기존 알림창과 같은 모양으로, 시간이 지나면 사라지게」 · 「알림은 하나의 포맷으로」: one small notice (the white card of `components/toast-view.tsx`) for what the customer just did - the Course Keeper turned on or off.
 * The plan check already owns that bar on its map screen (`plan-check.tsx`), so it LISTENS here and shows the notice in it; where no screen listens (the reading screen, the registration page, a trip), `pushToast`
 * says so (`false`) and the caller shows the same bar itself (`components/app-toast.tsx`).
 */
export type ToastTone = "ok" | "warn" | "changed";

export interface BusToast {
  /** The title line. */
  text: string;
  /** Lines under the title (line breaks kept): where, when, how. */
  sub?: string;
  /** What deserves a look, in the warning colour under the lines (the first thing a check found that is not fine). */
  note?: string;
  /** A small mark before the title (a pin's number, 「→」 for a route): what the notice is about. */
  badge?: string;
  /** A small tinted word after the title (「확인 필요」 · 「통과」 · 「바뀜」); its tone also colours the stripe at the card's edge. */
  chip?: { text: string; tone: ToastTone };
  /** A button on the notice (「되돌리기」 · 「다시 시도하기」): it runs, and the notice goes. */
  action?: { label: string; run: () => void };
  /** How long it stays when the default (2.8 s, 4.5 s with a button) is too short: a notice with more to read (a pin's description). */
  ms?: number;
  /**
   * `[2026-10-07 사용자 결정 — 오류 알림은 남기고 밀어서 닫기]` Something went wrong: the notice does not go by itself (the customer may not have seen it) - it goes with ✕ or a swipe sideways,
   * and its stripe is the error colour.
   */
  stay?: boolean;
}

type Listener = (toast: BusToast) => void;
const listeners = new Set<Listener>();
let pending: { toast: BusToast; expiresAt: number } | null = null;

/** Carry a locally displayed notice across the starting page's route replacement. */
export function takePendingToast(): BusToast | null {
  const held = pending;
  pending = null;
  if (!held) return null;
  const remaining = held.expiresAt - Date.now();
  return remaining > 0 ? { ...held.toast, ...(held.toast.stay ? {} : { ms: remaining }) } : null;
}

/** A dismissed local notice must not reappear on the next page. */
export function clearPendingToast(toast: BusToast): void {
  if (pending?.toast === toast) pending = null;
}

/** A screen that shows notices in its own bar. Returns the way to stop listening. */
export function onToast(listener: Listener): () => void {
  listeners.add(listener);
  const held = takePendingToast();
  if (held) listener(held);
  return () => { listeners.delete(listener); };
}

/** Hand the notice to the screen that listens; `false` when none does. */
export function pushToast(toast: BusToast): boolean {
  if (listeners.size === 0) {
    pending = { toast, expiresAt: toast.stay ? Number.POSITIVE_INFINITY : Date.now() + (toast.ms ?? (toast.action ? 4_500 : 2_800)) };
    return false;
  }
  pending = null;
  listeners.forEach((listener) => listener(toast));
  return true;
}
