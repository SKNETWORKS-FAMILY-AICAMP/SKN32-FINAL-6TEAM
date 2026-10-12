"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { OptionalConsentPrompt } from "@/features/consent/optional-consent-prompt";
import { TermsViewer } from "@/features/consent/terms-viewer";
import type { TermsDoc } from "@/features/consent/terms-content";
import { useT } from "@/lib/settings";
import styles from "./location-consent.module.css";

/** The existing optional consent, opened where the location tool was pressed. */
export function LocationConsent({ onAgreed, onCancel }: { onAgreed: () => void; onCancel: () => void }) {
  const [terms, setTerms] = useState<TermsDoc | null>(null);
  useLayoutEffect(() => {
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    return () => { trigger?.focus(); };
  }, []);
  // One surface at a time: the full terms replace the prompt instead of stacking dialogs.
  return terms ? <TermsViewer doc={terms} onClose={() => setTerms(null)} /> : <ConsentSheet onAgreed={onAgreed} onCancel={onCancel} onReadTerms={setTerms} />;
}

function ConsentSheet({ onAgreed, onCancel, onReadTerms }: { onAgreed: () => void; onCancel: () => void; onReadTerms: (doc: TermsDoc) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useId();
  const t = useT();
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    return () => { node?.close(); };
  }, []);
  const finish = (next: () => void) => { dialog.current?.close(); next(); };
  function keepFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab") return;
    const targets = [...event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], [tabindex="0"]')].filter(node => node.getClientRects().length > 0);
    const first = targets[0], last = targets.at(-1);
    if (!first || !last) { event.preventDefault(); return; }
    if (event.shiftKey && (document.activeElement === first || !event.currentTarget.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || !event.currentTarget.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
  }
  return <dialog ref={dialog} className={styles.dialog} aria-labelledby={title} onKeyDown={keepFocus} onCancel={event => { event.preventDefault(); finish(onCancel); }}>
    <h2 id={title}>{t("내 위치로 이동", "Go to my location")}</h2>
    <OptionalConsentPrompt code="location" why={t("지도에 내 위치를 표시하고 그곳으로 이동하려면 위치 이용 동의가 필요해요.", "To show your location and move the map there, we need your agreement to use location.")} onAgreed={() => finish(onAgreed)} onCancel={() => finish(onCancel)} onReadTerms={doc => finish(() => onReadTerms(doc))} />
  </dialog>;
}
