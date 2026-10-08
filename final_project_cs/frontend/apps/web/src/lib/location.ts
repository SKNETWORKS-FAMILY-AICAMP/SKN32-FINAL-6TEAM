/**
 * The customer's current position, from the browser's Geolocation API (`navigator.geolocation`).
 *
 * `[2026-09-30 user decision]` When a screen needs where the customer is, it asks the browser — never guesses from an
 * IP address or the plan. Rules:
 * - ★Only on the customer's own action (a button press). Asking as a page opens is what browsers penalise and what
 *   customers dismiss; the browser's permission prompt should follow something the customer did.
 *   ★`[2026-10-05 사용자 지시]` One exception — a map. 「지도가 나올 때 고객의 위치를 지도에 바로 표시」: when a map is on screen AND the customer
 *   has given the optional location consent (`useConsent("location")`, on the terms screen or My page), the map reads the position at once and
 *   follows it while it shows (`watchLocation`). The consent is the customer's own action the browser's question follows. Without that consent a
 *   map neither asks, sends nor draws anything. Every other place (the chat's 「내 위치 알려 주고 다시 묻기」) still asks only on a press.
 * - The browser allows it only on a secure page (https, or localhost/127.0.0.1 in development).
 * - A failure is returned, not thrown, with the reason, so the screen can say what to do (allow it in settings, try
 *   outside …) instead of a generic error.
 * - A fix is reused for a short while (the customer does not move far in two minutes) so a second question does not
 *   wait for the GPS again.
 * - ★A position is personal data: it is never written to the console, an error message, a URL or browser storage — memory only.
 */

export interface LocationFix {
  lat: number;
  lng: number;
  /** Radius in metres the browser is 95% sure of, when it says. */
  accuracyM: number | null;
  /** When the browser took the fix (ISO). */
  at: string;
}

export type LocationFailure = "unsupported" | "insecure" | "denied" | "unavailable" | "timeout";
export type LocationResult = { ok: true; fix: LocationFix } | { ok: false; reason: LocationFailure };
export type LocationPermission = "granted" | "prompt" | "denied" | "unknown";

const REUSE_MS = 2 * 60_000;
const TIMEOUT_MS = 15_000;
let last: LocationFix | null = null;
let pending: Promise<LocationResult> | null = null;

function geolocation(): Geolocation | null {
  return typeof navigator !== "undefined" && navigator.geolocation ? navigator.geolocation : null;
}

function fixOf(position: GeolocationPosition): LocationFix {
  return {
    lat: position.coords.latitude,
    lng: position.coords.longitude,
    accuracyM: Number.isFinite(position.coords.accuracy) ? Math.round(position.coords.accuracy) : null,
    at: new Date(position.timestamp || Date.now()).toISOString(),
  };
}

const failureOf = (error: { code: number }): LocationFailure => error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable";

/** Whether the browser will ask, has been allowed, or has been refused — without asking. `unknown` where it cannot say. */
export async function locationPermission(): Promise<LocationPermission> {
  try {
    const status = await navigator.permissions.query({ name: "geolocation" as PermissionName });
    return status.state === "granted" || status.state === "prompt" || status.state === "denied" ? status.state : "unknown";
  } catch {
    return "unknown";
  }
}

/** Ask the browser where the customer is. Call it from a click; concurrent calls share one request. */
export function currentLocation(options: { now?: number } = {}): Promise<LocationResult> {
  const now = options.now ?? Date.now();
  if (last && now - Date.parse(last.at) < REUSE_MS) return Promise.resolve({ ok: true, fix: last });
  if (typeof window !== "undefined" && window.isSecureContext === false) return Promise.resolve({ ok: false, reason: "insecure" });
  const geo = geolocation();
  if (!geo) return Promise.resolve({ ok: false, reason: "unsupported" });
  pending ??= new Promise<LocationResult>((resolve) => {
    geo.getCurrentPosition(
      (position) => {
        last = fixOf(position);
        resolve({ ok: true, fix: last });
      },
      (error) => resolve({ ok: false, reason: failureOf(error) }),
      { enableHighAccuracy: true, timeout: TIMEOUT_MS, maximumAge: REUSE_MS },
    );
  }).finally(() => { pending = null; });
  return pending;
}

