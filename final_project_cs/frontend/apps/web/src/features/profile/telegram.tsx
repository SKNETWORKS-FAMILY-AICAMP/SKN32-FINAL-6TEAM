"use client";

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, ButtonLink } from "@/components/ui";
import { useConsent } from "@/features/consent/consent-store";
import { OptionalConsentPrompt } from "@/features/consent/optional-consent-prompt";
import { DATA_MODE } from "@/lib/data-mode";
import type { Translate } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import { putProfile, type ServerProfile } from "@/lib/live/profile";
import { countdownText, disconnectTelegram, secondsLeft, startTelegramConnect, testTelegram, type TelegramTestResult } from "@/lib/live/telegram-connect";
import { useSettings, useT } from "@/lib/settings";
import { serverProfileKey, useServerProfile } from "./webhook";
import styles from "./profile.module.css";

const STATUS: Record<NonNullable<ServerProfile["telegram"]["status"]>, [string, string]> = {
  untested: ["아직 시험 메시지를 보내지 않았어요.", "No test message has been sent yet."],
  ok: ["시험 메시지가 도착했어요.", "The test message arrived."],
  blocked: ["텔레그램에서 봇을 차단해서 알림이 닿지 않아요. 차단을 풀고 시험 메시지를 다시 보내 보세요.", "The bot is blocked in Telegram, so alerts do not reach you. Unblock it and send a test message again."],
};

function testText(result: TelegramTestResult, t: Translate): string {
  switch (result) {
    case "ok": return t("텔레그램 대화로 시험 메시지를 보냈어요.", "Sent a test message to the Telegram chat.");
    case "blocked": return t("시험 메시지를 보내지 못했어요. 텔레그램에서 봇을 차단해 둔 것 같아요.", "Could not send the test message. It looks like the bot is blocked in Telegram.");
    case "rate_limited": return t("텔레그램이 잠시 보내기를 막았어요. 조금 뒤 다시 해 보세요.", "Telegram is limiting messages for now. Try again shortly.");
    default: return t("보내지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not send it. Try again shortly.");
  }
}

/** The one-time link we are waiting on: Telegram's address, and when (ms) it stops working. */
interface Waiting { link: string; expiresAt: number }

/**
 * My page's Telegram row (`[2026-10-05 사용자 지시]` 알림만): 「텔레그램으로 연결」 opens our bot in Telegram; one tap on 「시작」 there binds the chat to the customer
 * (the server hears it from Telegram - this page only asks again every 2 seconds until the profile says connected). Alerts then go to Telegram.
 * Contract: `wiki/records/plans/2026-10-05_텔레그램_연결_백엔드_요청.md`.
 *
 * ★The whole row is hidden unless the server says it can (`telegram_connect.available`, or a chat is already connected): an older server, a server with no bot,
 *   a loading or failed profile, a build without the real server, and a browser with no session show nothing - no button that cannot work.
 * ★The one-time code is inside the link only: it is not kept in storage nor put in this page's address. `window.open` is only tried (a browser may refuse it,
 *   since it comes after the server's answer); the visible 「텔레그램 열기」 link is the way that always works.
 */
