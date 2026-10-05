"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, ButtonLink } from "@/components/ui";
import { useConsent } from "@/features/consent/consent-store";
import { OptionalConsentPrompt } from "@/features/consent/optional-consent-prompt";
import { discordWebhookProblem } from "@/features/onboarding/model";
import { DATA_MODE } from "@/lib/data-mode";
import type { Language, Translate } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import { readDiscordReturn, startDiscordConnect, type DiscordReturn } from "@/lib/live/discord-connect";
import { getProfile, isUnsupported, putProfile, testDiscordWebhook, type ServerProfile, type WebhookTestResult } from "@/lib/live/profile";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { webhookWaiting } from "@/lib/webhook";
import styles from "./profile.module.css";

export const serverProfileKey = (language: Language) => ["server-profile", language] as const;

/** The server's contact details (`GET /v1/web/profile`) — asked only in a live build with a session: asking without one would create a user. */
export function useServerProfile(hasSession: boolean) {
  const { language } = useSettings();
  return useQuery({ queryKey: serverProfileKey(language), queryFn: () => getProfile(language), enabled: DATA_MODE === "live" && hasSession, retry: false });
}

const STATUS: Record<NonNullable<ServerProfile["webhook"]["status"]>, [string, string]> = {
  untested: ["아직 시험 메시지를 보내지 않았어요.", "No test message has been sent yet."],
  ok: ["시험 메시지가 도착했어요.", "The test message arrived."],
  invalid: ["디스코드가 이 웹훅을 거절했어요. 새 주소로 바꿔 주세요.", "Discord refused this webhook. Please replace it."],
};

function testText(result: WebhookTestResult, t: Translate): string {
  switch (result) {
    case "ok": return t("디스코드 채널에 시험 메시지를 보냈어요.", "Sent a test message to the Discord channel.");
    case "invalid": return t("디스코드가 이 웹훅을 거절했어요(지워졌거나 잘못된 주소). 새 주소로 바꿔 주세요.", "Discord refused this webhook (deleted or wrong). Please replace it.");
    case "rate_limited": return t("디스코드가 잠시 보내기를 막았어요. 조금 뒤 다시 해 보세요.", "Discord is limiting messages for now. Try again shortly.");
    default: return t("보내지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not send it. Try again shortly.");
  }
}

/** What the page says after the trip to Discord and back (`?discord=…`, sent by the server's callback). */
function returnText(result: DiscordReturn, t: Translate): { ok: boolean; text: string } {
  switch (result) {
    case "connected": return { ok: true, text: t("디스코드 채널이 연결됐어요. 「시험 메시지 보내기」로 그 채널에 메시지가 닿는지 확인해 보세요.", "The Discord channel is connected. Press “Send a test message” to see that a message reaches it.") };
    case "cancelled": return { ok: false, text: t("연결을 취소했어요. 바뀐 것은 없어요.", "Connecting was cancelled. Nothing changed.") };
    case "expired": return { ok: false, text: t("연결 시간이 지났어요. 「디스코드로 연결」을 다시 눌러 주세요.", "The connection took too long. Press “Connect with Discord” again.") };
    default: return { ok: false, text: t("디스코드 연결에 실패했어요. 잠시 뒤 다시 해 보세요.", "Could not connect to Discord. Try again shortly.") };
  }
}

/**
 * My page's Discord webhook row: whether one is saved (masked — the server never returns the address), whether Discord
 * took the last test, and a test message on request. Alerts about plan changes are the server's next step, not built yet.
 */
