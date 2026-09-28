"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui";
import { adoptKey, currentKey, KEY_CHANGED_EVENT, LiveError, rotateKey } from "@/lib/live/client";
import { useSettings, useT } from "@/lib/settings";
import { KeyNotice } from "./key-notice";
import styles from "./account.module.css";

/**
 * The settings-menu part of the key (D-021 §4): use a key you already have, or replace a key you think leaked.
 * ★Replacing is not undoable — the old key stops working at once — so it takes a second, explicit click.
 */
export function KeySettings() {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [hasKey, setHasKey] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  // ★The new key is shown right here, in the menu where it was replaced. The intro and onboarding frame has no
  //   page notice, so "copy it from the notice at the top" pointed at nothing there (found 2026-09-28 on the real server).
  const [rotated, setRotated] = useState(false);

  useEffect(() => {
    const read = () => setHasKey(Boolean(currentKey()));
    read();
    window.addEventListener(KEY_CHANGED_EVENT, read);
    return () => window.removeEventListener(KEY_CHANGED_EVENT, read);
  }, []);

  const reason = (error: unknown) => error instanceof LiveError || error instanceof Error ? error.message : String(error);

  async function use(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await adoptKey(input, language);
      setInput("");
      setMessage({ ok: true, text: t("이 키로 바꿨어요. 이 키의 여행을 다시 불러와요.", "Switched to this key. Reloading its trips.") });
      void queryClient.invalidateQueries();
    } catch (error) {
      setMessage({ ok: false, text: reason(error) });
    } finally { setBusy(false); }
  }

  async function replace() {
    setBusy(true);
    setMessage(null);
    try {
      await rotateKey(language);
      setConfirming(false);
      setRotated(true);
      setMessage({ ok: true, text: t("새 키를 받았어요. 아래 안내에서 복사해 따로 보관해 주세요.", "You have a new key. Copy it from the notice below and keep it safe.") });
      void queryClient.invalidateQueries();
    } catch (error) {
      setMessage({ ok: false, text: reason(error) });
    } finally { setBusy(false); }
  }

  return <fieldset className={styles.group}>
    <legend>{t("내 사용자 키", "Your user key")}</legend>
    <form onSubmit={(event) => void use(event)} className={styles.row}>
      <label htmlFor="user-key-input">{t("이미 가진 키로 열기", "Open with a key you already have")}</label>
      <input id="user-key-input" type="text" className={styles.keybox} value={input} autoComplete="off" spellCheck={false}
        placeholder="acop_u_…" onChange={(event) => setInput(event.target.value)} />
      <Button type="submit" disabled={busy || !input.trim()}>{t("이 키로 열기", "Open")}</Button>
    </form>
    {hasKey && <div className={styles.row}>
      {confirming
        ? <>
          <p className={styles.warn}>{t("옛 키는 바로 쓸 수 없게 돼요. 새 키를 따로 보관하지 않으면 다른 기기에서 이 여행을 열 수 없어요. 계속할까요?", "The old key stops working at once. If you do not keep the new key, you cannot open these trips on another device. Continue?")}</p>
          <div className={styles.actions}>
            <Button variant="primary" disabled={busy} onClick={() => void replace()}>{t("키 다시 발급", "Replace my key")}</Button>
            <Button disabled={busy} onClick={() => setConfirming(false)}>{t("취소", "Cancel")}</Button>
          </div>
        </>
        : <Button disabled={busy} onClick={() => setConfirming(true)}>{t("키가 샜어요 — 다시 발급받기", "My key leaked — replace it")}</Button>}
    </div>}
    {message && <p className={message.ok ? styles.ok : styles.error} role={message.ok ? "status" : "alert"}>{message.text}</p>}
    {rotated && <KeyNotice />}
  </fieldset>;
}