export function TelegramRow({ hasSession, guest = false }: { hasSession: boolean; guest?: boolean }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const profile = useServerProfile(hasSession);
  // ★`[2026-10-05 사용자 지시]` Connecting a chat hands over a piece of personal data (the chat's number): only after the optional alert-channel agreement, asked here when it is needed.
  const alertConsent = useConsent("alert_channel");
  const refetch = profile.refetch;
  const [waiting, setWaiting] = useState<Waiting | null>(null);
  const [now, setNow] = useState(0);                                // the clock of the countdown: set when the link arrives and each second after
  const [arrived, setArrived] = useState(false);                    // the connection was seen while we waited
  const [confirming, setConfirming] = useState(false);              // 「연결 풀기」 pressed once: 「정말 풀기」 / 「취소」
  const keep = (next: ServerProfile) => queryClient.setQueryData(serverProfileKey(language), next);

  const start = useMutation({
    mutationFn: () => startTelegramConnect(language),
    onSuccess: ({ link, expiresAt }) => {
      setNow(Date.now());
      setWaiting({ link, expiresAt: Date.parse(expiresAt) });
      try { window.open(link, "_blank", "noopener"); } catch { /* refused: the visible link is the way */ }
    },
  });
  const test = useMutation({ mutationFn: () => testTelegram(language), onSuccess: (answer) => keep(answer.profile) });
  const release = useMutation({
    mutationFn: () => disconnectTelegram(language),
    onSuccess: (next) => { keep(next); setConfirming(false); setWaiting(null); setArrived(false); test.reset(); },
    onError: () => setConfirming(false),
  });
  const choose = useMutation({ mutationFn: () => putProfile({ noticeChannel: "telegram" }, language), onSuccess: keep });

  // While we wait for the tap in Telegram: ask the server again every 2 seconds, and count down once a second. At the end of the time, look one last time.
  useEffect(() => {
    if (!waiting) return;
    const { expiresAt } = waiting;
    let alive = true;
    const look = async () => {
      const result = await refetch();
      if (alive && result.data?.telegram.connected === true) { setWaiting(null); setArrived(true); }
    };
    const poll = window.setInterval(() => void look(), 2000);
    const tick = window.setInterval(() => {
      const at = Date.now();
      setNow(at);
      if (at >= expiresAt) { window.clearInterval(tick); window.clearInterval(poll); void look(); }
    }, 1000);
    return () => { alive = false; window.clearInterval(tick); window.clearInterval(poll); };
  }, [waiting, refetch]);

  const data = profile.data;
  if (DATA_MODE !== "live" || !hasSession || !data) return null;
  if (!data.telegramConnect && !data.telegram.connected) return null;

  const connected = data.telegram.connected;
  const expired = waiting !== null && now >= waiting.expiresAt;
  const reason = (error: unknown, fallback: string) => error instanceof LiveError ? error.message : fallback;
  // ★`[2026-10-04]` 게스트는 알림을 받지 않는다(서버가 게스트의 여행을 감시·안내하지 않음) - 디스코드 줄과 같은 문장.
  // ★`[2026-10-05]` 서버가 일정 변경 알림을 고객이 연결한 채널로 보내는 길은 아직 없다(운영자 채널로만 나간다) - 화면은 알림이 간다고 약속하지 않고, 디스코드 줄과 같은 문장으로 「준비 중」이라고 말한다.
  const laterNote = !guest && <span className={styles.note}>{t("일정이 바뀔 때 텔레그램으로 알림을 보내는 기능은 준비 중이에요.", "Alerts about plan changes through Telegram are still being prepared.")}</span>;
  const guestNote = guest && <span className={styles.note}>{t("게스트는 일정 알림을 받지 않아요. 아래 소셜 계정을 연결하면 알림을 받을 수 있어요.", "Guests get no schedule alerts. Link a social account below to get them.")}</span>;

  const body = () => {
    if (connected) {
      const status = data.telegram.status;
      return <>
        {arrived && <span className={styles.note} role="status">{t("텔레그램이 연결됐어요. 「시험 메시지 보내기」로 이 대화에 메시지가 닿는지 확인해 보세요.", "Telegram is connected. Press “Send a test message” to see that a message reaches this chat.")}</span>}
        <span className={styles.line}>
          <Badge>{t("연결됨", "Connected")}</Badge>
          {data.noticeChannel === "telegram" && <>{" "}<span className={styles.tag}>{t("알림을 받는 곳", "Gets your alerts")}</span></>}
        </span>
        {status && <span className={status === "blocked" ? styles.failed : styles.note}>{t(...STATUS[status])}</span>}
        <Button variant="quiet" disabled={test.isPending} onClick={() => test.mutate()}>{test.isPending ? t("보내는 중…", "Sending…") : t("시험 메시지 보내기", "Send a test message")}</Button>
        <span className={test.isError || (test.data && test.data.result !== "ok") ? styles.failed : styles.note} role="status">{test.isError
          ? reason(test.error, t("보내지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not send it. Try again shortly."))
          : test.data ? testText(test.data.result, t) : ""}</span>
        {data.noticeChannel === "discord" && <>
          <Button variant="quiet" disabled={choose.isPending} onClick={() => choose.mutate()}>{choose.isPending ? t("바꾸는 중…", "Switching…") : t("이 채널로 받기", "Get alerts here")}</Button>
          {choose.isError && <span className={styles.failed} role="alert">{reason(choose.error, t("바꾸지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not switch. Try again shortly."))}</span>}
        </>}
        {confirming
          ? <>
            <span className={styles.note}>{t("연결을 풀면 이 텔레그램 대화로는 메시지가 가지 않아요.", "Once disconnected, nothing is sent to this Telegram chat.")}</span>
            <span className={styles.actions}>
              <Button variant="danger" disabled={release.isPending} onClick={() => release.mutate()}>{release.isPending ? t("푸는 중…", "Disconnecting…") : t("정말 풀기", "Disconnect now")}</Button>
              <Button variant="quiet" disabled={release.isPending} onClick={() => setConfirming(false)}>{t("취소", "Cancel")}</Button>
            </span>
          </>
          : <Button variant="quiet" onClick={() => { release.reset(); setConfirming(true); }}>{t("연결 풀기", "Disconnect")}</Button>}
        {release.isError && <span className={styles.failed} role="alert">{reason(release.error, t("연결을 풀지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not disconnect. Try again shortly."))}</span>}
      </>;
    }
    if (waiting && !expired) {
      return <>
        <ButtonLink href={waiting.link} target="_blank" rel="noopener noreferrer" variant="primary">{t("텔레그램 열기", "Open Telegram")}</ButtonLink>
        <span className={styles.note}>{t("텔레그램에서 「시작」을 눌러 주세요", "Press “Start” in Telegram")} · {t("남은 시간", "Time left")} {countdownText(secondsLeft(waiting.expiresAt, now))}</span>
        <Button variant="quiet" onClick={() => setWaiting(null)}>{t("취소", "Cancel")}</Button>
      </>;
    }
    if (!alertConsent) return <OptionalConsentPrompt code="alert_channel" why={t("텔레그램을 연결하려면 알림 채널 정보 수집·이용에 동의해야 해요.", "To connect Telegram, we need your agreement to the alert-channel item.")} onAgreed={() => {}} />;
    return <>
      {expired && <span className={styles.failed} role="alert">{t("연결 시간이 지났어요. 다시 눌러 주세요.", "The connection time ran out. Press the button again.")}</span>}
      {start.isError && <span className={styles.failed} role="alert">{reason(start.error, t("연결을 시작하지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not start connecting. Try again shortly."))}</span>}
      <Button variant="primary" disabled={start.isPending} onClick={() => { setWaiting(null); setArrived(false); start.mutate(); }}>
        {start.isPending ? t("텔레그램으로 가는 중…", "Going to Telegram…") : t("텔레그램으로 연결", "Connect with Telegram")}</Button>
      <span className={styles.note}>{t("텔레그램 앱이 열려요. 「시작」을 한 번 누르면 끝이에요. 텔레그램이 없으면 먼저 설치해 주세요(무료). 이 채팅은 알림 전용이라 답장은 받지 않아요.", "The Telegram app opens. Press “Start” once and you are done. No Telegram yet? Install it first (free). This chat is for alerts only - replies are not read.")}</span>
    </>;
  };

  return <div>
    <dt>{t("텔레그램 알림", "Telegram alerts")}</dt>
    <dd>{body()}{guestNote}{laterNote}</dd>
  </div>;
}
