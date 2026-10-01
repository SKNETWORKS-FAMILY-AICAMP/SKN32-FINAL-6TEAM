"use client";

import { useEffect, useId, useState } from "react";
import { KeyRound } from "lucide-react";
import { Button, Panel } from "@/components/ui";
import { currentKey, dismissKeyNotice, isKeyTemporary, KEY_CHANGED_EVENT, pendingKeyNotice } from "@/lib/live/client";
import { useT } from "@/lib/settings";
import styles from "./account.module.css";

/**
 * Shown once, right after a key was issued or rotated (D-020, D-021 §4): the key is the only way back into the
 * customer's trips on another device, and the server cannot show it again. The sentence is the server's own.
 */
export function KeyNotice() {
  const t = useT();
  const [state, setState] = useState<{ key: string; notice: string | null; temporary: boolean } | null>(null);
  const [copy, setCopy] = useState<"failed" | "done" | null>(null);
  // The page and the menu can both show it at once, so the heading id must be unique.
  const titleId = useId();

  useEffect(() => {
    const read = () => {
      const pending = pendingKeyNotice();
      const key = currentKey();
      setState(pending && key ? { key, notice: pending.notice, temporary: isKeyTemporary() } : null);
    };
    read();
    window.addEventListener(KEY_CHANGED_EVENT, read);
    return () => window.removeEventListener(KEY_CHANGED_EVENT, read);
  }, []);

  if (!state) return null;

  async function copyKey() {
    try { await navigator.clipboard.writeText(state?.key ?? ""); setCopy("done"); }
    catch { setCopy("failed"); }
  }

  return <Panel className={styles.notice} role="status" aria-labelledby={titleId}>
    <h2 id={titleId}><KeyRound size={18} strokeWidth={1.6} aria-hidden="true" />{t("내 여행 열쇠를 따로 보관해 주세요", "Keep your trip key somewhere safe")}</h2>
    <p>{state.notice ?? t("이 키가 있어야 다른 기기에서 내 여행을 다시 열 수 있어요.", "You need this key to open your trips again on another device.")}</p>
    {state.temporary && <p className={styles.error} role="alert">{t("브라우저에 키를 저장하지 못했어요. 새로고침하거나 창을 닫으면 이 키를 잃을 수 있으니 지금 복사해 따로 보관해 주세요.", "Your browser could not save the key. You may lose it when you reload or close this page. Copy it somewhere safe now.")}</p>}
    <input className={styles.keybox} readOnly value={state.key} aria-label={t("내 사용자 키", "Your user key")} onFocus={(event) => event.currentTarget.select()} />
    <div className={styles.actions}>
      <Button onClick={() => void copyKey()}>{copy === "done" ? t("복사했어요", "Copied") : t("키 복사", "Copy key")}</Button>
      <Button variant="primary" onClick={dismissKeyNotice}>{t("따로 보관했어요", "I saved it")}</Button>
    </div>
    {copy === "failed" && <p className={styles.error} role="alert">{t("복사하지 못했어요. 위 키를 눌러 선택한 뒤 직접 복사해 주세요.", "Could not copy. Select the key above and copy it yourself.")}</p>}
  </Panel>;
}
