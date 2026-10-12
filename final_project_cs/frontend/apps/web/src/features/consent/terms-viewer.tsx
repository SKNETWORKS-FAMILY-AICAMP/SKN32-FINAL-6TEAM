"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useSettings, useT } from "@/lib/settings";
import { TermsBody } from "./terms-body";
import { DRAFT_NOTICE, TERMS_EFFECTIVE, TERMS_STATUS, type TermsDoc } from "./terms-content";
import { useLiveTerms } from "./terms-live";
import { plainTitle } from "./terms-text";
import styles from "./consent.module.css";

/** The full text of one document, read-only (no checkbox): from My page the customer only looks or changes their mind. */
export function TermsViewer({ doc, documents, onClose }: { doc: TermsDoc; documents?: readonly TermsDoc[]; onClose: () => void }) {
  const t = useT();
  const { version } = useLiveTerms(useSettings().language);
  const [selected, setSelected] = useState(doc.code);
  const current = documents?.find((entry) => entry.code === selected) ?? doc;
  const multiple = (documents?.length ?? 0) > 1;
  const dialog = useRef<HTMLDialogElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const node = dialog.current;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    node?.showModal();
    closeButton.current?.focus();
    return () => { node?.close(); trigger?.focus({ preventScroll: true }); };
  }, []);
  function keepFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;
    const node = event.currentTarget;
    // Native modal dialogs block background controls, but Chrome may still tab into its browser chrome.
    const targets = [...node.querySelectorAll<HTMLElement>('a[href], button, input, select, textarea, [tabindex], [contenteditable="true"]')]
      .filter((element) => element.tabIndex >= 0 && !element.matches(":disabled") && element.getClientRects().length > 0);
    const first = targets[0];
    const last = targets.at(-1);
    if (!first || !last) { event.preventDefault(); return; }
    const active = document.activeElement;
    if (event.shiftKey && (active === first || !node.contains(active))) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && (active === last || !node.contains(active))) {
      event.preventDefault(); first.focus();
    }
  }
  return <dialog ref={dialog} className={styles.viewer} aria-modal="true" aria-labelledby="consent-viewer-title" onKeyDown={keepFocus} onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <header className={styles.viewerHead}>
      <div><small>{t(`버전 ${version} · 시행 ${TERMS_EFFECTIVE}`, `Version ${version} · effective ${TERMS_EFFECTIVE}`)}</small><h2 id="consent-viewer-title">{multiple ? t("약관 전문", "Full terms") : t(current.title[0], current.title[1])}</h2></div>
      <button ref={closeButton} type="button" className={styles.viewerClose} aria-label={t("약관 닫기", "Close terms")} onClick={onClose}>×</button>
    </header>
    {multiple && <nav className={styles.viewerDocs} aria-label={t("필수 약관 선택", "Choose required terms")}>
      {documents!.map((entry) => <button key={entry.code} type="button" aria-pressed={entry.code === current.code} onClick={() => setSelected(entry.code)}>{t(...plainTitle(entry.title))}</button>)}
    </nav>}
    <article key={current.code} className={styles.viewerBody} tabIndex={0} aria-label={t("약관 전체 내용", "Full terms")}>
      {TERMS_STATUS === "draft" && <p className={styles.draft} role="note">{t(DRAFT_NOTICE[0], DRAFT_NOTICE[1])}</p>}
      <p>{t("한국어 약관이 정본이고, 영어는 참고용 번역이에요.", "The Korean text is the binding version; the English is a courtesy translation.")}</p>
      {multiple && <h3>{t(...plainTitle(current.title))}</h3>}
      <TermsBody doc={current} t={t} />
    </article>
  </dialog>;
}
