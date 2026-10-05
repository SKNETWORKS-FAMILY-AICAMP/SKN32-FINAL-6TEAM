"use client";

import { useT } from "@/lib/settings";
import styles from "./google-button.module.css";

/**
 * `[2026-10-05 사용자 지시]` 「구글 로그인은 구글이 주는 공식 버튼으로」 - the "Sign in with Google" button of Google's own button generator
 * (developers.google.com/identity/branding-guidelines). Its markup and its "G" are Google's, unchanged (see `google-button.module.css`).
 *
 * ★The sign-in itself is still ours (`startSocial` - the server sends the browser to Google); Google's rules allow the HTML button for that.
 *   Google's script button (`accounts.google.com/gsi/client`) hands the page an ID token instead and would need another server call.
 * ★The text is one Google allows: "Sign in with Google" / "Continue with Google" (a translation is allowed). 「연결」 (link) uses "Continue",
 *   because nothing is being signed into - the session stays and the account is added to it.
 */
export function GoogleButton({ mode, disabled, onClick }: { mode: "login" | "link"; disabled?: boolean; onClick: () => void }) {
  const t = useT();
  const label = mode === "login" ? t("Google 계정으로 로그인", "Sign in with Google") : t("Google 계정으로 계속", "Continue with Google");
  return <button type="button" className={styles.button} disabled={disabled} onClick={onClick} data-provider-button="google">
    <div className={styles.state} />
    <div className={styles.wrapper}>
      <div className={styles.icon} aria-hidden="true">
        <svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" xmlnsXlink="http://www.w3.org/1999/xlink" style={{ display: "block" }}>
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
          <path fill="none" d="M0 0h48v48H0z" />
        </svg>
      </div>
      <span className={styles.contents}>{label}</span>
    </div>
  </button>;
}
