"use client";

import type { RefObject } from "react";
import type { Translate } from "@/lib/i18n";
import { OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/**
 * Optional Discord alerts card: the webhook of the channel that should get the trip's alerts, and a `Continue` that works
 * with the field empty. `[2026-10-03 user decision]` The recovery email is gone from the product — the Discord webhook is
 * the one way to be told. The address is checked only when leaving (see `Onboarding`), never while typing. It is saved
 * through `lib/webhook.ts`: on the server once this browser has a user key, in the meantime in this page's memory only —
 * a webhook is a secret, so it never reaches this browser's storage.
 */
export function ContactBody({ t, webhook, webhookError, webhookInput, onWebhook, onContinue }: {
  t: Translate; webhook: string; webhookError: boolean;
  webhookInput: RefObject<HTMLInputElement | null>;
  onWebhook: (value: string) => void; onContinue: () => void;
}) {
  const describedBy = webhookError ? "discord-webhook-hint discord-webhook-error" : "discord-webhook-hint";
  return <form className={styles.emailForm} noValidate onSubmit={(event) => { event.preventDefault(); onContinue(); }}>
    <p className={styles.termsIntro}>{t("여행 알림을 받을 디스코드 채널의 웹훅 주소예요.", "The webhook of the Discord channel that should get your trip alerts.")}<br />{t("입력하지 않아도 서비스를 시작할 수 있어요.", "You can start without it.")}</p>
    <label htmlFor="discord-webhook" className={styles.emailLabel}>{t("디스코드 웹훅 URL", "Discord webhook URL")}</label>
    <input ref={webhookInput} id="discord-webhook" className={styles.emailInput} type="url" inputMode="url" autoComplete="off" autoCapitalize="none" spellCheck={false}
      placeholder="https://discord.com/api/webhooks/…" value={webhook} onChange={(event) => onWebhook(event.target.value)} aria-invalid={webhookError} aria-describedby={describedBy} />
    <p id="discord-webhook-hint" className={styles.emailHint}>{t("디스코드에서 채널 설정 → 연동 → 웹후크 → 새 웹후크를 만들고, 웹후크 URL 복사로 얻은 주소를 붙여 넣어 주세요.", "In Discord: channel settings → Integrations → Webhooks → New webhook, then paste the address from Copy webhook URL.")}</p>
    {webhookError && <p id="discord-webhook-error" className={styles.emailError}>{t("디스코드 웹훅 주소를 확인해 주세요. 예: https://discord.com/api/webhooks/…", "Please check the Discord webhook URL, e.g. https://discord.com/api/webhooks/…")}<br />{t("입력하지 않으려면 내용을 지우고 계속할 수 있어요.", "To leave it out, clear the field and continue.")}</p>}
    <p className={styles.draftNote}>{t("마이페이지에서 언제든 추가하거나 바꿀 수 있어요. 첫 여행을 등록하면 서버에 저장돼요. 주소는 이 브라우저에 남기지 않아서, 그 전에 새로고침하면 다시 넣어 주세요. 시험 메시지는 마이페이지에서 보낼 수 있어요.", "You can add or change it on My page any time. It is saved to the server when you register your first trip. The address is not kept in this browser, so enter it again if you reload before then. You can send a test message from My page.")}</p>
    <button type="submit" className={`${styles.next} ${styles.emailContinue}`}>{t("계속", "Continue")}<OnboardingIcon name="arrow" size={15} /></button>
  </form>;
}
