"use client";

import { useSyncExternalStore } from "react";
import { useRecoveryEmail } from "./contact";
import type { Translate } from "./i18n";
import { currentKey, KEY_CHANGED_EVENT } from "./live/client";

/**
 * What the menu and My page show about the user. Checked 2026-09-28 against every branch: the server has no
 * profile API. `POST /v1/web/session` returns `customer_id` and `user_key` only — no nickname — and no call
 * reads or saves a nickname or a recovery email. So both are null ("not issued" / "none registered") and are
 * never made up here. The token is this browser's user key, where the live connection keeps it.
 * ★`[2026-10-01]` The recovery email is the one exception: the customer can add it on My page, and it is kept in
 * this browser (`lib/contact.ts`) until the server has a call for it.
 */
export interface Profile {
  nickname: string | null;
  email: string | null;
  token: string | null;
}

/** Another tab changing the key fires `storage`; this tab adopting or replacing one fires `KEY_CHANGED_EVENT`. */
function subscribe(onChange: () => void) {
  addEventListener("storage", onChange);
  addEventListener(KEY_CHANGED_EVENT, onChange);
  return () => { removeEventListener("storage", onChange); removeEventListener(KEY_CHANGED_EVENT, onChange); };
}

/** Undefined until the page has read this browser (server render and hydration), then the profile. */
export function useProfile(): Profile | undefined {
  const token = useSyncExternalStore(subscribe, currentKey, () => undefined);
  const email = useRecoveryEmail();
  return token === undefined || email === undefined ? undefined : { nickname: null, email, token };
}

/** The name line of the menu and My page: the server's nickname, or which state it is in. */
export function nicknameLabel(profile: Profile | undefined, t: Translate): string {
  if (profile === undefined) return t("불러오는 중…", "Loading…");
  return profile.nickname ?? t("닉네임 미발급", "No nickname yet");
}
