"use client";

import { useState } from "react";
import { Button } from "@/components/ui";
import { useSettings, useT } from "@/lib/settings";
import type { ConsentCode } from "./consent-model";
import { readConsents } from "./consent-store";
import { saveConsents } from "./consent-sync";
import { TERMS_DOCS } from "./terms-content";
import { plainTitle } from "./terms-text";
import { TermsViewer } from "./terms-viewer";
import styles from "./consent.module.css";

/**
 * `[2026-10-05 사용자 지시]` 선택 동의가 필요한 일을 하려는 순간(위치로 묻기 · 알림 채널 연결) 그 자리에서 동의를 받는다. 선택 동의는 거부해도 앱을 쓸 수 있으므로
 * 약관 화면에서 묻지 않은 항목은 이렇게 **필요해질 때** 묻는다: 왜 필요한지 한 줄 · 전문 보기 · 동의하고 계속 / 그만두기. 동의하면 브라우저와 서버 기록에 남고 `onAgreed` 로 이어 간다.
 */
export function OptionalConsentPrompt({ code, why, onAgreed, onCancel }: { code: ConsentCode; why: string; onAgreed: () => void; onCancel?: () => void }) {
  const t = useT();
  const { language } = useSettings();
  const doc = TERMS_DOCS.find((entry) => entry.code === code);
  const [reading, setReading] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!doc) return null;

  async function agree() {
    setBusy(true);
    try {
      await saveConsents({ ...readConsents(), [code]: true }, language);       // 서버에 못 보내도 이 브라우저에는 남고 나중에 다시 보낸다
      onAgreed();
    } finally { setBusy(false); }
  }

  return <div className={styles.prompt} role="group" aria-label={t(`${plainTitle(doc.title)[0]} 동의`, `${plainTitle(doc.title)[1]} consent`)}>
    <p className={styles.promptText}><span className={styles.itemTag}>{t("[선택]", "[Optional]")}</span>{why}</p>
    <p className={styles.managerNote}>{t("동의하지 않아도 앱은 그대로 쓸 수 있어요. 동의는 마이페이지에서 언제든 철회할 수 있어요.", "You can keep using the app without agreeing, and withdraw this on My page at any time.")}</p>
    <div className={styles.itemActions}>
      <Button variant="quiet" onClick={() => setReading(true)}>{t("전문 보기", "Read in full")}</Button>
      <Button variant="primary" disabled={busy} onClick={() => void agree()}>{busy ? t("기록하는 중…", "Recording…") : t(`${plainTitle(doc.title)[0]}에 동의하고 계속`, `Agree to ${plainTitle(doc.title)[1]} and continue`)}</Button>
      {onCancel && <Button disabled={busy} onClick={onCancel}>{t("그만두기", "Not now")}</Button>}
    </div>
    {reading && <TermsViewer doc={doc} onClose={() => setReading(false)} />}
  </div>;
}
