"use client";

import type { RefObject } from "react";
import type { Translate } from "@/lib/i18n";
import { OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/**
 * Optional alerts & recovery card: a recovery email, a Discord webhook for trip alerts, and a `Continue` that works with
 * both fields empty. The values are checked only when leaving (see `Onboarding`), never while typing. The email is saved
 * through `lib/contact.ts` (on the server once this browser has a user key, in the meantime in this browser); the webhook
 * is not saved — that is the backend's part.
 */
export function ContactBody({ t, email, webhook, emailError, webhookError, emailInput, webhookInput, onEmail, onWebhook, onContinue }: {
  t: Translate; email: string; webhook: string; emailError: boolean; webhookError: boolean;
  emailInput: RefObject<HTMLInputElement | null>; webhookInput: RefObject<HTMLInputElement | null>;
  onEmail: (value: string) => void; onWebhook: (value: string) => void; onContinue: () => void;
}) {
  const emailDescribedBy = emailError ? "recovery-email-hint recovery-email-error" : "recovery-email-hint";
  const webhookDescribedBy = webhookError ? "discord-webhook-hint discord-webhook-error" : "discord-webhook-hint";
  return <form className={styles.emailForm} noValidate onSubmit={(event) => { event.preventDefault(); onContinue(); }}>
    <p className={styles.termsIntro}>{t("토큰 복구에 쓸 이메일과 여행 알림을 받을 디스코드 웹훅이에요.", "An email for recovering your token and a Discord webhook for trip alerts.")}<br />{t("입력하지 않아도 서비스를 시작할 수 있어요.", "You can start without them.")}</p>
    <label htmlFor="recovery-email" className={styles.emailLabel}>{t("복구용 이메일", "Recovery email")}</label>
    <input ref={emailInput} id="recovery-email" className={styles.emailInput} type="email" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false}
      placeholder="example@email.com" value={email} onChange={(event) => onEmail(event.target.value)} aria-invalid={emailError} aria-describedby={emailDescribedBy} />
    <p id="recovery-email-hint" className={styles.emailHint}>{t("이메일 주소를 정확하게 입력했는지 확인해 주세요.", "Please check that the address is typed correctly.")}</p>
    {emailError && <p id="recovery-email-error" className={styles.emailError}>{t("이메일 형식을 확인해 주세요. 예: name@example.com", "Please check the email format, e.g. name@example.com")}<br />{t("입력하지 않으려면 내용을 지우고 계속할 수 있어요.", "To leave it out, clear the field and continue.")}</p>}
    <label htmlFor="discord-webhook" className={`${styles.emailLabel} ${styles.webhookLabel}`}>{t("디스코드 웹훅 URL", "Discord webhook URL")}</label>
    <input ref={webhookInput} id="discord-webhook" className={styles.emailInput} type="url" inputMode="url" autoComplete="off" autoCapitalize="none" spellCheck={false}
      placeholder="https://discord.com/api/webhooks/…" value={webhook} onChange={(event) => onWebhook(event.target.value)} aria-invalid={webhookError} aria-describedby={webhookDescribedBy} />
    <p id="discord-webhook-hint" className={styles.emailHint}>{t("알림을 받을 디스코드 채널에서 만든 웹훅 주소를 붙여 넣어 주세요.", "Paste the webhook URL made in the Discord channel that should get the alerts.")}</p>
    {webhookError && <p id="discord-webhook-error" className={styles.emailError}>{t("디스코드 웹훅 주소를 확인해 주세요. 예: https://discord.com/api/webhooks/…", "Please check the Discord webhook URL, e.g. https://discord.com/api/webhooks/…")}<br />{t("입력하지 않으려면 내용을 지우고 계속할 수 있어요.", "To leave it out, clear the field and continue.")}</p>}
    <p className={styles.draftNote}>{t("마이페이지에서 언제든 추가하거나 바꿀 수 있어요. 첫 여행을 등록하면 서버에 저장돼요. 인증 메일은 보내지 않고, 복구 메일도 아직 준비 중이에요.", "You can add or change it on My page any time. It is saved to the server when you register your first trip. No verification email is sent, and recovery by email is still being prepared.")}<br />{t("디스코드 웹훅은 아직 저장하지 않고, 알림도 보내지 않아요.", "The Discord webhook is not saved yet, and no alert is sent.")}</p>
    <button type="submit" className={`${styles.next} ${styles.emailContinue}`}>{t("계속", "Continue")}<OnboardingIcon name="arrow" size={15} /></button>
  </form>;
}
