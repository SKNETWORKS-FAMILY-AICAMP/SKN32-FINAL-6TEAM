"use client";

import type { ReactNode } from "react";
import { Leaf } from "lucide-react";
import { RegistrationSteps } from "@/components/ui";
import { LanguageButton } from "@/components/ui/language-picker";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { DeviceFrame } from "./device-frame";
import styles from "./journey-shell.module.css";

/** `checking` is the plan-check screen's frame (`features/intake-review`), the second of the registration steps. `[2026-10-07]` A trip has its own map screen now (`features/trip/trip-screen.tsx`), not this frame. */
export type JourneyView = "registration" | "checking" | "other";

const steps: Partial<Record<JourneyView, 0 | 1 | 2>> = { registration: 0, checking: 1 };

/** Frame of the journey screens: brand, settings, step marker and the landscape behind. */
export function JourneyShell({ view, title, children }: { view: JourneyView; title: readonly [ko: string, en: string]; children: ReactNode }) {
  const t = useT();
  useDocumentTitle(`${t(...title)} · guguroute`);
  const step = steps[view];
  const footer = <footer className={styles.footer}>
    <span><Leaf size={18} strokeWidth={1.6} aria-hidden="true" />{t("당신의 취향대로, 더 편안하게.", "More you. A little more at ease.")}</span>
    <p>{t("서버에 연결된 화면이에요. 일정과 답은 서버가 낸 결과만 보여 드려요.", "Connected to the server. Itineraries and answers shown here come from the server only.")}</p>
  </footer>;
  // 모든 공통 화면은 휴대폰 크기 틀을 사용한다. 등록한 여행은 전용 지도 화면을 사용한다.
  // `[2026-10-13 사용자 결정]` 계획 담기(등록 첫 단계)까지는 메뉴 옆에 언어 지구본도 둔다(설정 화면에서도 바꾼다). 그 자리의 항로 지킴이 아이콘은 뺀다 — 「계획 확인하기」를 누르면 항로 지킴이 카드가 뜬다.
  return <DeviceFrame scroll guardianIcon={view === "checking"} headerExtra={view === "registration" ? <LanguageButton /> : null}>
    <a href="#main-content" className={styles.skip}>{t("본문으로 이동", "Skip to content")}</a>
    <main id="main-content" className={styles.phoneMain} tabIndex={-1} data-view={view}>
      {step !== undefined && <RegistrationSteps current={step} />}
      {children}
      {footer}
    </main>
  </DeviceFrame>;
}
