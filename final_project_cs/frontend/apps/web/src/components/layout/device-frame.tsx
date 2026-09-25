"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { useT } from "@/lib/settings";
import { routes } from "@/lib/routes";
import { OverlayRoot, SettingsMenu } from "./settings-menu";
import styles from "./device-frame.module.css";

/** Phone-sized frame of the intro and onboarding. Fixed-position children stay inside it. */
export function DeviceFrame({ children, onBrand, headerInert = false }: { children: ReactNode; onBrand?: () => void; headerInert?: boolean }) {
  const t = useT();
  const [overlay, setOverlay] = useState<HTMLElement | null>(null);
  const brand = <><span className={styles.mark} aria-hidden="true">t</span>triPilot</>;
  return <div className={styles.stage}>
    <div className={styles.device}>
      <OverlayRoot.Provider value={overlay}>
        <header className={styles.header} inert={headerInert}>
          {onBrand
            ? <button type="button" className={styles.brand} onClick={onBrand} aria-label={t("triPilot — 소개 화면으로 돌아가기", "triPilot — Back to introduction")}>{brand}</button>
            : <Link href={routes.home} className={styles.brand} aria-label={t("triPilot — 소개 화면으로 돌아가기", "triPilot — Back to introduction")}>{brand}</Link>}
          <SettingsMenu />
        </header>
        {children}
      </OverlayRoot.Provider>
      <div ref={setOverlay} className={styles.overlay} />
    </div>
  </div>;
}
