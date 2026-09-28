"use client";

import { createContext, useContext, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Menu, X } from "lucide-react";
import { updateSettings, useSettings, useT, type TripNavigation } from "@/lib/settings";
import type { Language } from "@/lib/i18n";
import styles from "./settings-menu.module.css";

/** Where the drawer renders: the device frame on intro screens, the page otherwise. */
export const OverlayRoot = createContext<HTMLElement | null>(null);

export function SettingsMenu({ className = "" }: { className?: string }) {
  const t = useT();
  const { language, navigation } = useSettings();
  const [open, setOpen] = useState(false);
  const root = useContext(OverlayRoot);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (open) panel.current?.querySelector<HTMLElement>("input:checked")?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    button.current?.focus({ preventScroll: true });
  }

  function trapFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.stopPropagation(); close(); return; }
    if (event.key !== "Tab" || !panel.current) return;
    const focusable = [...panel.current.querySelectorAll<HTMLElement>("button, input:checked")];
    const first = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }

  const languages: [Language, string][] = [["en", "English"], ["ko", "한국어"]];
  const navigations: [TripNavigation, string, string][] = [
    ["fixed", t("고정 하단 탭", "Fixed tabs"), t("화면 아래에 탭이 항상 보여요.", "Tabs stay at the bottom of the screen.")],
    ["floating", t("플로팅 버튼", "Floating button"), t("왼쪽 아래 버튼을 누르면 탭이 펼쳐져요.", "Tap the button at the bottom left to open the tabs.")],
  ];

  const drawer = open && <div className={styles.overlay} onClick={(event) => { if (event.target === event.currentTarget) close(); }}>
    <div ref={panel} className={styles.panel} id={`${id}-panel`} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} onKeyDown={trapFocus}>
      <header className={styles.head}>
        <div><p className={styles.eyebrow}>SETTINGS</p><h2 id={`${id}-title`}>{t("설정", "Settings")}</h2></div>
        <button type="button" className={styles.close} onClick={close} aria-label={t("설정 닫기", "Close settings")}><X size={20} aria-hidden="true" /></button>
      </header>
      <fieldset className={styles.group}>
        <legend>{t("언어", "Language")}</legend>
        <div className={styles.segment}>{languages.map(([value, label]) => (
          <label key={value} lang={value}><input type="radio" name={`${id}-language`} value={value} checked={language === value} onChange={() => updateSettings({ language: value })} /><span>{label}</span></label>
        ))}</div>
      </fieldset>
      <fieldset className={styles.group}>
        <legend>{t("여행 화면 내비게이션", "Trip navigation")}</legend>
        {navigations.map(([value, label, description]) => (
          <label key={value} className={styles.option}><input type="radio" name={`${id}-navigation`} value={value} checked={navigation === value} onChange={() => updateSettings({ navigation: value })} /><span><strong>{label}</strong><small>{description}</small></span></label>
        ))}
      </fieldset>
      <p className={styles.note}>{t("설정은 이 브라우저에 저장돼요.", "Settings are saved in this browser.")}</p>
    </div>
  </div>;

  return <>
    <button ref={button} type="button" className={`${styles.menuButton} ${className}`} aria-label={t("설정 메뉴", "Settings menu")} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? `${id}-panel` : undefined} onClick={() => setOpen(true)}>
      <Menu size={20} aria-hidden="true" />
    </button>
    {drawer && createPortal(drawer, root ?? document.body)}
  </>;
}
