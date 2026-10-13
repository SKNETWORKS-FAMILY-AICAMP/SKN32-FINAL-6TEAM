"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
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
 * the server gives a session cookie this page cannot read. A guest is told how long a trip lasts without use and what a guest may do.
 * Everything here is what the server said about the session (`GET /v1/web/auth/me`). Signing out is `SignOut`, at the foot of the screen.
 */
export function SessionCard({ profile }: { profile: Profile }) {
  const t = useT();
  const session: WebSession | null = profile.session;

  const body = () => {
    if (profile.unreachable) return <p className={styles.mutedNote} role="alert">{t("서버에 연결하지 못해 로그인 상태를 확인하지 못했어요. 잠시 뒤 다시 열어 주세요.", "Could not reach the server to check your sign-in. Please open this page again shortly.")}</p>;
    if (!session) return <p className={styles.mutedNote}>{t("아직 시작하지 않았어요. 첫 계획을 올리면 이 기기에서 게스트로 시작해요.", "Nothing started yet. When you add your first plan, you start as a guest on this device.")}</p>;
    if (session.kind === "member") return <p className={styles.explain}>{t("로그인한 계정으로 쓰고 있어요. 여행은 이 기기를 쓰지 않아도 계정에 보관돼요.", "You are signed in. Your trips are kept with the account, even when this device is not used.")}</p>;
    return <>
      {/* `[2026-10-04 사용자 지시 · 서버]` 게스트 쿠키는 브라우저 세션 쿠키다(Max-Age 없음) — 창을 닫으면 이어 쓸 수 없고, 서버의 자료는 N시간 뒤 지워진다. */}
      <p className={styles.explain}>{session.guestIdleHours
        ? t(`게스트로 쓰고 있어요. 창을 닫으면 이어 쓸 수 없고, 서버에 있는 자료는 ${idleText(session.guestIdleHours, t)} 뒤에 지워져요. 여행계획서를 내려받아 두세요.`, `You are using triPilot as a guest. If you close this window you cannot continue it, and the data on the server is deleted after ${idleText(session.guestIdleHours, t)}. Download your trip plan to keep it.`)
        : t("게스트로 쓰고 있어요. 창을 닫으면 이어 쓸 수 없고, 서버에 있는 자료도 얼마 뒤 지워져요. 여행계획서를 내려받아 두세요.", "You are using triPilot as a guest. If you close this window you cannot continue it, and the data on the server is deleted after a while. Download your trip plan to keep it.")}</p>
      <p className={styles.explain}>{t("게스트는 여행을 1개까지, 오늘부터 1년 안에 시작해 7일 이내로 만들 수 있어요. 일정 알림도 받지 않아요. 아래에서 계정을 연결하면 이 제한이 없어지고 여행이 보관돼요.", "A guest can make one trip, starting within a year and lasting up to seven days, and gets no schedule alerts. Link an account below to lift these limits and keep your trips.")}</p>
    </>;
  };

  return <fieldset className={styles.group}>
    <legend>{t("로그인 상태", "Sign-in status")}</legend>
    {body()}
  </fieldset>;
}

/**
 * `[2026-10-13 회의 확정 — 로그아웃은 「로그인 · 계정」 화면에만]` The sign-out at the foot of that screen (the menu has none now), and
 * `[2026-10-13 사용자 결정]` it asks first. A member signs out only from the dialog's 「로그아웃」; what was read for the account is dropped and
 * the sentence stays here — the screen does not move (`[2026-10-13 정한 것 ⑤]`).
 */
export function SignOut({ profile }: { profile: Profile | undefined }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const member = profile?.session?.kind === "member";

  async function signOut() {
    setBusy(true);
    setMessage(null);
    try {
      await logout(language);
      // `[2026-10-05 · 팀 develop 점검]` Not only marked old: dropped. Marked old they stayed on screen (the previous account's trips and chat) until a re-read, and a failed re-read left them.
      await queryClient.cancelQueries();
      queryClient.clear();
      setMessage({ ok: true, text: t("로그아웃했어요. 다시 로그인하면 이 계정의 여행을 열 수 있어요.", "Signed out. Sign in again to open this account's trips.") });
    } catch (error) {
      setMessage({ ok: false, text: error instanceof LiveError || error instanceof Error ? error.message : String(error) });
    } finally { setBusy(false); setAsking(false); }
  }

  function cancel() {
    setAsking(false);
    opener.current?.focus();
  }

  if (!member && !message) return null;
  return <div className={styles.signOut}>
    {member && <Button ref={opener} className={styles.signOutButton} disabled={busy} onClick={() => setAsking(true)}>{t("로그아웃", "Sign out")}</Button>}
    {message && <p className={message.ok ? styles.ok : styles.error} role={message.ok ? "status" : "alert"}>{message.text}</p>}
    {asking && <SignOutDialog t={t} pending={busy} onCancel={cancel} onConfirm={() => void signOut()} />}
  </div>;
}

/** Asks before signing out — the same dialog as deleting a trip (`trip-list.tsx`): focus starts on Cancel and stays inside; Escape cancels; the backdrop does nothing. */
function SignOutDialog({ t, pending, onCancel, onConfirm }: { t: (ko: string, en: string) => string; pending: boolean; onCancel: () => void; onConfirm: () => void }) {
  const cancel = useRef<HTMLButtonElement>(null);
  const confirm = useRef<HTMLButtonElement>(null);
  useEffect(() => { cancel.current?.focus(); }, []);

  function keys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.preventDefault(); if (!pending) onCancel(); return; }
    if (event.key !== "Tab") return;
    if (event.shiftKey && document.activeElement === cancel.current) { event.preventDefault(); confirm.current?.focus(); }
    else if (!event.shiftKey && document.activeElement === confirm.current) { event.preventDefault(); cancel.current?.focus(); }
  }

  // While signing out, both buttons stay focusable (aria-disabled) so focus does not drop out of the dialog.
  return createPortal(<div className={styles.overlay}>
    <div className={styles.dialog} role="alertdialog" aria-modal="true" aria-labelledby="sign-out-title" aria-describedby="sign-out-body" onKeyDown={keys}>
      <h2 id="sign-out-title">{t("로그아웃할까요?", "Sign out?")}</h2>
      <p id="sign-out-body" className={styles.dialogBody}>{t("이 브라우저에서 계정 여행이 안 보여요. 다시 로그인하면 그대로 있어요.", "This browser stops showing your account's trips. Sign in again and they are all there.")}</p>
      <div className={styles.dialogActions}>
        <Button ref={cancel} aria-disabled={pending || undefined} onClick={() => { if (!pending) onCancel(); }}>{t("취소", "Cancel")}</Button>
        <Button ref={confirm} variant="primary" aria-disabled={pending || undefined} onClick={() => { if (!pending) onConfirm(); }}>{pending ? t("로그아웃하는 중…", "Signing out…") : t("로그아웃", "Sign out")}</Button>
      </div>
    </div>
  </div>, document.body);
}
