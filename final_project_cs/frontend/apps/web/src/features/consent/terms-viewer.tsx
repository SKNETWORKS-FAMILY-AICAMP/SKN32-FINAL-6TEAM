"use client";

import { useEffect, useRef } from "react";
import { useT } from "@/lib/settings";
import { TermsBody } from "./terms-body";
import { DRAFT_NOTICE, TERMS_EFFECTIVE, TERMS_STATUS, TERMS_VERSION, type TermsDoc } from "./terms-content";
import styles from "./consent.module.css";

/** The full text of one document, read-only (no checkbox): from My page the customer only looks or changes their mind. */
export function TermsViewer({ doc, onClose }: { doc: TermsDoc; onClose: () => void }) {
  const t = useT();
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => { closeButton.current?.focus(); }, []);
  return <div className={styles.viewer} role="dialog" aria-modal="true" aria-labelledby="consent-viewer-title" onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); onClose(); } }}>
    <header className={styles.viewerHead}>
      <div><small>{t(`버전 ${TERMS_VERSION} · 시행 ${TERMS_EFFECTIVE}`, `Version ${TERMS_VERSION} · effective ${TERMS_EFFECTIVE}`)}</small><h2 id="consent-viewer-title">{t(doc.title[0], doc.title[1])}</h2></div>
      <button ref={closeButton} type="button" className={styles.viewerClose} aria-label={t("약관 닫기", "Close terms")} onClick={onClose}>×</button>
    </header>
    <article className={styles.viewerBody} tabIndex={0} aria-label={t("약관 전체 내용", "Full terms")}>
      {TERMS_STATUS === "draft" && <p className={styles.draft} role="note">{t(DRAFT_NOTICE[0], DRAFT_NOTICE[1])}</p>}
      <p>{t("한국어 약관이 정본이고, 영어는 참고용 번역이에요.", "The Korean text is the binding version; the English is a courtesy translation.")}</p>
      <TermsBody doc={doc} t={t} />
    </article>
  </div>;
}
