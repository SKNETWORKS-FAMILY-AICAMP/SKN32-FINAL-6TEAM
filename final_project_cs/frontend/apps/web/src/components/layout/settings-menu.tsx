"use client";

import { createContext, useContext, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronRight, Menu, X } from "lucide-react";
import { Avatar } from "@/components/ui";
import { useAuthProviders } from "@/features/account/use-auth-providers";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { LanguagePicker } from "@/components/ui/language-picker";
import { ThemePicker } from "@/components/ui/theme-picker";
import { nicknameLabel, useProfile } from "@/lib/profile";
import { updateSettings, useSettings, useT } from "@/lib/settings";
import { routes } from "@/lib/routes";
import { OverlayRoot } from "./overlay-root";
import styles from "./settings-menu.module.css";

/** Where the drawer renders: the device frame on intro screens, the page otherwise. */
export { OverlayRoot };

/** The drawer's way to close itself, for what a screen puts in its head (`tools`): a press that opens a card of its own closes the drawer first (the drawer takes the focus and covers the frame). */
export const CloseMenu = createContext<() => void>(() => undefined);

/** `tools` (`[2026-10-07 사용자 결정 — 목업 C안]`): a screen's own icon in the drawer's head, left of the close button (a registered trip's Course Keeper). It reads `CloseMenu`. */
export function SettingsMenu({ className = "", tools }: { className?: string; tools?: ReactNode }) {
  const t = useT();
  const { skipAnimation, desktopLayout } = useSettings();
  const profile = useProfile();
  const [open, setOpen] = useState(false);
  // `[2026-10-03 사용자 지시]` 「계정 연결 · 로그인」 줄은 서버가 로그인 방법을 하나라도 설정했을 때만 있다(메뉴를 열 때 한 번 물어본다).
  const providers = useAuthProviders(open);
  const root = useContext(OverlayRoot);
  const router = useRouter();
  const [{ agreed }, setOnboarding] = useOnboarding();
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

  /**
   * `[2026-10-06 사용자 지시]` 취향 설문은 첫 진행에서 빠졌다 — 따로 하고 싶을 때 이 메뉴에서 연다(마이페이지의 「여행 취향」과 같은 화면: 시작 화면의 취향 카드).
   * 약관에 아직 동의하지 않았으면 카드를 열지 않고 시작 화면(약관)으로 간다.
   */
  function openSurvey() {
    setOnboarding((current) => ({ ...current, open: agreed ? 2 : null }));      // ★`agreed` 는 동의 저장소에서 온 파생 값이다
    setOpen(false);
    router.push(routes.start);
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
        <div className={styles.headTools}><CloseMenu.Provider value={close}>{tools}</CloseMenu.Provider>
          <button type="button" className={styles.close} onClick={close} aria-label={t("메뉴 닫기", "Close menu")}><X size={20} aria-hidden="true" /></button></div>
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
        <button type="button" className={styles.link} onClick={openSurvey}>{t("여행 취향 설문", "Travel preferences survey")}<ChevronRight size={18} aria-hidden="true" /></button>
        {(providers.data?.length ?? 0) > 0 && <Link href={`${routes.myPage}#accounts`} className={styles.link} onClick={close}>{t("계정 연결 · 로그인", "Link account · Sign in")}<ChevronRight size={18} aria-hidden="true" /></Link>}
        {/* The same card as the home intro, caption included. */}
        <LanguagePicker caption={<>LANGUAGE · <span lang="ko">언어</span></>} />
        <ThemePicker />
        {/* `[2026-10-03 사용자 결정]` 계획 확인 화면의 단계별 재생을 건너뛰고 서버 결과를 바로 본다. 시스템의 「동작 줄이기」가 아니라 이 스위치가 정한다. */}
        <label className={styles.switchRow}>
          <span className={styles.switchText}><strong id={`${id}-skip`}>{t("애니메이션 건너뛰기", "Skip animations")}</strong><small id={`${id}-skip-note`}>{t("켜면 계획 확인 화면이 단계별 재생 없이 바로 떠요.", "When on, the plan check appears at once, without the step-by-step replay.")}</small></span>
          <input type="checkbox" role="switch" className={styles.switch} checked={skipAnimation} aria-labelledby={`${id}-skip`} aria-describedby={`${id}-skip-note`}
            onChange={(event) => updateSettings({ skipAnimation: event.target.checked })} />
        </label>
        {/* `[2026-10-06 사용자 지시]` 기본은 모든 화면이 휴대폰 크기 틀이다. 넓은 창에서 화면 전체 폭을 쓰고 싶을 때만 켠다. */}
        <label className={styles.switchRow}>
          <span className={styles.switchText}><strong id={`${id}-desktop`}>{t("데스크탑 화면으로 보기", "Use the desktop layout")}</strong><small id={`${id}-desktop-note`}>{t("끄면 모든 화면이 휴대폰 크기로 보여요.", "When off, every screen is shown phone-sized.")}</small></span>
          <input type="checkbox" role="switch" className={styles.switch} checked={desktopLayout} aria-labelledby={`${id}-desktop`} aria-describedby={`${id}-desktop-note`}
            onChange={(event) => updateSettings({ desktopLayout: event.target.checked })} />
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
