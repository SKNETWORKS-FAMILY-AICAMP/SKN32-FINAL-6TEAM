/**
 * `[2026-10-06 사용자 지시]` 「기존 알림창과 같은 모양으로, 시간이 지나면 사라지게」: one small notice (the dark bar of the plan check's own notices) for what the customer just did - the Course Keeper turned on or off.
 * The plan check already owns that bar on its map screen (`plan-check.tsx`), so it LISTENS here and shows the notice in it; where no screen listens (the reading screen, the registration page, a trip), `pushToast`
 * says so (`false`) and the caller shows the same bar itself (`components/app-toast.tsx`).
 */
export interface BusToast {
  text: string;
  sub?: string;
  /** A button on the notice (「되돌리기」 · 「다시 시도하기」): it runs, and the notice goes. */
  action?: { label: string; run: () => void };
}

type Listener = (toast: BusToast) => void;
const listeners = new Set<Listener>();

/** A screen that shows notices in its own bar. Returns the way to stop listening. */
export function onToast(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** Hand the notice to the screen that listens; `false` when none does. */
export function pushToast(toast: BusToast): boolean {
  if (listeners.size === 0) return false;
  listeners.forEach((listener) => listener(toast));
  return true;
}
