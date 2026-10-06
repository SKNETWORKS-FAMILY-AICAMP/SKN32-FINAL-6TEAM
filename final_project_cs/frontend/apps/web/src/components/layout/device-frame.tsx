"use client";

import Link from "next/link";
import { createContext, useState, type ReactNode } from "react";
import { useT } from "@/lib/settings";
import { routes } from "@/lib/routes";
import { GuardianHeaderControl } from "@/features/guardian/guardian-header";
import { OverlayRoot, SettingsMenu } from "./settings-menu";
import styles from "./device-frame.module.css";

/**
 * The place in the header the brand stands in: a screen puts something there (`createPortal` into this element) and the brand
 * steps aside while it is there — `[2026-10-03 사용자]` the plan check's place search lives there instead of in a bar of its own.
 */
export const HeaderSlot = createContext<HTMLElement | null>(null);

/**
 * Phone-sized frame of the intro and onboarding. Fixed-position children stay inside it.
 * `floating` (★`[2026-10-04 사용자 지시]` the plan check's map): the header has no bar of its own — the screen under it reaches the top of the frame and the home mark, what a screen
 * puts in the slot (the plan's name) and the menu button each float over it as a small chip.
 */
export function DeviceFrame({ children, onBrand, headerInert = false, floating = false, guardianIcon = false }: { children: ReactNode; onBrand?: () => void; headerInert?: boolean; floating?: boolean; guardianIcon?: boolean }) {
  const t = useT();
  const [overlay, setOverlay] = useState<HTMLElement | null>(null);
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const brand = <><span className={styles.mark} aria-hidden="true">t</span>triPilot</>;
  return <div className={styles.stage}>
    <div className={styles.device} data-floating={floating || undefined}>
      <OverlayRoot.Provider value={overlay}>
        <HeaderSlot.Provider value={slot}>
        <header className={styles.header} inert={headerInert}>
          {onBrand
            ? <button type="button" className={styles.brand} onClick={onBrand} aria-label={t("triPilot — 소개 화면으로 돌아가기", "triPilot — Back to introduction")}>{brand}</button>
            : <Link href={routes.home} className={styles.brand} aria-label={t("triPilot — 소개 화면으로 돌아가기", "triPilot — Back to introduction")}>{brand}</Link>}
          <div ref={setSlot} className={styles.slot} />
          {/* `[2026-10-06]` 항로 지킴이 아이콘: 등록 전 화면(읽는 중 · 계획 확인)에서, 카드로 정한 뒤부터만 보인다. */}
          <div className={styles.right}>{guardianIcon && <GuardianHeaderControl />}<SettingsMenu /></div>
        </header>
        {children}
        </HeaderSlot.Provider>
      </OverlayRoot.Provider>
      <div ref={setOverlay} className={styles.overlay} />
    </div>
  </div>;
}
