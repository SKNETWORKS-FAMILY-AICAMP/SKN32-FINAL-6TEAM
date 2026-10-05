"use client";

import { useEffect, useRef, type KeyboardEvent } from "react";
import { requiredAgreed, type ConsentCode, type ConsentMap } from "@/features/consent/consent-model";
import { TermsBody } from "@/features/consent/terms-body";
import { plainTitle } from "@/features/consent/terms-text";
import { DRAFT_NOTICE, TERMS_DOCS, TERMS_EFFECTIVE, TERMS_STATUS, TERMS_VERSION, type TermsDoc } from "@/features/consent/terms-content";
import type { Translate } from "@/lib/i18n";
import { DrawnCheck, OnboardingIcon } from "./icons";
import styles from "./onboarding.module.css";

/**
 * ★`[2026-10-05 사용자 지시]` 약관 동의는 한 덩어리가 아니라 **항목별**이다(`features/consent/consent-model.ts`): 필수(서비스 이용약관 · 개인정보 수집·이용)는 동의해야 앱을 쓸 수 있고,
 * 선택(민감정보 · 위치 · 알림 채널)은 거부해도 쓸 수 있다. 약관 전문은 `features/consent/terms-content.ts` 가 정본이다(한국어가 정본, 영어는 참고 번역).
 * 필수 항목은 전문을 끝까지 내려 읽어야 체크할 수 있다. 체크한 것을 기록하는 것은 「동의하고 다음으로」를 누르는 행동이다(`onboarding.tsx`).
 */
export const termsDoc = (code: ConsentCode): TermsDoc | undefined => TERMS_DOCS.find((doc) => doc.code === code);

const tagOf = (doc: TermsDoc, t: Translate) => doc.required ? t("[필수]", "[Required]") : t("[선택]", "[Optional]");
/**
 * The words next to the box. ★The personal-data item also carries the age statement: the service is closed to children under 14 (their data needs a guardian's consent),
 * and the customer confirms being 14 or older when agreeing (terms 제7조 ④) - there is no other age check in the app.
 */
const consentLine = (doc: TermsDoc, t: Translate) => `${tagOf(doc, t)} ${t(...plainTitle(doc.title))}${t("에 동의합니다.", " - I agree.")}${doc.code === "privacy" ? t(" 저는 만 14세 이상입니다.", " I am 14 or older.") : ""}`;

/** 「초안」 표시: 법무 검토와 운영 주체 정보 확정 전의 약관임을 숨기지 않는다. */
function DraftNote({ t }: { t: Translate }) {
  if (TERMS_STATUS !== "draft") return null;
  return <p className={styles.termsDraft} role="note">{t(DRAFT_NOTICE[0], DRAFT_NOTICE[1])}</p>;
}

export function TermsCardBody({ t, choices, readDocs, consentMotion, alertTyped = false, onReadDoc, onToggle, onContinue }: {
  t: Translate; choices: ConsentMap; readDocs: Partial<Record<ConsentCode, boolean>>; consentMotion: boolean;
  /** The customer typed a Discord address on the first card: it is kept only if the alert-channel item is ticked. */
  alertTyped?: boolean;
  onReadDoc: (code: ConsentCode) => void; onToggle: (code: ConsentCode, checked: boolean) => void; onContinue: () => void;
}) {
  return <>
    <p className={styles.termsIntro}>{t("여행을 시작하기 전에", "Before we begin")}</p>
    <DraftNote t={t} />
    <ul className={styles.consentList} aria-label={t("동의 항목", "Consent items")}>
      {TERMS_DOCS.map((doc) => {
        const locked = doc.required && !readDocs[doc.code];
        return <li key={doc.code} className={styles.consentItem} data-doc={doc.code}>
          <label className={styles.termsCheck}>
            <input type="checkbox" id={`consent-${doc.code}`} disabled={locked} checked={choices[doc.code]} onChange={(event) => onToggle(doc.code, event.target.checked)} />
            <span className={`${styles.consentMark} ${consentMotion && choices[doc.code] ? styles.completionMotion : ""}`} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
            <span>{consentLine(doc, t)}</span>
          </label>
          <p className={styles.consentSummary}>{t(doc.summary[0], doc.summary[1])}</p>
          {locked && <p className={styles.consentHint}>{t("전문을 끝까지 읽으면 동의할 수 있어요.", "Read the full text to the end to agree.")}</p>}
          {doc.code === "alert_channel" && alertTyped && !choices.alert_channel && <p className={styles.consentHint}>{t("앞에서 입력한 디스코드 주소는 이 항목에 동의해야 저장돼요.", "The Discord address you entered earlier is saved only if you agree to this item.")}</p>}
          <button type="button" className={styles.consentRead} data-action="read-terms" data-doc={doc.code} aria-haspopup="dialog" onClick={() => onReadDoc(doc.code)}>{t("전문 보기 ↗", "Read in full ↗")}</button>
        </li>;
      })}
    </ul>
    <button type="button" className={`${styles.next} ${styles.termsContinue}`} disabled={!requiredAgreed(choices)} onClick={onContinue}>{t("동의하고 다음으로", "Agree and continue")}<OnboardingIcon name="arrow" size={15} /></button>
  </>;
}

export function TermsReader({ t, doc, read, agreed, onRead, onAgree, onClose }: {
  t: Translate; doc: TermsDoc; read: boolean; agreed: boolean; onRead: () => void; onAgree: (checked: boolean) => void; onClose: () => void;
}) {
  const scroller = useRef<HTMLElement>(null);
  const locked = doc.required && !read;

  useEffect(() => { scroller.current?.focus(); }, []);
  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const checkEnd = () => { if (element.clientHeight > 0 && element.scrollHeight - element.scrollTop - element.clientHeight <= 3) onRead(); };
    const observer = new ResizeObserver(checkEnd);
    observer.observe(element);
    element.addEventListener("scroll", checkEnd, { passive: true });
    const frame = requestAnimationFrame(checkEnd);
    return () => { observer.disconnect(); element.removeEventListener("scroll", checkEnd); cancelAnimationFrame(frame); };
  }, [onRead]);

  function escape(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.stopPropagation(); onClose(); }
  }

  const title = t(doc.title[0], doc.title[1]);
  return <div className={styles.termsDialog} role="dialog" aria-modal="true" aria-labelledby="terms-full-title" onKeyDown={escape}>
    <header className={styles.termsHeader}>
      <div><small>{t("이용 안내", "NOTICE")} · {t(`버전 ${TERMS_VERSION} · 시행 ${TERMS_EFFECTIVE}`, `Version ${TERMS_VERSION} · effective ${TERMS_EFFECTIVE}`)}</small><h2 id="terms-full-title">{title}</h2></div>
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
        ? (read ? t("내용을 확인했어요. 동의 여부를 선택해 주세요.", "You have reached the end. You can now choose whether to agree.") : t("약관을 끝까지 내려 읽으면 동의할 수 있어요.", "Scroll to the end of the terms to enable agreement."))
        : t("선택 항목이에요. 동의하지 않아도 앱을 쓸 수 있어요.", "This is optional. You can use the app without agreeing.")}</p>
      <label className={styles.termsCheck}>
        <input type="checkbox" id="terms-full-check" disabled={locked} checked={agreed} onChange={(event) => onAgree(event.target.checked)} />
        <span className={styles.consentMark} aria-hidden="true"><DrawnCheck className={styles.drawnCheck} /></span>
        <span>{consentLine(doc, t)}</span>
      </label>
    </footer>
  </div>;
}
