"use client";

import { createContext, useContext, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronRight, Menu, X } from "lucide-react";
import { Avatar, ButtonLink } from "@/components/ui";
import { idleText } from "@/features/account/session-card";
import { answerLines, questions } from "@/features/onboarding/model";
import { useOnboarding, useOnboardingReady } from "@/features/onboarding/onboarding-state";
import { useServiceStatus } from "@/features/support/service-notices";
import { useTrips } from "@/features/trip/use-trip";
import { DATA_MODE } from "@/lib/data-mode";
import { nicknameLabel, useProfile, type Profile } from "@/lib/profile";
import { useT } from "@/lib/settings";
import { routes } from "@/lib/routes";
import { OverlayRoot } from "./overlay-root";
import styles from "./settings-menu.module.css";

/** Where the drawer renders: the device frame on intro screens, the page otherwise. */
export { OverlayRoot };

/** The drawer's way to close itself, for what a screen puts in its head (`tools`): a press that opens a card of its own closes the drawer first (the drawer takes the focus and covers the frame). */
export const CloseMenu = createContext<() => void>(() => undefined);

/**
 * `tools` (`[2026-10-07 사용자 결정 — 목업 C안]`): a screen's own icon in the drawer's head, left of the close button (a registered trip's Course Keeper). It reads `CloseMenu`.
 * `[2026-10-13 회의 확정 — 메뉴 = 마이페이지(목업 C안)]` The drawer is My page: one board, its first cell the profile (image · name · sign-in chip · one button),
 * then four rows — 여행 목록 보기 · 여행 취향 설문 · 문의함 · 설정 (`[2026-10-13 사용자 지시]` the first three keep the names they had before, with a note under each).
 * The app settings (language · theme · list size · skip animations) moved to the settings screen, and signing out is only on 「설정 › 로그인 · 계정」.
 */
export function SettingsMenu({ className = "", tools }: { className?: string; tools?: ReactNode }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const root = useContext(OverlayRoot);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const board = useRef<HTMLDivElement>(null);
  const id = useId();

  // The first thing on the board takes the focus: the profile cell's button, or 「여행 목록 보기」 while the profile is still being read.
  useEffect(() => {
    if (open) board.current?.querySelector<HTMLElement>("a[href], button")?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    button.current?.focus({ preventScroll: true });
  }

  function trapFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.stopPropagation(); close(); return; }
    if (event.key !== "Tab" || !panel.current) return;
    const focusable = [...panel.current.querySelectorAll<HTMLElement>("a[href], button, input")];
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
      {/* One board; its cells are divided by lines only. */}
      <div ref={board} className={styles.board}><MenuBoard onClose={close} onHide={() => setOpen(false)} /></div>
    </div>
  </div>;

  return <>
    <button ref={button} type="button" className={`${styles.menuButton} ${className}`} aria-label={t("메뉴", "Menu")} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? `${id}-panel` : undefined} onClick={() => setOpen(true)}>
      <Menu size={20} aria-hidden="true" />
    </button>
    {drawer && createPortal(drawer, root ?? document.body)}
  </>;
}

