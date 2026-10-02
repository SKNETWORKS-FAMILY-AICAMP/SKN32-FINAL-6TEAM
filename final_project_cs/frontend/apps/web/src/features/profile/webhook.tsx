"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, ButtonLink } from "@/components/ui";
import { discordWebhookProblem } from "@/features/onboarding/model";
import { DATA_MODE } from "@/lib/data-mode";
import type { Language, Translate } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import { getProfile, isUnsupported, testDiscordWebhook, type ServerProfile, type WebhookTestResult } from "@/lib/live/profile";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { webhookWaiting } from "@/lib/webhook";
import styles from "./profile.module.css";

export const serverProfileKey = (language: Language) => ["server-profile", language] as const;

/** The server's contact details (`GET /v1/web/profile`) — asked only in a live build with a user key: asking without one would create a user. */
export function useServerProfile(hasKey: boolean) {
  const { language } = useSettings();
  return useQuery({ queryKey: serverProfileKey(language), queryFn: () => getProfile(language), enabled: DATA_MODE === "live" && hasKey, retry: false });
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

/**
 * My page's Discord webhook row: whether one is saved (masked — the server never returns the address), whether Discord
 * took the last test, and a test message on request. Alerts about plan changes are the server's next step, not built yet.
 */
export function WebhookView({ hasKey }: { hasKey: boolean }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const profile = useServerProfile(hasKey);
  const test = useMutation({
    mutationFn: () => testDiscordWebhook(language),
    onSuccess: (answer) => queryClient.setQueryData(serverProfileKey(language), answer.profile),
  });
  const later = <span className={styles.note}>{t("일정이 바뀔 때 디스코드로 알림을 보내는 기능은 준비 중이에요.", "Alerts about plan changes through Discord are still being prepared.")}</span>;
  const add = <ButtonLink href={routes.myPageEdit} variant="quiet">{t("웹훅 등록하기", "Add a webhook")}</ButtonLink>;

  if (DATA_MODE !== "live") return <span className={styles.muted}>{t("실제 서버에 연결됐을 때만 등록할 수 있어요.", "Can be added only when connected to the real server.")}</span>;
  if (!hasKey) return <>
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
  if (!hook.set) return <><span className={styles.muted}>{t("등록된 웹훅이 없어요.", "No webhook registered.")}</span>{add}{later}</>;
  return <>
    <code className={styles.line}>{hook.masked}</code>
    {hook.status && <span className={hook.status === "invalid" ? styles.failed : styles.note}>{t(...STATUS[hook.status])}</span>}
    <Button variant="quiet" disabled={test.isPending} onClick={() => test.mutate()}>{test.isPending ? t("보내는 중…", "Sending…") : t("시험 메시지 보내기", "Send a test message")}</Button>
    <span className={test.isError || (test.data && test.data.result !== "ok") ? styles.failed : styles.note} role="status">{test.isError
      ? (test.error instanceof LiveError ? test.error.message : t("보내지 못했어요. 잠시 뒤 다시 해 보세요.", "Could not send it. Try again shortly."))
      : test.data ? testText(test.data.result, t) : ""}</span>
    {later}
  </>;
}

/** The edit screen's webhook field. Blank keeps the saved one (its address is never shown again); the box removes it. */
export function WebhookField({ hasKey, value, remove, touched, onValue, onRemove, onBlur }: {
  hasKey: boolean; value: string; remove: boolean; touched: boolean;
  onValue: (value: string) => void; onRemove: (remove: boolean) => void; onBlur: () => void;
}) {
  const t = useT();
  const profile = useServerProfile(hasKey);
  const live = DATA_MODE === "live";
  const saved = profile.data?.webhook.set ? profile.data.webhook.masked : null;
  const error = touched && !remove && Boolean(discordWebhookProblem(value));
  return <div className={styles.field}>
    <label htmlFor="profile-webhook">{t("디스코드 웹훅 URL", "Discord webhook URL")} <small>{t("(선택)", "(optional)")}</small></label>
    <input id="profile-webhook" type="url" inputMode="url" autoComplete="off" autoCapitalize="none" spellCheck={false} disabled={!live || remove}
      placeholder={saved ? t(`등록됨: ${saved}`, `Saved: ${saved}`) : "https://discord.com/api/webhooks/…"} value={value}
      onChange={(event) => onValue(event.target.value)} onBlur={onBlur}
      aria-invalid={error} aria-describedby={error ? "profile-webhook-hint profile-webhook-error" : "profile-webhook-hint"} />
    <p id="profile-webhook-hint" className={styles.note}>{!live
      ? t("실제 서버에 연결됐을 때만 등록할 수 있어요.", "Can be added only when connected to the real server.")
      : saved
        ? t("새 주소를 넣고 저장하면 바뀌어요. 비워 두면 등록된 웹훅을 그대로 둬요. 주소는 서버에만 있고 다시 보여 드리지 않아요.", "Enter a new address and save to replace it; leave it blank to keep the saved one. The address stays on the server and is not shown again.")
        : t("알림을 받을 디스코드 채널에서 만든 웹훅 주소를 붙여 넣어 주세요. 이 브라우저에는 남기지 않아요.", "Paste the webhook URL made in the Discord channel that should get the alerts. It is not kept in this browser.")}</p>
    {error && <p id="profile-webhook-error" className={styles.failed}>{t("디스코드 웹훅 주소를 확인해 주세요. 예: https://discord.com/api/webhooks/…", "Please check the Discord webhook URL, e.g. https://discord.com/api/webhooks/…")}</p>}
    {live && saved && <label className={styles.check}><input type="checkbox" checked={remove} onChange={(event) => onRemove(event.target.checked)} />{t("등록된 웹훅 지우기", "Remove the saved webhook")}</label>}
  </div>;
}
