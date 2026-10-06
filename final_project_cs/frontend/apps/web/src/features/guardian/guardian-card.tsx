"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { useT } from "@/lib/settings";
import styles from "./guardian-card.module.css";

/** 항로 지킴이 (Course Keeper): the shield with a route arrow, as the mockup draws it. */
export function ShieldIcon({ size = 24 }: { size?: number }) {
  return <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    <path d="M12 2.8 20 6v5.4c0 4.8-3.2 8-8 9.8-4.8-1.8-8-5-8-9.8V6Z" /><path d="M8 16c0-2.5 6-2 6-5V8m-2 2 2-2 2 2" /></svg>;
}

/** `start`: 「계획 확인하기」 was pressed, before the plan is read. `notice`: a notification link (`?guardian=on`) or the icon that is off - the same card, one line less. */
export type GuardianCardKind = "start" | "notice";

const LEAVE_MS = 150;

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 · 목업 v9]` The card that asks whether the Course Keeper is on. It stands over the screen (a dialog): top right on a wide screen, a sheet from below on a narrow one
 * (by the width of its own layer). The words are the mockup's, letter for letter; nothing here promises a number.
 *
 * - It opens with the focus on the TITLE (not on a button), so pressing Enter by reflex does not turn anything on.
 * - Esc, pressing outside, and the close button leave without deciding anything, and the focus goes back to what opened it. Esc does not wait for the movement to end.
 * - Tab goes round inside it; what is behind it is `inert` while it is open.
 * The parent shows it only while it is wanted and takes it away when `onClose` is called (after the leaving movement, or at once for Esc).
 */
export function GuardianCard({ kind, onPrimary, onSecondary, onClose }: { kind: GuardianCardKind; onPrimary: () => void; onSecondary: () => void; onClose: () => void }) {
  const t = useT();
  const start = kind === "start";
  const [shown, setShown] = useState(false);
  const layer = useRef<HTMLDivElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const opener = useRef<Element | null>(null);
  const leaving = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const titleId = useId(), leadId = useId();

  useEffect(() => {
    opener.current = document.activeElement;
    const frame = requestAnimationFrame(() => setShown(true));
    title.current?.focus({ preventScroll: true });
    // What is behind the card cannot be reached while it is open (the keyboard, a screen reader).
    const behind = Array.from(document.body.children).filter((element) => element !== layer.current && !element.matches("script, [data-guardian-keep]")) as HTMLElement[];
    const was = behind.map((element) => element.inert);
    behind.forEach((element) => { element.inert = true; });
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(leaving.current);
      behind.forEach((element, index) => { element.inert = was[index]; });
      const back = opener.current;
      if (back instanceof HTMLElement && document.contains(back)) back.focus({ preventScroll: true });
    };
  }, []);

  /** Leave without deciding anything: slide away, then the parent takes the card out. `wait` is 0 for Esc. */
  function dismiss(wait = LEAVE_MS) {
    if (!wait) { onClose(); return; }
    setShown(false);
    leaving.current = setTimeout(onClose, wait);
  }

  function keys(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); dismiss(0); return; }
    if (event.key !== "Tab") return;
    const stops = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("button")).filter((element) => !element.hasAttribute("disabled"));
    if (!stops.length) return;
    const first = stops[0], last = stops[stops.length - 1], at = document.activeElement;
    if (event.shiftKey && (at === first || at === title.current)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && at === last) { event.preventDefault(); first.focus(); }
  }

  if (typeof document === "undefined") return null;
  return createPortal(
    <div ref={layer} className={styles.layer} data-open={shown} data-kind={kind} onKeyDown={keys} onClick={(event) => { if (event.target === event.currentTarget) dismiss(); }}>
      <aside className={styles.card} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={leadId}>
        <header className={styles.head}>
          <span className={styles.icon} aria-hidden="true"><ShieldIcon size={28} /></span>
          <div className={styles.heading}>
            <h2 id={titleId} ref={title} className={styles.title} tabIndex={-1}><span className={styles.reco}>{t("추천", "Recommended")}</span> {t("항로 지킴이", "Course Keeper")}</h2>
            <p className={styles.en} lang="en">Course Keeper</p>
          </div>
          <button type="button" className={styles.close} onClick={() => dismiss()} aria-label={t("닫기", "Close")} data-tip={t("닫기", "Close")} data-kbd=" · Esc"><X strokeWidth={1.8} aria-hidden="true" /></button>
        </header>
        <div className={styles.body}>
          <p id={leadId} className={styles.lead}>{t("문제가 생기면 알아서 바꾸고 알려요.", "If something goes wrong, it changes the plan and tells you.")} <span>{t("되돌릴 수 있어요.", "You can undo it.")}</span></p>
          <ul className={styles.asks}>
            {start && <li>{t("끄고 진행하면 문제가 생길 때 먼저 물어봐요.", "If you turn it off, it asks you first when something goes wrong.")}</li>}
            <li>{t("켜 두어도 고정한 일정은 먼저 물어봐요.", "Even when it is on, it asks you first about locked stops.")}</li>
            <li>{t("재난·지진이 나면 일정을 멈추고 안전 안내를 보내요.", "If a disaster or earthquake happens, it pauses your itinerary and sends safety guidance.")}</li>
          </ul>
        </div>
        <footer className={styles.foot}>
          <div className={styles.actions}>
            <button type="button" className={styles.primary} onClick={onPrimary}>{start ? t("켜고 진행", "Turn on and go on") : t("켜기", "Turn on")}</button>
            <button type="button" onClick={onSecondary}>{start ? t("건너뛰기 — 끄고 진행", "Skip — turn off and go on") : t("그대로 두기", "Leave it off")}</button>
          </div>
          <p className={styles.where}><span className={styles.whereIcon} aria-hidden="true"><ShieldIcon size={20} /></span><span>{t("켠 뒤에도 언제든 화면 위 아이콘에서 끌 수 있어요.", "Even after turning it on, you can turn it off any time from the icon at the top.")}</span></p>
        </footer>
      </aside>
    </div>,
    document.body,
  );
}