/** Metres between two WGS84 points (haversine; plenty for tens of metres to a few kilometres). */
export function distanceM(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.min(1, Math.sqrt(h)));
}

// ── following the position while a map shows (`[2026-10-05 사용자 지시]`) ─────────────────────────────────────────

/** At most one new position every 2 s — a phone's GPS answers about once a second, and the map need not redraw that often. */
export const FOLLOW_MIN_MS = 2_000;
/** A move under 5 m is the same place on a map (GPS wobbles that much standing still)… */
export const FOLLOW_MIN_M = 5;
/**
 * …unless 30 s passed since the last one handed out: a customer standing still still gives a fresh fix now and then, so the server can tell
 * where they stayed (`location-samples.ts`). ★Only fixes the browser gives are handed out — an old fix is never re-dated.
 */
export const FOLLOW_KEEPALIVE_MS = 30_000;

/** The browser's sureness moved enough to redraw the circle (≥ 5 m and ≥ 20 %), or it said nothing before and does now. */
function accuracyChanged(before: number | null, after: number | null): boolean {
  if (before === null || after === null) return before !== after;
  return Math.abs(after - before) >= Math.max(5, before * 0.2);
}

/** Whether `next` is worth handing out after `previous` (the last one handed out): newer, and moved, surer, or 30 s later. Pure. */
export function isNewFix(previous: LocationFix | null, next: LocationFix): boolean {
  if (!previous) return true;
  const elapsed = Date.parse(next.at) - Date.parse(previous.at);
  if (!(elapsed > 0)) return false;                       // the same fix again (a cached answer), or an older one
  return distanceM(previous, next) >= FOLLOW_MIN_M || accuracyChanged(previous.accuracyM, next.accuracyM) || elapsed >= FOLLOW_KEEPALIVE_MS;
}

interface Follower { onFix: (fix: LocationFix) => void; onError?: (reason: LocationFailure) => void }
const followers = new Set<Follower>();
let watchId: number | null = null;
/** The last fix handed out, and when (page clock). */
let handed: LocationFix | null = null;
let handedAt = 0;
/** A fix that came sooner than `FOLLOW_MIN_MS` after the last one: handed out when that time has passed (the newest wins), so the map never stops short of where the customer is. */
let held: LocationFix | null = null;
let heldTimer: ReturnType<typeof setTimeout> | null = null;
let hearingVisibility = false;

function dropHeld() {
  if (heldTimer) clearTimeout(heldTimer);
  heldTimer = null;
  held = null;
}

function handOut(fix: LocationFix) {
  handed = fix;
  handedAt = Date.now();
  [...followers].forEach((follower) => follower.onFix(fix));
}

function take(fix: LocationFix) {
  if (!isNewFix(handed, fix)) {
    // The customer is back where the map already shows them: what was held is no longer where they are.
    if (held && Date.parse(fix.at) > Date.parse(held.at)) dropHeld();
    return;
  }
  const wait = handedAt + FOLLOW_MIN_MS - Date.now();
  if (!handed || wait <= 0) { dropHeld(); handOut(fix); return; }
  held = fix;
  heldTimer ??= setTimeout(() => {
    heldTimer = null;
    const next = held;
    held = null;
    if (next && followers.size) handOut(next);
  }, wait);
}

const pageHidden = () => typeof document !== "undefined" && document.visibilityState === "hidden";

function startWatch() {
  const geo = geolocation();
  if (watchId !== null || !followers.size || !geo || pageHidden()) return;
  watchId = geo.watchPosition(
    (position) => take(fixOf(position)),
    (error) => {
      const reason = failureOf(error);
      if (reason === "denied") stopWatch();               // the browser will not answer again; a page shown again asks once more (settings may have changed)
      [...followers].forEach((follower) => follower.onError?.(reason));
    },
    { enableHighAccuracy: true, timeout: 30_000, maximumAge: 10_000 },
  );
}

function stopWatch() {
  if (watchId !== null) geolocation()?.clearWatch(watchId);
  watchId = null;
  dropHeld();
}

/** A hidden page (another tab, the phone locked) does not follow the customer; shown again, it does. */
function onVisibility() {
  if (pageHidden()) stopWatch();
  else startWatch();
}

