"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui";
import type { Translate } from "@/lib/i18n";
import { useSettings, useT } from "@/lib/settings";
import type { ConsentCode } from "./consent-model";
import { consentedAt, readConsents, useConsent } from "./consent-store";
import { saveConsents, type SendResult } from "./consent-sync";
import { plainTitle } from "./terms-text";
import { TermsViewer } from "./terms-viewer";
import { TERMS_EFFECTIVE, type TermsDoc } from "./terms-content";
import { useLiveTerms } from "./terms-live";
import styles from "./consent.module.css";

/** What turning an item off does - said before it is done. */
const WITHDRAW: Record<ConsentCode, [string, string]> = {
  service_terms: ["철회하면 서비스를 쓸 수 없어요. 처음 화면의 약관 동의로 돌아가요.", "If you withdraw, you can no longer use the service. You go back to the consent screen."],
  privacy: ["철회하면 서비스를 쓸 수 없어요. 처음 화면의 약관 동의로 돌아가요.", "If you withdraw, you can no longer use the service. You go back to the consent screen."],
  sensitive: ["종교·식사 제한 같은 취향 답을 서버에서 지워요. 앱은 그대로 쓸 수 있어요.", "Answers such as religion and food restrictions are deleted from the server. You can keep using the app."],
  location: ["지도에 내 위치를 그리지 않고, 서버에 있는 내 위치 기록을 지워요. 앱은 그대로 쓸 수 있어요.", "Your location is no longer drawn on the map and your location history on the server is deleted. You can keep using the app."],
  alert_channel: ["연결해 둔 디스코드·텔레그램 알림을 풀어요. 앱은 그대로 쓸 수 있어요.", "Your connected Discord/Telegram alerts are unlinked. You can keep using the app."],
};

function resultText(result: SendResult, agreed: boolean, t: Translate): { ok: boolean; text: string } {
  switch (result) {
    case "recorded": case "local_only": return { ok: true, text: agreed ? t("동의를 기록했어요.", "Your consent is recorded.") : t("동의를 철회했어요.", "Your consent is withdrawn.") };
    case "outdated": return { ok: false, text: t("약관이 새 버전으로 바뀌었어요. 화면을 새로 고침해 주세요.", "The terms have a newer version. Please reload.") };
    default: return { ok: false, text: t("서버에 기록하지 못했어요. 이 브라우저에는 저장했고, 연결되면 다시 보내요.", "Could not record it on the server. It is saved in this browser and will be sent again when connected.") };
  }
}

function Row({ doc, onView }: { doc: TermsDoc; onView: (doc: TermsDoc) => void }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const agreed = useConsent(doc.code);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const at = agreed ? consentedAt() : null;

  async function change(next: boolean) {
    setBusy(true);
    setMessage(null);
    setConfirming(false);
    try {
      const result = await saveConsents({ ...readConsents(), [doc.code]: next }, language);
      setMessage(resultText(result, next, t));
      // A withdrawn item takes its data with it (a webhook, a chat link, answers): the lists that show them are read again.
      void queryClient.invalidateQueries();
    } finally { setBusy(false); }
  }

  return <li className={styles.item} data-doc={doc.code}>
    <div className={styles.itemHead}>
      <span className={styles.itemName}><span className={styles.itemTag} data-required={doc.required || undefined}>{doc.required ? t("[필수]", "[Required]") : t("[선택]", "[Optional]")}</span>{t(...plainTitle(doc.title))}</span>
      <span className={styles.itemState}>{agreed ? t(`동의함${at ? ` · ${at.slice(0, 10)}` : ""}`, `Agreed${at ? ` · ${at.slice(0, 10)}` : ""}`) : t("동의 안 함", "Not agreed")}</span>
    </div>
    <p className={styles.managerNote}>{t(doc.summary[0], doc.summary[1])}</p>
    {confirming && <p className={styles.failed} role="alert">{t(...WITHDRAW[doc.code])}</p>}
    <div className={styles.itemActions}>
      <Button variant="quiet" onClick={() => onView(doc)}>{t("전문 보기", "Read in full")}</Button>
      {agreed
        ? (confirming
          ? <><Button variant="primary" disabled={busy} onClick={() => void change(false)}>{t("철회하기", "Withdraw")}</Button><Button disabled={busy} onClick={() => setConfirming(false)}>{t("취소", "Cancel")}</Button></>
          : <Button variant="quiet" disabled={busy} onClick={() => setConfirming(true)}>{t("동의 철회", "Withdraw")}</Button>)
        : !doc.required && <Button disabled={busy} onClick={() => void change(true)}>{t("동의하기", "Agree")}</Button>}
    </div>
    {message && <p className={message.ok ? styles.ok : styles.failed} role={message.ok ? "status" : "alert"}>{message.text}</p>}
  </li>;
}

/**
 * `[2026-10-05 사용자 지시]` 마이페이지 「동의 관리」: 어떤 항목에 동의했는지 보고, 약관 전문을 다시 읽고, 선택 항목은 언제든 켜고 끈다(필수 항목의 철회는 서비스 중단이라
 * 한 번 더 확인한다). 바꾼 것은 이 브라우저와 서버의 동의 기록(추가만 하는 표)에 함께 남는다.
 */
export function ConsentManager() {
  const t = useT();
  const [viewing, setViewing] = useState<TermsDoc | null>(null);
  const { version, docs } = useLiveTerms(useSettings().language);
  if (!docs.length) return null;
  return <div className={styles.manager} id="consents">
    <h2 className={styles.managerTitle}>{t("약관 동의 관리", "Manage consents")}</h2>
    <p className={styles.managerNote}>{t(`약관 버전 ${version} (시행 ${TERMS_EFFECTIVE}). 선택 항목은 동의하지 않아도 앱을 쓸 수 있고, 언제든 철회할 수 있어요.`, `Terms version ${version} (effective ${TERMS_EFFECTIVE}). Optional items can be declined without losing the app, and withdrawn at any time.`)}</p>
    <ul className={styles.items} aria-label={t("동의 항목", "Consent items")}>{docs.map((doc) => <Row key={doc.code} doc={doc} onView={setViewing} />)}</ul>
    {viewing && <TermsViewer doc={viewing} onClose={() => setViewing(null)} />}
  </div>;
}
