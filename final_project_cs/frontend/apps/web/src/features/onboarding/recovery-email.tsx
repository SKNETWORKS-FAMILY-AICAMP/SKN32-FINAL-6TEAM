"use client";

import type { RefObject } from "react";
import type { Translate } from "@/lib/i18n";
import { OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/**
 * Optional recovery email: one field and a `Continue` that works with the field empty. The address is checked only
 * when leaving (see `Onboarding`), never while typing. It is saved through `lib/contact.ts`: on the server once this
 * browser has a user key, in the meantime in this browser.
 */
export function RecoveryEmailBody({ t, value, error, input, onChange, onContinue }: {
  t: Translate; value: string; error: boolean; input: RefObject<HTMLInputElement | null>;
  onChange: (value: string) => void; onContinue: () => void;
}) {
  const describedBy = error ? "recovery-email-hint recovery-email-error" : "recovery-email-hint";
  return <form className={styles.emailForm} noValidate onSubmit={(event) => { event.preventDefault(); onContinue(); }}>
    <p className={styles.termsIntro}>{t("토큰을 잃어버렸을 때 복구에 사용할 이메일이에요.", "An email for recovering your token if you lose it.")}<br />{t("입력하지 않아도 서비스를 시작할 수 있어요.", "You can start without it.")}</p>
    <label htmlFor="recovery-email" className={styles.emailLabel}>{t("이메일", "Email")}</label>
    <input ref={input} id="recovery-email" className={styles.emailInput} type="email" inputMode="email" autoComplete="email" autoCapitalize="none" spellCheck={false}
      placeholder="example@email.com" value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={error} aria-describedby={describedBy} />
    <p id="recovery-email-hint" className={styles.emailHint}>{t("이메일 주소를 정확하게 입력했는지 확인해 주세요.", "Please check that the address is typed correctly.")}</p>
    {error && <p id="recovery-email-error" className={styles.emailError}>{t("이메일 형식을 확인해 주세요. 예: name@example.com", "Please check the email format, e.g. name@example.com")}<br />{t("입력하지 않으려면 내용을 지우고 계속할 수 있어요.", "To leave it out, clear the field and continue.")}</p>}
    <p className={styles.draftNote}>{t("마이페이지에서 언제든 추가하거나 바꿀 수 있어요. 첫 여행을 등록하면 서버에 저장돼요. 인증 메일은 보내지 않고, 복구 메일도 아직 준비 중이에요.", "You can add or change it on My page any time. It is saved to the server when you register your first trip. No verification email is sent, and recovery by email is still being prepared.")}</p>
    <button type="submit" className={`${styles.next} ${styles.emailContinue}`}>{t("계속", "Continue")}<OnboardingIcon name="arrow" size={15} /></button>
  </form>;
}
