"use client";

import { useSyncExternalStore } from "react";
import type { Translate } from "./i18n";
import { currentKey, KEY_CHANGED_EVENT } from "./live/client";

/**
 * What the menu and My page show about the user. Checked 2026-09-28 against every branch: the server has no
 * profile API. `POST /v1/web/session` returns `customer_id` and `user_key` only — no nickname — and no call
 * reads or saves a nickname or a recovery email. So both are null ("not issued" / "none registered") and are
 * never made up here. The token is this browser's user key, where the live connection keeps it.
 * ★`[2026-10-03 user decision]` There is no recovery email any more; the Discord webhook (My page) is how alerts reach the customer.
 */
export interface Profile {
  nickname: string | null;
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
  return token === undefined ? undefined : { nickname: null, token };
}

/** The name line of the menu and My page: the server's nickname, or which state it is in. */
export function nicknameLabel(profile: Profile | undefined, t: Translate): string {
  if (profile === undefined) return t("불러오는 중…", "Loading…");
  return profile.nickname ?? t("닉네임 미발급", "No nickname yet");
}
