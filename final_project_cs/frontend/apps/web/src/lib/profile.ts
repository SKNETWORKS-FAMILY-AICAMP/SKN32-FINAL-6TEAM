"use client";

import { useEffect, useSyncExternalStore } from "react";
import type { Translate } from "./i18n";
import { probeSession, sessionSnapshot, subscribeSession, type SessionSnapshot, type WebSession } from "./live/client";
import { useSettings } from "./settings";

/**
 * What the menu and My page show about the user. Checked 2026-09-28 against every branch: the server has no
 * profile API for a nickname, so it is null and never made up here.
 * ★`[2026-10-04 사용자 결정]` There is no token to show or keep any more: the server gives a session cookie, and what the screen can say
 *   is only what the server says about it — a guest (gone after some hours without use) or a signed-in member.
 * ★`[2026-10-03 user decision]` There is no recovery email any more; the Discord webhook (My page) is how alerts reach the customer.
 */
export interface Profile {
  nickname: string | null;
  /** The session this browser has; null = none yet (nothing has been started here) or the server could not be asked (`unreachable`). */
  session: WebSession | null;
  unreachable: boolean;
}

/** What the server render and hydration see: nothing asked yet. */
const unknown: SessionSnapshot = { probed: false, failed: false, session: null };

/** Undefined until the server has been asked who this browser is, then the profile. */
export function useProfile(): Profile | undefined {
  const { language } = useSettings();
  const snapshot = useSyncExternalStore(subscribeSession, sessionSnapshot, () => unknown);
  useEffect(() => {
    // Asks the server who this is; it never makes a session. A server that cannot be asked is shown as such (`failed`).
    if (!snapshot.probed) probeSession(language).catch(() => undefined);
  }, [snapshot.probed, language]);
  return snapshot.probed ? { nickname: null, session: snapshot.session, unreachable: snapshot.failed } : undefined;
}

/** The name line of the menu and My page: the server's nickname, or what kind of user this is. */
export function nicknameLabel(profile: Profile | undefined, t: Translate): string {
  if (profile === undefined) return t("불러오는 중…", "Loading…");
  if (profile.nickname) return profile.nickname;
  return profile.session?.kind === "member" ? t("로그인한 사용자", "Signed-in user") : t("게스트", "Guest");
}