export function WebhookView({ hasSession, guest = false }: { hasSession: boolean; guest?: boolean }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const profile = useServerProfile(hasSession);
  // ★`[2026-10-05 사용자 지시]` Connecting a channel hands over a piece of personal data (the address of the customer's channel): it is asked for only once the customer has agreed to the optional
  //   alert-channel item (`alert_channel`) - asked right here, when it becomes needed, and the app works without it.
  const alertConsent = useConsent("alert_channel");
  const test = useMutation({
    mutationFn: () => testDiscordWebhook(language),
    onSuccess: (answer) => queryClient.setQueryData(serverProfileKey(language), answer.profile),
  });
  // ★`[2026-10-04]` 서버는 게스트의 여행을 감시·안내하지 않는다(외부 호출 비용) — 웹훅을 넣어도 알림은 로그인한 사용자만 받는다.
  const later = <span className={styles.note}>{guest
    ? t("게스트는 일정 알림을 받지 않아요. 아래 소셜 계정을 연결하면 알림을 받을 수 있어요.", "Guests get no schedule alerts. Link a social account below to get them.")
    : t("일정이 바뀔 때 디스코드로 알림을 보내는 기능은 준비 중이에요.", "Alerts about plan changes through Discord are still being prepared.")}</span>;
  // ★`[2026-10-05 사용자 지시]` 「디스코드로 연결」: 서버가 연결할 수 있다고 말할 때만(`discord_connect.available`) 단추가 있다. 디스코드 창에서 서버·채널을 고르면 서버가 웹훅을 받아 저장한다.
  const [returned, setReturned] = useState<DiscordReturn | null>(null);
  useEffect(() => {
    const found = readDiscordReturn(window.location.search);
    if (found === null) return;
    window.history.replaceState(null, "", window.location.pathname);          // 돌아왔다는 표시는 주소창에 남기지 않는다
    void Promise.resolve().then(() => {                                       // 화면을 바꾸는 것은 이 효과가 끝난 뒤에(개발 모드에서 효과가 두 번 돌아도 메시지는 한 번)
      setReturned(found);
      if (found === "connected") void queryClient.invalidateQueries({ queryKey: ["server-profile"] });
    });
  }, [queryClient]);
  const connect = useMutation({ mutationFn: async () => { window.location.assign(await startDiscordConnect(language)); } });
  // ★`[2026-10-05 사용자 지시]` 알림 받는 곳은 한 번에 한 곳(디스코드·텔레그램 중 마지막에 연결한 곳). 텔레그램이 활성일 때 「이 채널로 받기」로 디스코드로 되돌린다.
  const choose = useMutation({
    mutationFn: () => putProfile({ noticeChannel: "discord" }, language),
    onSuccess: (next) => queryClient.setQueryData(serverProfileKey(language), next),
  });
  const connectable = profile.data?.discordConnect === true;
  const back = returned && returnText(returned, t);
  const connectLine = (label: string, primary: boolean) => <>
    <Button variant={primary ? "primary" : "quiet"} disabled={connect.isPending} onClick={() => { setReturned(null); connect.mutate(); }}>
      {connect.isPending ? t("디스코드로 가는 중…", "Going to Discord…") : label}</Button>
    {connect.isError && <span className={styles.failed} role="alert">{connect.error instanceof LiveError ? connect.error.message : t("연결을 시작하지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not start connecting. Try again shortly.")}</span>}
  </>;
  const backLine = back && <span className={back.ok ? styles.note : styles.failed} role={back.ok ? "status" : "alert"}>{back.text}</span>;
  const add = <ButtonLink href={routes.myPageEdit} variant="quiet">{connectable ? t("주소 직접 넣기", "Paste the address") : t("웹훅 등록하기", "Add a webhook")}</ButtonLink>;

  if (DATA_MODE !== "live") return <span className={styles.muted}>{t("실제 서버에 연결됐을 때만 등록할 수 있어요.", "Can be added only when connected to the real server.")}</span>;
  if (!hasSession) return <>
    <span className={styles.muted}>{webhookWaiting()
      ? t("입력한 웹훅은 첫 여행을 등록하면 서버에 저장돼요. 그 전에 새로고침하면 다시 넣어 주세요.", "The webhook you entered is saved when you register your first trip. Enter it again if you reload before then.")
      : t("등록된 웹훅이 없어요.", "No webhook registered.")}</span>
    {!webhookWaiting() && add}{later}
  </>;
  if (profile.isPending) return <span className={styles.muted} role="status">{t("불러오고 있어요.", "Loading.")}</span>;
  if (profile.isError) return <>
    <span className={styles.failed} role="alert">{isUnsupported(profile.error) ? t("이 서버는 웹훅 저장을 지원하지 않아요.", "This server does not take a webhook.") : profile.error.message}</span>
    {!isUnsupported(profile.error) && <Button variant="quiet" onClick={() => void profile.refetch()}>{t("다시 불러오기", "Try again")}</Button>}
  </>;
  const hook = profile.data.webhook;
  // 서버가 텔레그램을 알릴 때만(`telegram_connect.available`, 또는 이미 연결된 대화) 「알림을 받는 곳」 꼬리표와 「이 채널로 받기」가 있다 - 옛 서버의 줄은 그대로다.
  const twoPlaces = profile.data.telegramConnect || profile.data.telegram.connected;
  if (!hook.set) return <>
    {backLine}
    <span className={styles.muted}>{t("등록된 웹훅이 없어요.", "No webhook registered.")}</span>
    {!alertConsent && <OptionalConsentPrompt code="alert_channel" why={t("알림을 받을 채널을 연결하려면 알림 채널 정보 수집·이용에 동의해야 해요.", "To connect a channel for alerts, we need your agreement to the alert-channel item.")} onAgreed={() => {}} />}
    {alertConsent && connectable && <>
      {connectLine(t("디스코드로 연결", "Connect with Discord"), true)}
      <span className={styles.note}>{t("버튼을 누르면 디스코드 창이 열려요. 알림을 받을 서버와 채널을 고르고 승인하면 끝이에요 — 주소를 복사해 붙여넣을 필요가 없어요. 알림을 받을 서버가 없으면 디스코드 앱에서 「서버 만들기」로 내 서버를 먼저 만들어 주세요(무료).", "Press the button and Discord opens a window. Pick the server and channel that should get the alerts and approve - no address to copy. No server yet? Make your own in the Discord app first (free).")}</span>
    </>}
    {alertConsent && add}{later}
  </>;
  return <>
    {backLine}
    <code className={styles.line}>{hook.masked}</code>
    {twoPlaces && profile.data.noticeChannel === "discord" && <span className={styles.tag}>{t("알림을 받는 곳", "Gets your alerts")}</span>}
    {hook.status && <span className={hook.status === "invalid" ? styles.failed : styles.note}>{t(...STATUS[hook.status])}</span>}
    <Button variant="quiet" disabled={test.isPending} onClick={() => test.mutate()}>{test.isPending ? t("보내는 중…", "Sending…") : t("시험 메시지 보내기", "Send a test message")}</Button>
    <span className={test.isError || (test.data && test.data.result !== "ok") ? styles.failed : styles.note} role="status">{test.isError
      ? (test.error instanceof LiveError ? test.error.message : t("보내지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not send it. Try again shortly."))
      : test.data ? testText(test.data.result, t) : ""}</span>
    {twoPlaces && profile.data.noticeChannel === "telegram" && <>
      <Button variant="quiet" disabled={choose.isPending} onClick={() => choose.mutate()}>{choose.isPending ? t("바꾸는 중…", "Switching…") : t("이 채널로 받기", "Get alerts here")}</Button>
      {choose.isError && <span className={styles.failed} role="alert">{choose.error instanceof LiveError ? choose.error.message : t("바꾸지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not switch. Try again shortly.")}</span>}
    </>}
    {connectable && connectLine(t("다른 채널로 바꾸기", "Switch to another channel"), false)}
    {later}
  </>;
}

