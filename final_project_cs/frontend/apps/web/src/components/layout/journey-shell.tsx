"use client";

import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { Leaf } from "lucide-react";
import { RegistrationSteps } from "@/components/ui";
import { GuardianHeaderControl } from "@/features/guardian/guardian-header";
import { TripGuardianControl } from "@/features/guardian/trip-guardian";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Scene, type SceneStage } from "./scene";
import { SettingsMenu } from "./settings-menu";
import styles from "./journey-shell.module.css";

/** `checking` is the plan-check screen's frame (`features/intake-review`), the second of the registration steps. */
export type JourneyView = "registration" | "checking" | "trip" | "other";

const stages: Record<JourneyView, SceneStage> = { registration: 0, checking: 1, trip: 2, other: 0 };
const steps: Partial<Record<JourneyView, 0 | 1 | 2>> = { registration: 0, checking: 1 };

/** Frame of the journey screens: brand, settings, step marker and the landscape behind. */
export function JourneyShell({ view, title, tripId, children }: { view: JourneyView; title: readonly [ko: string, en: string]; /** `view="trip"`: the trip whose Course Keeper icon is drawn at the top. */ tripId?: string; children: ReactNode }) {
  const t = useT();
  useDocumentTitle(`${t(...title)} · triPilot`);
  const step = steps[view];
  return <div className={styles.page}>
    <Scene stage={stages[view]} sizes="100vw" />
    <a href="#main-content" className={styles.skip}>{t("본문으로 이동", "Skip to content")}</a>
    <div className={styles.shell} data-view={view}>
      <header className={styles.topbar}>
        <Link href={routes.home} className={styles.brand} aria-label={t("triPilot 홈으로", "triPilot home")}><span className={styles.mark} aria-hidden="true">t</span>triPilot</Link>
        <div className={styles.actions}>
          {/* `[2026-10-06]` 항로 지킴이 아이콘: 등록 전 화면(계획 담기 · 계획 확인)에서, 카드로 정한 뒤부터만 보인다. */}
          {(view === "registration" || view === "checking") && <GuardianHeaderControl />}
          {/* `[2026-10-06]` 등록된 여행: 서버가 말한 켜짐·꺼짐(`guardian`)을 그리고 누르면 서버에 보낸다. 알림 링크(`?guardian=on`)도 여기서 받는다. */}
          {view === "trip" && tripId && <Suspense fallback={null}><TripGuardianControl tripId={tripId} /></Suspense>}
          <SettingsMenu />
        </div>
      </header>
      <main id="main-content" className={styles.main} tabIndex={-1}>
        {step !== undefined && <RegistrationSteps current={step} />}
        {children}
        <footer className={styles.footer}>
          <span><Leaf size={18} strokeWidth={1.6} aria-hidden="true" />{t("당신의 취향대로, 더 편안하게.", "More you. A little more at ease.")}</span>
          <p>{t("서버에 연결된 화면이에요. 일정과 답은 서버가 낸 결과만 보여 드려요.", "Connected to the server. Itineraries and answers shown here come from the server only.")}</p>
        </footer>
      </main>
    </div>
  </div>;
}
