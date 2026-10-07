"use client";

import { Suspense, type ReactNode } from "react";
import { Leaf } from "lucide-react";
import { RegistrationSteps } from "@/components/ui";
import { TripGuardianControl } from "@/features/guardian/trip-guardian";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { DeviceFrame } from "./device-frame";
import styles from "./journey-shell.module.css";

/** `checking` is the plan-check screen's frame (`features/intake-review`), the second of the registration steps. */
export type JourneyView = "registration" | "checking" | "trip" | "other";

const steps: Partial<Record<JourneyView, 0 | 1 | 2>> = { registration: 0, checking: 1 };

/** Frame of the journey screens: brand, settings, step marker and the landscape behind. */
export function JourneyShell({ view, title, tripId, children }: { view: JourneyView; title: readonly [ko: string, en: string]; /** `view="trip"`: the trip whose Course Keeper icon is drawn at the top. */ tripId?: string; children: ReactNode }) {
  const t = useT();
  useDocumentTitle(`${t(...title)} · triPilot`);
  const step = steps[view];
  const footer = <footer className={styles.footer}>
    <span><Leaf size={18} strokeWidth={1.6} aria-hidden="true" />{t("당신의 취향대로, 더 편안하게.", "More you. A little more at ease.")}</span>
    <p>{t("서버에 연결된 화면이에요. 일정과 답은 서버가 낸 결과만 보여 드려요.", "Connected to the server. Itineraries and answers shown here come from the server only.")}</p>
  </footer>;
  // ★`[2026-10-07 사용자 지시 — 어차피 지금 데스크탑 화면은 없다]` Every journey screen stands in the phone-sized frame the intro and the plan check stand in, the page scrolling inside it. The wide layout and its menu switch are gone.
  return <DeviceFrame scroll guardianIcon={view === "registration" || view === "checking"}
    headerExtra={view === "trip" && tripId ? <Suspense fallback={null}><TripGuardianControl tripId={tripId} /></Suspense> : null}>
    <a href="#main-content" className={styles.skip}>{t("본문으로 이동", "Skip to content")}</a>
    <main id="main-content" className={styles.phoneMain} tabIndex={-1} data-view={view}>
      {step !== undefined && <RegistrationSteps current={step} />}
      {children}
      {footer}
    </main>
  </DeviceFrame>;
}