/** The edit screen's webhook field. Blank keeps the saved one (its address is never shown again); the box removes it. */
export function WebhookField({ hasSession, value, remove, touched, onValue, onRemove, onBlur }: {
  hasSession: boolean; value: string; remove: boolean; touched: boolean;
  onValue: (value: string) => void; onRemove: (remove: boolean) => void; onBlur: () => void;
}) {
  const t = useT();
  const profile = useServerProfile(hasSession);
  const live = DATA_MODE === "live";
  const saved = profile.data?.webhook.set ? profile.data.webhook.masked : null;
  const alertConsent = useConsent("alert_channel");
  const easier = live && profile.data?.discordConnect === true && alertConsent;
  const error = touched && !remove && Boolean(discordWebhookProblem(value));
  return <div className={styles.field}>
    <label htmlFor="profile-webhook">{t("디스코드 웹훅 URL", "Discord webhook URL")} <small>{t("(선택)", "(optional)")}</small></label>
    <input id="profile-webhook" type="url" inputMode="url" autoComplete="off" autoCapitalize="none" spellCheck={false} disabled={!live || remove || !alertConsent}
      placeholder={saved ? t(`등록됨: ${saved}`, `Saved: ${saved}`) : "https://discord.com/api/webhooks/…"} value={value}
      onChange={(event) => onValue(event.target.value)} onBlur={onBlur}
      aria-invalid={error} aria-describedby={error ? "profile-webhook-hint profile-webhook-error" : "profile-webhook-hint"} />
    <p id="profile-webhook-hint" className={styles.note}>{!live
      ? t("실제 서버에 연결됐을 때만 등록할 수 있어요.", "Can be added only when connected to the real server.")
      : saved
        ? t("새 주소를 넣고 저장하면 바뀌어요. 비워 두면 등록된 웹훅을 그대로 둬요. 주소는 서버에만 있고 다시 보여 드리지 않아요.", "Enter a new address and save to replace it; leave it blank to keep the saved one. The address stays on the server and is not shown again.")
        : t("알림을 받을 디스코드 채널에서 만든 웹훅 주소를 붙여 넣어 주세요. 이 브라우저에는 남기지 않아요.", "Paste the webhook URL made in the Discord channel that should get the alerts. It is not kept in this browser.")}</p>
    {live && !alertConsent && <OptionalConsentPrompt code="alert_channel" why={t("디스코드 주소를 저장하려면 알림 채널 정보 수집·이용에 동의해야 해요.", "To save a Discord address, we need your agreement to the alert-channel item.")} onAgreed={() => {}} />}
    {easier && <p className={styles.note}>{t("주소를 직접 만들기 어렵다면 마이페이지의 「디스코드로 연결」을 쓰면 디스코드 창에서 서버와 채널만 고르면 돼요.", "If making the address is hard, use “Connect with Discord” on My page - just pick the server and channel in Discord's window.")}</p>}
    {error && <p id="profile-webhook-error" className={styles.failed}>{t("디스코드 웹훅 주소를 확인해 주세요. 예: https://discord.com/api/webhooks/…", "Please check the Discord webhook URL, e.g. https://discord.com/api/webhooks/…")}</p>}
    {live && saved && <label className={styles.check}><input type="checkbox" checked={remove} onChange={(event) => onRemove(event.target.checked)} />{t("등록된 웹훅 지우기", "Remove the saved webhook")}</label>}
  </div>;
}
