"use client";

import type { RefObject } from "react";
import type { Translate } from "@/lib/i18n";
import { OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/**
 * Optional recovery email: one field and a `Continue` that works with the field empty. The address is checked only
 * when leaving (see `Onboarding`), never while typing. Nothing is saved or sent — there is no server call for it yet.
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
    <p className={styles.draftNote}>{t("지금은 이 화면에서만 기억하고 서버에 저장하지 않아요. 인증 메일도 보내지 않아요.", "For now it is kept on this screen only and not saved to the server. No verification email is sent.")}</p>
    <button type="submit" className={`${styles.next} ${styles.emailContinue}`}>{t("계속", "Continue")}<OnboardingIcon name="arrow" size={15} /></button>
  </form>;
}
