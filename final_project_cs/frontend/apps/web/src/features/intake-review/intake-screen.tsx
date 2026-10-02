"use client";

import { useState, type ReactNode } from "react";
import { OverlayRoot } from "@/components/layout/settings-menu";
import { KeyNotice } from "@/features/account/key-notice";
import { DATA_MODE } from "@/lib/data-mode";
import styles from "./intake-screen.module.css";

/**
 * The frame of the plan-check screen — the phone-sized screen of the 2026-10-02 mockup. On a wide window it is the same
 * 402 px card the intro and onboarding use; at 720 px and below it is the whole window.
 *
 * It also holds the mockup's palette (`--ink`, `--line`, `--ok`, …) for everything inside, and the place where the settings
 * drawer opens, so the drawer stays inside the frame like on the other phone-sized screens.
 */
export function IntakeScreen({ children }: { children: ReactNode }) {
  const [overlay, setOverlay] = useState<HTMLElement | null>(null);
  return <div className={styles.stage}>
    <div className={styles.screen}>
      <OverlayRoot.Provider value={overlay}>
        <main id="main-content" className={styles.main} tabIndex={-1}>{children}</main>
        {/* ★A key issued while this plan was uploaded is shown once, here too: the server cannot show it again (D-020, D-021 §4). */}
        {DATA_MODE === "live" && <div className={styles.keyNotice}><KeyNotice /></div>}
      </OverlayRoot.Provider>
      <div ref={setOverlay} className={styles.overlay} />
    </div>
  </div>;
}
