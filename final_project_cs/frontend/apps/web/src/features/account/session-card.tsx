"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui";
import { LiveError, logout, type WebSession } from "@/lib/live/client";
import type { Profile } from "@/lib/profile";
import { useSettings, useT } from "@/lib/settings";
import styles from "./account.module.css";

/** 「168시간」 → 「7일」, 「30시간」 → 「30시간」 — whole days only when they come out even. */
export function idleText(hours: number, t: (ko: string, en: string) => string): string {
  if (hours >= 24 && hours % 24 === 0) {
    const days = hours / 24;
    return t(`${days}일`, `${days} day${days === 1 ? "" : "s"}`);
  }
  return t(`${hours}시간`, `${hours} hour${hours === 1 ? "" : "s"}`);
}

/**
 * `[2026-10-04 사용자 결정]` What My page says in place of the token: who this browser is to the server. No token is shown or kept —
 * the server gives a session cookie this page cannot read. A guest is told how long a trip lasts without use and what a guest may do;
 * a signed-in member can sign out. Everything here is what the server said about the session (`GET /v1/web/auth/me`).
 */
export function SessionCard({ profile }: { profile: Profile }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const session: WebSession | null = profile.session;

  async function signOut() {
    setBusy(true);
    setMessage(null);
    try {
      await logout(language);
      void queryClient.invalidateQueries();
      setMessage({ ok: true, text: t("로그아웃했어요. 다시 로그인하면 이 계정의 여행을 열 수 있어요.", "Signed out. Sign in again to open this account's trips.") });
    } catch (error) {
      setMessage({ ok: false, text: error instanceof LiveError || error instanceof Error ? error.message : String(error) });
    } finally { setBusy(false); }
  }

  const body = () => {
    if (profile.unreachable) return <p className={styles.mutedNote} role="alert">{t("서버에 연결하지 못해 로그인 상태를 확인하지 못했어요. 잠시 뒤 다시 열어 주세요.", "Could not reach the server to check your sign-in. Please open this page again shortly.")}</p>;
    if (!session) return <p className={styles.mutedNote}>{t("아직 시작하지 않았어요. 첫 계획을 올리면 이 기기에서 게스트로 시작해요.", "Nothing started yet. When you add your first plan, you start as a guest on this device.")}</p>;
    if (session.kind === "member") return <>
      <p className={styles.explain}>{t("로그인한 계정으로 쓰고 있어요. 여행은 이 기기를 쓰지 않아도 계정에 보관돼요.", "You are signed in. Your trips are kept with the account, even when this device is not used.")}</p>
      <div className={styles.actions}><Button disabled={busy} onClick={() => void signOut()}>{t("로그아웃", "Sign out")}</Button></div>
    </>;
    return <>
      <p className={styles.explain}>{session.guestIdleHours
        ? t(`게스트로 쓰고 있어요. 이 기기에서 ${idleText(session.guestIdleHours, t)} 동안 쓰지 않으면 여행과 함께 사라져요.`, `You are using triPilot as a guest. If this device is not used for ${idleText(session.guestIdleHours, t)}, your trips go away with it.`)
        : t("게스트로 쓰고 있어요. 한동안 쓰지 않으면 여행과 함께 사라져요.", "You are using triPilot as a guest. After a while without use, your trips go away with it.")}</p>
      <p className={styles.explain}>{t("게스트는 여행을 1개까지, 오늘부터 1년 안에 시작해 7일 이내로 만들 수 있어요. 일정 알림도 받지 않아요. 아래에서 계정을 연결하면 이 제한이 없어지고 여행이 보관돼요.", "A guest can make one trip, starting within a year and lasting up to seven days, and gets no schedule alerts. Link an account below to lift these limits and keep your trips.")}</p>
    </>;
  };

  return <fieldset className={styles.group}>
    <legend>{t("로그인 상태", "Sign-in status")}</legend>
    {body()}
    {message && <p className={message.ok ? styles.ok : styles.error} role={message.ok ? "status" : "alert"}>{message.text}</p>}
  </fieldset>;
}
