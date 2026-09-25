"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { House, Leaf } from "lucide-react";
import { RegistrationSteps } from "@/components/ui";
import { DATA_MODE } from "@/lib/data-mode";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Scene, type SceneStage } from "./scene";
import { SettingsMenu } from "./settings-menu";
import styles from "./journey-shell.module.css";

export type JourneyView = "registration" | "checking" | "results" | "trip" | "other";

const stages: Record<JourneyView, SceneStage> = { registration: 0, checking: 1, results: 1, trip: 2, other: 0 };
const steps: Partial<Record<JourneyView, 0 | 1 | 2>> = { registration: 0, checking: 1, results: 2 };

/** Frame of the journey screens: brand, settings, step marker and the landscape behind. */
export function JourneyShell({ view, title, children }: { view: JourneyView; title: readonly [ko: string, en: string]; children: ReactNode }) {
  const t = useT();
  useDocumentTitle(`${t(...title)} · triPilot`);
  const step = steps[view];
  return <div className={styles.page}>
    <Scene stage={stages[view]} sizes="100vw" />
    <a href="#main-content" className={styles.skip}>{t("본문으로 이동", "Skip to content")}</a>
    <div className={styles.shell} data-view={view}>
      <header className={styles.topbar}>
        <Link href={routes.start} className={styles.brand} aria-label={t("triPilot 홈으로", "triPilot home")}><span className={styles.mark} aria-hidden="true">t</span>triPilot</Link>
        <div className={styles.actions}>
          <Link href={routes.start} className={styles.homeButton} aria-label={t("홈으로", "Home")}><House size={18} strokeWidth={1.6} aria-hidden="true" /></Link>
          <SettingsMenu />
        </div>
      </header>
      <main id="main-content" className={styles.main} tabIndex={-1}>
        {step !== undefined && <RegistrationSteps current={step} />}
        {children}
        <footer className={styles.footer}>
          <span><Leaf size={18} strokeWidth={1.6} aria-hidden="true" />{t("당신의 취향대로, 더 편안하게.", "More you. A little more at ease.")}</span>
          <p>{DATA_MODE === "demo"
            ? t("데모 · 검증과 채팅은 시연 응답이며 실제 서비스에 연결되지 않아요.", "Demo · Checks and chat use demo responses, without a live service connection.")
            : t("실제 여행 API 연결이 필요합니다. 현재 모드에서는 데모 데이터를 사용하지 않습니다.", "A live travel API connection is required. Demo data is not used in this mode.")}</p>
        </footer>
      </main>
    </div>
  </div>;
}