/** The board's cells; mounted only while the drawer is open, so what the rows say (the trip count) is read when the menu is opened. Links close the menu on the way, also when their page is already open. */
/** `onClose` closes the drawer and gives the focus back to the menu button (links); `onHide` only closes it (the survey row, which moves to the start screen). */
function MenuBoard({ onClose, onHide }: { onClose: () => void; onHide: () => void }) {
  const t = useT();
  const router = useRouter();
  const profile = useProfile();
  const [{ complete, answers, agreed }, setOnboarding] = useOnboarding();
  const ready = useOnboardingReady();

  /**
   * `[2026-10-06 사용자 지시]` 취향 설문은 첫 진행에서 빠졌다 — 따로 하고 싶을 때 이 메뉴에서 연다(시작 화면의 취향 카드).
   * 약관에 아직 동의하지 않았으면 카드를 열지 않고 시작 화면(약관)으로 간다.
   */
  function openSurvey() {
    setOnboarding((current) => ({ ...current, open: agreed ? 2 : null }));      // ★`agreed` 는 동의 저장소에서 온 파생 값이다
    onHide();
    router.push(routes.start);
  }

  // `[2026-10-13 정한 것 ③]` 줄의 보조 문구: 여행 개수 · 취향 요약(이 브라우저 값) · 문의함 · 설정은 고정 설명 — 메뉴를 열 때 서버 읽기를 늘리지 않는다.
  const preferences = !ready ? t("불러오고 있어요", "Loading")
    : complete ? questions.slice(0, 3).map((question) => answerLines(question.id, answers, t)[0]).join(" · ")
      : t("아직 설정하지 않았어요", "Not set yet");
  const row = (title: string, note: ReactNode) => <><span className={styles.rowText}><strong>{title}</strong><small>{note}</small></span><ChevronRight size={18} aria-hidden="true" /></>;
  return <>
    <ProfileCell profile={profile} onClose={onClose} />
    <Link href={routes.trips} className={styles.row} onClick={onClose}>{row(t("여행 목록 보기", "View trip list"), <TripCount />)}</Link>
    <button type="button" className={styles.row} onClick={openSurvey}>{row(t("여행 취향 설문", "Travel preferences survey"), preferences)}</button>
    {/* `[2026-10-12 사용자 지시]` 문의함(옛 「문의하기」)은 마이페이지 카드에서 이 메뉴로 옮겼다. */}
    <Link href={routes.support} className={styles.row} onClick={onClose}>{row(t("문의함", "Inquiries"), t("보낸 문의와 답변", "Your inquiries and the answers"))}</Link>
    {/* `[2026-10-17 사용자 결정 — ST4F-604]` 공지사항 게시판 — 배너를 닫았거나 여행 화면 밖(알림 센터가 없는 곳)에서도 공지를 본다. */}
    <Link href={routes.notices} className={styles.row} onClick={onClose}>{row(t("공지사항", "Notices"), <NoticeCount />)}</Link>
    <Link href={routes.myPage} className={styles.row} onClick={onClose}>{row(t("설정", "Settings"), t("계정 · 알림 · 약관 동의 · 에이전트 · 언어 · 테마", "Account · alerts · consents · agents · language · theme"))}</Link>
  </>;
}

/**
 * The profile cell: the default image, the name, a chip with how this browser is signed in, and one button —
 * 「프로필 수정」 for a signed-in member, `[2026-10-13 사용자 결정]` 「로그인 · 가입」 for everyone else (the sign-in & accounts screen, back to the screen the menu was opened on).
 * A server with no sign-in method set up still shows the button — that screen says 「설정된 로그인 방법이 아직 없어요」.
 */
function ProfileCell({ profile, onClose }: { profile: Profile | undefined; onClose: () => void }) {
  const t = useT();
  const pathname = usePathname();
  const live = DATA_MODE === "live";
  const session = profile?.session ?? null;
  const member = session?.kind === "member";
  const chip = !live || !session ? null
    : member ? <span className={styles.chip}>{t("로그인됨", "Signed in")}</span>
      : <span className={`${styles.chip} ${styles.guestChip}`}>{session.guestIdleHours
        ? t(`게스트 · ${idleText(session.guestIdleHours, t)} 뒤 지워져요`, `Guest · deleted after ${idleText(session.guestIdleHours, t)}`)
        : t("게스트 · 이 기기에서만", "Guest · this device only")}</span>;
  // While the profile is being read nothing is offered: which button it is depends on who this is.
  const action = live && profile === undefined ? null
    : live && !member
      ? <ButtonLink href={`${routes.myPageAccount}?returnTo=${encodeURIComponent(pathname)}`} variant="primary" className={styles.cellButton} onClick={onClose}>{t("로그인 · 가입", "Sign in or sign up")}</ButtonLink>
      : <ButtonLink href={routes.myPageEdit} className={styles.cellButton} onClick={onClose}>{t("프로필 수정", "Edit profile")}</ButtonLink>;
  return <div className={styles.profile}>
    <Avatar size={64} />
    <strong className={styles.name}>{nicknameLabel(profile, t)}</strong>
    {chip}
    {action}
  </div>;
}

/** 「여행 목록 보기」's note: how many trips this browser has (the same list as the 「내 여행」 screen, read when the menu opens). */
/** `[2026-10-17 ST4F-604]` 공지사항 줄의 보조 문구 — 게시 중인 공지 수(맨 위 배너와 같은 읽기). */
function NoticeCount() {
  const t = useT();
  const status = useServiceStatus();
  if (status.isPending) return t("불러오고 있어요", "Loading");
  const count = status.data?.notices.length ?? 0;
  return count > 0 ? t(`게시 중 ${count}개`, `${count} posted now`) : t("게시 중인 공지 없음", "Nothing posted now");
}

function TripCount() {
  const t = useT();
  const trips = useTrips();
  if (trips.isPending) return t("불러오고 있어요", "Loading");
  if (trips.isError) return t("목록을 불러오지 못했어요", "Could not load the list");
  const count = trips.data.length;
  return count ? t(`${count}개`, `${count} trip${count === 1 ? "" : "s"}`) : t("아직 등록한 여행이 없어요", "No trips yet");
}