/**
 * `[2026-10-05 사용자 지시]` Follow the customer's position while a map shows (`navigator.geolocation.watchPosition`). Returns the function that stops it.
 * - One browser watch is shared by every caller; the last one to stop ends it (and forgets the last fix).
 * - A new caller gets the last fix at once, then each new one. Fixes are thinned out (`isNewFix`, `FOLLOW_MIN_MS`).
 * - It pauses while the page is hidden and goes on when it shows again.
 * - ★Call it only with the customer's location consent; the screen checks that (`useConsent("location")`).
 */
export function watchLocation(onFix: (fix: LocationFix) => void, onError?: (reason: LocationFailure) => void): () => void {
  let live = true;
  const failNow = (reason: LocationFailure) => { queueMicrotask(() => { if (live) onError?.(reason); }); return () => { live = false; }; };
  if (typeof window !== "undefined" && window.isSecureContext === false) return failNow("insecure");
  if (!geolocation()) return failNow("unsupported");
  const follower: Follower = { onFix, onError };
  followers.add(follower);
  if (!hearingVisibility && typeof document !== "undefined") { document.addEventListener("visibilitychange", onVisibility); hearingVisibility = true; }
  if (handed) { const fix = handed; queueMicrotask(() => { if (followers.has(follower)) onFix(fix); }); }
  startWatch();
  return () => {
    if (!followers.delete(follower) || followers.size) return;
    stopWatch();
    handed = null;
    handedAt = 0;
    if (hearingVisibility && typeof document !== "undefined") document.removeEventListener("visibilitychange", onVisibility);
    hearingVisibility = false;
  };
}

/**
 * What to tell the customer when the position could not be read. `where: "map"` — said under a map that could not show 「내 위치」 (there is no
 * button there to press again, so it does not say "press again").
 */
export function locationFailureText(reason: LocationFailure, t: (ko: string, en: string) => string, where: "button" | "map" = "button"): string {
  if (where === "map") {
    switch (reason) {
      case "denied": return t("위치 권한이 꺼져 있어 내 위치를 못 보여 드려요. 브라우저 주소창 왼쪽의 사이트 설정에서 위치를 허용하면 지도에 보여 드려요.", "Location is blocked, so your position is not on the map. Allow it in the site settings next to the address bar to see it.");
      case "timeout": return t("내 위치를 아직 찾지 못했어요. 실내라면 창가나 밖에서 더 잘 잡혀요.", "Your position has not been found yet. It works better near a window or outside.");
      case "insecure": return t("이 주소(https 가 아닌 주소)에서는 브라우저가 위치를 알려 주지 않아 내 위치를 못 보여 드려요.", "The browser gives location only on a secure (https) page, so your position is not on the map.");
      case "unsupported": return t("이 브라우저는 위치를 알려 주지 않아 내 위치를 못 보여 드려요.", "This browser cannot share your location, so your position is not on the map.");
      default: return t("지금은 위치를 찾을 수 없어 내 위치를 못 보여 드려요.", "Your location is not available right now, so it is not on the map.");
    }
  }
  switch (reason) {
    case "denied": return t("위치 권한이 꺼져 있어요. 브라우저 주소창 왼쪽의 사이트 설정에서 위치를 허용한 뒤 다시 눌러 주세요.", "Location is blocked. Allow it in the site settings next to the address bar, then press again.");
    case "timeout": return t("위치를 제때 찾지 못했어요. 실내라면 창가나 밖에서 다시 눌러 주세요.", "Finding your location took too long. If you are indoors, try near a window or outside.");
    case "insecure": return t("이 주소(https 가 아닌 주소)에서는 브라우저가 위치를 알려 주지 않아요.", "The browser gives location only on a secure (https) page.");
    case "unsupported": return t("이 브라우저는 위치를 알려 주지 않아요.", "This browser cannot share your location.");
    default: return t("지금은 위치를 찾을 수 없어요. 잠시 뒤 다시 눌러 주세요.", "Your location is not available right now. Please try again shortly.");
  }
}

/** Test hook: forget the reused fix, and stop following (every caller of `watchLocation` is dropped). */
export function forgetLocation() {
  last = null;
  pending = null;
  stopWatch();
  followers.clear();
  handed = null;
  handedAt = 0;
  if (hearingVisibility && typeof document !== "undefined") document.removeEventListener("visibilitychange", onVisibility);
  hearingVisibility = false;
}
