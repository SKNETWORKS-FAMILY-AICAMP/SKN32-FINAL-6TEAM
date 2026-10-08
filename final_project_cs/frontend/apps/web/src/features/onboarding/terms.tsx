"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import { requiredAgreed, type ConsentCode, type ConsentMap } from "@/features/consent/consent-model";
import { TermsBody } from "@/features/consent/terms-body";
import { plainTitle } from "@/features/consent/terms-text";
import { DRAFT_NOTICE, TERMS_EFFECTIVE, TERMS_STATUS, type TermsDoc } from "@/features/consent/terms-content";
import { termsDocs, useLiveTerms } from "@/features/consent/terms-live";
import { useSettings } from "@/lib/settings";
import type { Translate } from "@/lib/i18n";
import { DrawnCheck, OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/**
 * ★`[2026-10-05 사용자 지시]` 약관 동의는 한 덩어리가 아니라 **항목별**이다(`features/consent/consent-model.ts`): 필수(서비스 이용약관 · 개인정보 수집·이용)는 동의해야 앱을 쓸 수 있고,
 * 선택(민감정보 · 위치 · 알림 채널)은 거부해도 쓸 수 있다. 약관 전문은 `features/consent/terms-content.ts` 가 정본이다(한국어가 정본, 영어는 참고 번역).
 * `[2026-10-05 사용자 지시]` 필수 항목도 **바로 체크할 수 있다**(전문을 끝까지 읽어야 한다는 잠금을 뺐다). 카드마다 전문이 상자 안에 있어 그 자리에서 내려 읽을 수 있고,
 * 「전문 보기」는 같은 글을 크게 보여 줄 뿐이다. 체크한 것을 기록하는 것은 「동의하고 다음으로」를 누르는 행동이다(`onboarding.tsx`).
 */
/** `[2026-10-07]` 보관 기간 문장은 cs 프로젝트 서버가 준 것으로 조립한 판(`terms-live.ts`) — 못 읽었으면 웹에 실린 기본값. */
export const termsDoc = (code: ConsentCode): TermsDoc | undefined => termsDocs().find((doc) => doc.code === code);

const tagOf = (doc: TermsDoc, t: Translate) => doc.required ? t("[필수]", "[Required]") : t("[선택]", "[Optional]");
/**
 * The words next to the box. ★The personal-data item also carries the age statement: the service is closed to children under 14 (their data needs a guardian's consent),
 * and the customer confirms being 14 or older when agreeing (terms 제7조 ④) - there is no other age check in the app.
 */
const consentLine = (doc: TermsDoc, t: Translate) => `${tagOf(doc, t)} ${t(...plainTitle(doc.title))}${t("에 동의합니다.", " - I agree.")}${doc.code === "privacy" ? t(" 저는 만 14세 이상입니다.", " I am 14 or older.") : ""}`;

/** 「초안」 표시: 변호사 검토와 보관 기간 확정 전의 약관임을 숨기지 않는다(법령 조문은 확인함 — `terms-content.ts` 의 `DRAFT_NOTICE`). */
function DraftNote({ t }: { t: Translate }) {
  if (TERMS_STATUS !== "draft") return null;
  return <p className={styles.termsDraft} role="note">{t(DRAFT_NOTICE[0], DRAFT_NOTICE[1])}</p>;
}

export function TermsCardBody({ t, choices, consentMotion, alertTyped = false, onReadDoc, onToggle, onContinue }: {
  t: Translate; choices: ConsentMap; consentMotion: boolean;
  /** The customer typed a Discord address on the first card: it is kept only if the alert-channel item is ticked. */
  alertTyped?: boolean;
  onReadDoc: (code: ConsentCode) => void; onToggle: (code: ConsentCode, checked: boolean) => void; onContinue: () => void;
}) {
  const { docs } = useLiveTerms(useSettings().language);
  return <>
    <p className={styles.termsIntro}>{t("여행을 시작하기 전에", "Before we begin")}</p>
    <DraftNote t={t} />
    <ul className={styles.consentList} aria-label={t("동의 항목", "Consent items")}>
      {docs.map((doc) => {
        return <li key={doc.code} className={styles.consentItem} data-doc={doc.code}>
          <label className={styles.termsCheck}>
            <input type="checkbox" id={`consent-${doc.code}`} checked={choices[doc.code]} onChange={(event) => onToggle(doc.code, event.target.checked)} />
            <span className={`${styles.consentMark} ${consentMotion && choices[doc.code] ? styles.completionMotion : ""}`} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
            <span>{consentLine(doc, t)}</span>
          </label>
          <p className={styles.consentSummary}>{t(doc.summary[0], doc.summary[1])}</p>
          {/* The whole text, right here, in a box that scrolls on its own (no need to open anything to read it). */}
          <div className={styles.consentText} role="region" tabIndex={0} aria-label={t(`${plainTitle(doc.title)[0]} 전문`, `${plainTitle(doc.title)[1]} - full text`)}><TermsBody doc={doc} t={t} /></div>
          {doc.code === "alert_channel" && alertTyped && !choices.alert_channel && <p className={styles.consentHint}>{t("앞에서 입력한 디스코드 주소는 이 항목에 동의해야 저장돼요.", "The Discord address you entered earlier is saved only if you agree to this item.")}</p>}
          <button type="button" className={styles.consentRead} data-action="read-terms" data-doc={doc.code} aria-haspopup="dialog" onClick={() => onReadDoc(doc.code)}>{t("전문 보기 ↗", "Read in full ↗")}</button>
        </li>;
      })}
    </ul>
    <button type="button" className={`${styles.next} ${styles.termsContinue}`} disabled={!requiredAgreed(choices)} onClick={onContinue}>{t("동의하고 다음으로", "Agree and continue")}<OnboardingIcon name="arrow" size={15} /></button>
  </>;
}

/** The same text, enlarged (`[2026-10-05]` nothing has to be read to the end here: the box can be ticked at once). */
export function TermsReader({ t, doc, agreed, onAgree, onClose }: {
  t: Translate; doc: TermsDoc; agreed: boolean; onAgree: (checked: boolean) => void; onClose: () => void;
}) {
  const scroller = useRef<HTMLElement>(null);
  const { version } = useLiveTerms(useSettings().language);

  useEffect(() => { scroller.current?.focus(); }, []);

  function escape(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.stopPropagation(); onClose(); }
  }

  const title = t(doc.title[0], doc.title[1]);
  return <div className={styles.termsDialog} role="dialog" aria-modal="true" aria-labelledby="terms-full-title" onKeyDown={escape}>
    <header className={styles.termsHeader}>
      <div><small>{t("이용 안내", "NOTICE")} · {t(`버전 ${version} · 시행 ${TERMS_EFFECTIVE}`, `Version ${version} · effective ${TERMS_EFFECTIVE}`)}</small><h2 id="terms-full-title">{title}</h2></div>
      <button type="button" className={styles.termsClose} aria-label={t("약관 닫기", "Close terms")} onClick={onClose}>×</button>
    </header>
    <article ref={scroller} className={styles.termsScroll} tabIndex={0} aria-label={t("약관 전체 내용", "Full terms")}>
      <DraftNote t={t} />
      <p>{t("한국어 약관이 정본이고, 영어는 참고용 번역이에요.", "The Korean text is the binding version; the English is a courtesy translation.")}</p>
      <TermsBody doc={doc} t={t} />
      <p className={styles.termsEnd}>{t("약관 내용의 끝입니다.", "You have reached the end of the terms.")}</p>
    </article>
    <footer className={styles.termsFooter}>
      <p id="terms-read-hint" role="status">{doc.required
        ? t("필수 항목이에요. 동의 여부를 선택해 주세요.", "This is required. Please choose whether to agree.")
        : t("선택 항목이에요. 동의하지 않아도 앱을 쓸 수 있어요.", "This is optional. You can use the app without agreeing.")}</p>
      <label className={styles.termsCheck}>
        <input type="checkbox" id="terms-full-check" checked={agreed} onChange={(event) => onAgree(event.target.checked)} />
        <span className={styles.consentMark} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
        <span>{consentLine(doc, t)}</span>
      </label>
    </footer>
  </div>;
}
