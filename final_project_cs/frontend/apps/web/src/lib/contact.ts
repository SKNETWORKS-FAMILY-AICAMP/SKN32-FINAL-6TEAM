"use client";

import { useSyncExternalStore } from "react";
import { DATA_MODE } from "./data-mode";
import type { Language } from "./i18n";
import { currentKey, LiveError } from "./live/client";
import { getProfile, isUnsupported, putProfile } from "./live/profile";

/**
 * The customer's recovery email.
 *
 * `[2026-10-01 user decision]` The first-start screen asks for it once (optional); My page adds, changes or removes it
 * later. The server keeps it (`PUT /v1/web/profile`) once this browser has a user key. This browser keeps a copy so
 * screens read it at once, and holds the value on its own when the server cannot take it yet:
 *   - no user key yet (the first trip has not been registered): saving the email must not create a server user, so it
 *     waits here (`pending`) and goes up with the first sync after the key exists;
 *   - a server without the call (404/405), or the demo build: it stays here.
 *
 * ★Only the email is kept in this browser. A Discord webhook address, when it comes, is a secret the server uses to send —
 *   it must never be written to this browser's storage.
 */
const KEY = "tripilot.web.contact.v1";
export const CONTACT_CHANGED_EVENT = "tripilot:contact-changed";

interface Stored { recoveryEmail: string; pending: boolean }

function readRaw(): string | null {
  try { return window.localStorage.getItem(KEY); } catch { return null; }
}

function parse(raw: string | null): Stored | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as { recoveryEmail?: unknown; pending?: unknown };
    const email = typeof value.recoveryEmail === "string" ? value.recoveryEmail.trim() : "";
    // A copy written before the server call existed has no `pending`: it never reached the server.
    return email ? { recoveryEmail: email, pending: value.pending !== false } : null;
  } catch {
    return null;
  }
}

function write(value: Stored | null): boolean {
  try {
    if (value === null) window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    return false;
  }
  try { window.dispatchEvent(new Event(CONTACT_CHANGED_EVENT)); } catch { /* not in a browser */ }
  return true;
}

/** The email this browser holds, or null. Never throws: storage can be blocked or hold something unreadable. */
export function readRecoveryEmail(): string | null {
  return parse(readRaw())?.recoveryEmail ?? null;
}

export type SavedWhere = "server" | "browser";

/**
 * Save the email (ends trimmed); blank or null removes it. Resolves where it ended up. Rejects — with nothing changed —
 * when the browser blocks storage or the server refuses the value.
 */
export async function saveRecoveryEmail(email: string | null, language: Language): Promise<SavedWhere> {
  const value = email?.trim() || null;
  const before = readRaw();
  const restore = () => {
    try {
      if (before === null) window.localStorage.removeItem(KEY); else window.localStorage.setItem(KEY, before);
      window.dispatchEvent(new Event(CONTACT_CHANGED_EVENT));
    } catch { /* ignore */ }
  };
  if (!write(value === null ? null : { recoveryEmail: value, pending: true })) {
    throw new LiveError("storage_blocked", language === "ko" ? "이 브라우저가 저장을 막았어요. 개인정보 보호 모드를 끄고 다시 눌러 주세요." : "This browser blocked saving. Turn off private browsing and try again.");
  }
  if (DATA_MODE !== "live" || !currentKey()) return "browser";
  try {
    const profile = await putProfile({ recoveryEmail: value }, language);
    const confirmed = profile.recoveryEmail;
    write(confirmed === null ? null : { recoveryEmail: confirmed, pending: false });
    return "server";
  } catch (error) {
    if (isUnsupported(error)) return "browser";
    // The server said no (or could not be reached): put back what was there, so the screen and the server agree.
    restore();
    throw error;
  }
}

/**
 * Bring this browser's copy and the server together — run once when the app opens. The server's value wins, except a
 * value that only reached this browser (`pending`): that one goes up first, so an email typed before the first trip was
 * registered is not lost. Silent on any failure: nothing here may stop the app from opening.
 */
export async function syncRecoveryEmail(language: Language): Promise<void> {
  if (DATA_MODE !== "live" || !currentKey()) return;
  try {
    const local = parse(readRaw());
    if (local?.pending) {
      const sent = await putProfile({ recoveryEmail: local.recoveryEmail }, language);
      write(sent.recoveryEmail === null ? null : { recoveryEmail: sent.recoveryEmail, pending: false });
      return;
    }
    const server = await getProfile(language);
    if (server.recoveryEmail !== (local?.recoveryEmail ?? null)) {
      write(server.recoveryEmail === null ? null : { recoveryEmail: server.recoveryEmail, pending: false });
    }
  } catch { /* an older server, or no connection: this browser's copy stays as it is */ }
}

function subscribe(onChange: () => void) {
  addEventListener("storage", onChange);
  addEventListener(CONTACT_CHANGED_EVENT, onChange);
  return () => { removeEventListener("storage", onChange); removeEventListener(CONTACT_CHANGED_EVENT, onChange); };
}

/** Undefined until the page has read this browser (server render and hydration), then the email or null. */
export function useRecoveryEmail(): string | null | undefined {
  return useSyncExternalStore(subscribe, readRecoveryEmail, () => undefined);
}

/** Whether the email shown is on the server (true), only in this browser (false), or there is none / not read yet (undefined). */
export function useRecoveryEmailOnServer(): boolean | undefined {
  const pending = useSyncExternalStore(subscribe, () => parse(readRaw())?.pending ?? null, () => undefined);
  return pending === undefined || pending === null ? undefined : !pending;
}
