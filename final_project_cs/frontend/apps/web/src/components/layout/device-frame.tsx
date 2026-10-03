"use client";

import Link from "next/link";
import { createContext, useState, type ReactNode } from "react";
import { useT } from "@/lib/settings";
import { routes } from "@/lib/routes";
import { OverlayRoot, SettingsMenu } from "./settings-menu";
import styles from "./device-frame.module.css";

/**
 * The place in the header the brand stands in: a screen puts something there (`createPortal` into this element) and the brand
 * steps aside while it is there — `[2026-10-03 사용자]` the plan check's place search lives there instead of in a bar of its own.
 */
export const HeaderSlot = createContext<HTMLElement | null>(null);

/** Phone-sized frame of the intro and onboarding. Fixed-position children stay inside it. */
export function DeviceFrame({ children, onBrand, headerInert = false }: { children: ReactNode; onBrand?: () => void; headerInert?: boolean }) {
  const t = useT();
  const [overlay, setOverlay] = useState<HTMLElement | null>(null);
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const brand = <><span className={styles.mark} aria-hidden="true">t</span>triPilot</>;
  return <div className={styles.stage}>
    <div className={styles.device}>
      <OverlayRoot.Provider value={overlay}>
        <HeaderSlot.Provider value={slot}>
        <header className={styles.header} inert={headerInert}>
          {onBrand
            ? <button type="button" className={styles.brand} onClick={onBrand} aria-label={t("triPilot — 소개 화면으로 돌아가기", "triPilot — Back to introduction")}>{brand}</button>
            : <Link href={routes.home} className={styles.brand} aria-label={t("triPilot — 소개 화면으로 돌아가기", "triPilot — Back to introduction")}>{brand}</Link>}
          <div ref={setSlot} className={styles.slot} />
          <SettingsMenu />
        </header>
        {children}
        </HeaderSlot.Provider>
      </OverlayRoot.Provider>
      <div ref={setOverlay} className={styles.overlay} />
    </div>
  </div>;
}
