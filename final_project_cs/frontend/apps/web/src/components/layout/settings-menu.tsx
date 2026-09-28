"use client";

import { createContext, useContext, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { ChevronRight, Menu, X } from "lucide-react";
import { Avatar } from "@/components/ui";
import { LanguagePicker } from "@/components/ui/language-picker";
import { nicknameLabel, useProfile } from "@/lib/profile";
import { updateSettings, useSettings, useT } from "@/lib/settings";
import { routes } from "@/lib/routes";
import styles from "./settings-menu.module.css";

/** Where the drawer renders: the device frame on intro screens, the page otherwise. */
export const OverlayRoot = createContext<HTMLElement | null>(null);

export function SettingsMenu({ className = "" }: { className?: string }) {
  const t = useT();
  const { navigation } = useSettings();
  const profile = useProfile();
  const [open, setOpen] = useState(false);
  const root = useContext(OverlayRoot);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const first = useRef<HTMLAnchorElement>(null);
  const id = useId();

  useEffect(() => {
    if (open) first.current?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    button.current?.focus({ preventScroll: true });
  }

  function trapFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.stopPropagation(); close(); return; }
    if (event.key !== "Tab" || !panel.current) return;
    // A closed language list is inert, so its options are not part of the cycle.
    const focusable = [...panel.current.querySelectorAll<HTMLElement>("a[href], button, input")].filter((element) => !element.closest("[inert]"));
    const head = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === head) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); head?.focus(); }
  }

  const drawer = open && <div className={styles.overlay} onClick={(event) => { if (event.target === event.currentTarget) close(); }}>
    <div ref={panel} className={styles.panel} id={`${id}-panel`} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} onKeyDown={trapFocus}>
      <header className={styles.head}>
        <div><p className={styles.eyebrow}>MENU</p><h2 id={`${id}-title`}>{t("메뉴", "Menu")}</h2></div>
        <button type="button" className={styles.close} onClick={close} aria-label={t("메뉴 닫기", "Close menu")}><X size={20} aria-hidden="true" /></button>
      </header>
      {/* One board; its rows are divided by lines only. */}
      <div className={styles.board}>
        {/* Links close the menu on the way, also when their page is already open. */}
        <Link ref={first} href={routes.myPage} className={styles.profile} onClick={close}>
          <Avatar size={48} />
          <span className={styles.profileText}><strong>{nicknameLabel(profile, t)}</strong><small>{t("마이페이지", "My page")}</small></span>
          <ChevronRight size={18} aria-hidden="true" />
        </Link>
        <Link href={routes.trips} className={styles.link} onClick={close}>{t("여행 목록 보기", "View trip list")}<ChevronRight size={18} aria-hidden="true" /></Link>
        {/* The same card as the home intro, caption included. */}
        <LanguagePicker caption={<>LANGUAGE · <span lang="ko">언어</span></>} />
        {/* One switch over the saved `navigation`: off = fixed tabs (the default), on = floating button. */}
        <label className={styles.switchRow}>
          <span className={styles.switchText}><strong id={`${id}-floating`}>{t("플로팅 버튼 사용", "Use floating button")}</strong><small id={`${id}-floating-note`}>{t("끄면 고정 하단 탭으로 표시됩니다.", "When off, the tabs stay fixed at the bottom.")}</small></span>
          <input type="checkbox" role="switch" className={styles.switch} checked={navigation === "floating"} aria-labelledby={`${id}-floating`} aria-describedby={`${id}-floating-note`}
            onChange={(event) => updateSettings({ navigation: event.target.checked ? "floating" : "fixed" })} />
        </label>
      </div>
      <p className={styles.note}>{t("설정은 이 브라우저에 저장돼요.", "Settings are saved in this browser.")}</p>
    </div>
  </div>;

  return <>
    <button ref={button} type="button" className={`${styles.menuButton} ${className}`} aria-label={t("메뉴", "Menu")} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? `${id}-panel` : undefined} onClick={() => setOpen(true)}>
      <Menu size={20} aria-hidden="true" />
    </button>
    {drawer && createPortal(drawer, root ?? document.body)}
  </>;
}
