/**
 * The customer's current position, from the browser's Geolocation API (`navigator.geolocation`).
 *
 * `[2026-09-30 user decision]` When a screen needs where the customer is, it asks the browser — never guesses from an
 * IP address or the plan. Rules:
 * - ★Only on the customer's own action (a button press). Asking as a page opens is what browsers penalise and what
 *   customers dismiss; the browser's permission prompt should follow something the customer did.
 * - The browser allows it only on a secure page (https, or localhost/127.0.0.1 in development).
 * - A failure is returned, not thrown, with the reason, so the screen can say what to do (allow it in settings, try
 *   outside …) instead of a generic error.
 * - A fix is reused for a short while (the customer does not move far in two minutes) so a second question does not
 *   wait for the GPS again.
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
        last = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracyM: Number.isFinite(position.coords.accuracy) ? Math.round(position.coords.accuracy) : null,
          at: new Date(position.timestamp || Date.now()).toISOString(),
        };
        resolve({ ok: true, fix: last });
      },
      (error) => resolve({ ok: false, reason: error.code === 1 ? "denied" : error.code === 3 ? "timeout" : "unavailable" }),
      { enableHighAccuracy: true, timeout: TIMEOUT_MS, maximumAge: REUSE_MS },
    );
  }).finally(() => { pending = null; });
  return pending;
}

/** What to tell the customer when the position could not be read. */
export function locationFailureText(reason: LocationFailure, t: (ko: string, en: string) => string): string {
  switch (reason) {
    case "denied": return t("위치 권한이 꺼져 있어요. 브라우저 주소창 왼쪽의 사이트 설정에서 위치를 허용한 뒤 다시 눌러 주세요.", "Location is blocked. Allow it in the site settings next to the address bar, then press again.");
    case "timeout": return t("위치를 제때 찾지 못했어요. 실내라면 창가나 밖에서 다시 눌러 주세요.", "Finding your location took too long. If you are indoors, try near a window or outside.");
    case "insecure": return t("이 주소(https 가 아닌 주소)에서는 브라우저가 위치를 알려 주지 않아요.", "The browser gives location only on a secure (https) page.");
    case "unsupported": return t("이 브라우저는 위치를 알려 주지 않아요.", "This browser cannot share your location.");
    default: return t("지금은 위치를 찾을 수 없어요. 잠시 뒤 다시 눌러 주세요.", "Your location is not available right now. Please try again shortly.");
  }
}

/** Test hook: forget the reused fix. */
export function forgetLocation() {
  last = null;
  pending = null;
}
