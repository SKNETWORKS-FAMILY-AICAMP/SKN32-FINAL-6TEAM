import type { Language } from "../i18n";
import { openApi } from "./client";

/**
 * `[2026-10-19 사용자 결정 — ST4F-613]` What the operator has turned on for the web, read WITHOUT a session (`GET /v1/web/features` → `{guardian}`):
 * the screens before a trip is registered may have no session yet (a new customer's first plan), and asking must not make a user.
 *
 * The Course Keeper (항로 지킴이) can be switched off in the admin console. Then the plan screen sends the plan without its card, the icon at the top is
 * not shown and the plan goes without `on_disruption` (`guardian/criteria-store.ts` `withCriteria`); the server asks first for every trip while it is
 * off, whatever it is sent. A registered trip learns it from its own view (no `guardian` there while it is off — `features/guardian/trip-guardian.tsx`).
 * ★Not readable (an older server without the read — 404 — or no connection): ON, as before. The server decides either way.
 * Contract: `wiki/external/rest-endpoints/web-trips.md` 「항로 지킴이 운영 스위치」.
 */
export interface WebFeatures { guardian: boolean }

const AS_BEFORE: WebFeatures = { guardian: true };

let known: WebFeatures | null = null;
let loading: Promise<WebFeatures> | null = null;
const listeners = new Set<() => void>();

function set(next: WebFeatures) {
  known = next;
  listeners.forEach((listener) => listener());
}

/** The answer so far: null until the first read is over. */
export const knownFeatures = (): WebFeatures | null => known;

/** The operator switched the Course Keeper off (and the server said so). Not read yet: false - nothing is held back on a guess. */
export const guardianSwitchedOff = (): boolean => known?.guardian === false;

export function subscribeFeatures(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => { listeners.delete(onChange); };
}

/** Read once per page (concurrent callers share the request). Never throws: what cannot be read is the way it was before (on). */
export function loadFeatures(language: Language): Promise<WebFeatures> {
  if (known) return Promise.resolve(known);
  loading ??= (async () => {
    let next = AS_BEFORE;
    try {
      const body = await openApi<{ guardian?: unknown }>("/v1/web/features", language);
      next = { guardian: body.guardian !== false };       // only a plain `false` switches it off
    } catch { /* older server (404) · no connection: as before */ }
    set(next);
    return next;
  })().finally(() => { loading = null; });
  return loading;
}

/** Tests only: forget what was read. */
export function resetFeatures() {
  known = null;
  loading = null;
  listeners.forEach((listener) => listener());
}
