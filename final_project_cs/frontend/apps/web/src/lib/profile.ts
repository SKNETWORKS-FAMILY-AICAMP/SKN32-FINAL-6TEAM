"use client";

import { useSyncExternalStore } from "react";
import type { Translate } from "./i18n";
import { currentKey } from "./live/client";

/**
 * What the menu and My page show about the user. Checked 2026-09-28 against every branch: the server has no
 * profile API. `POST /v1/web/session` returns `customer_id` and `user_key` only — no nickname — and no call
 * reads or saves a nickname or a recovery email. So both are null ("not issued" / "none registered") and are
 * never made up here. The token is this browser's user key, where the live connection keeps it.
 */
export interface Profile {
  nickname: string | null;
  email: string | null;
  token: string | null;
}

function subscribe(onChange: () => void) {
  addEventListener("storage", onChange);
  return () => removeEventListener("storage", onChange);
}

/** Undefined until the page has read this browser (server render and hydration), then the profile. */
export function useProfile(): Profile | undefined {
  const token = useSyncExternalStore(subscribe, currentKey, () => undefined);
  return token === undefined ? undefined : { nickname: null, email: null, token };
}

/** The name line of the menu and My page: the server's nickname, or which state it is in. */
export function nicknameLabel(profile: Profile | undefined, t: Translate): string {
  if (profile === undefined) return t("불러오는 중…", "Loading…");
  return profile.nickname ?? t("닉네임 미발급", "No nickname yet");
}
