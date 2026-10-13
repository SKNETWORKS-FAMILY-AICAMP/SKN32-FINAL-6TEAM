"use client";

import { useId } from "react";
import { LanguagePicker } from "@/components/ui/language-picker";
import { ThemePicker } from "@/components/ui/theme-picker";
import { useListZoom, writeListZoom } from "@/features/plan-check/list-zoom";
import { updateSettings, useSettings, useT } from "@/lib/settings";
import styles from "./app-settings.module.css";

/**
 * `[2026-10-13 회의 확정 — 메뉴 = 마이페이지]` The app settings the menu had — language · theme · schedule list size · skip animations —
 * now on the settings screen (`/mypage`). Moved as they were; they are saved in this browser.
 */
export function AppSettings() {
  const t = useT();
  const { skipAnimation } = useSettings();
  const listZoom = useListZoom();
  const id = useId();
  return <div className={styles.board}>
    {/* The same card as the home intro, caption included. */}
    <LanguagePicker caption={<>LANGUAGE · <span lang="ko">언어</span></>} />
    <ThemePicker />
    <div className={styles.listZoom} role="group" aria-label={t("일정 목록 크기", "Schedule list size")}>
      <div className={styles.zoomHeading}><strong>{t("일정 목록 크기", "Schedule list size")}</strong><output aria-live="polite">{Math.round(listZoom * 100)}%</output></div>
      <div className={styles.zoomButtons}>
        <button type="button" aria-label={t("일정 목록 축소", "Reduce schedule list size")} disabled={listZoom <= 0.8} onClick={() => writeListZoom(listZoom - 0.1)}>−</button>
        <button type="button" disabled={listZoom === 1} onClick={() => writeListZoom(1)}>{t("기본 크기", "Default size")}</button>
        <button type="button" aria-label={t("일정 목록 확대", "Increase schedule list size")} disabled={listZoom >= 1.3} onClick={() => writeListZoom(listZoom + 0.1)}>+</button>
      </div>
    </div>
    {/* `[2026-10-03 사용자 결정]` 계획 확인 화면의 단계별 재생을 건너뛰고 서버 결과를 바로 본다. 시스템의 「동작 줄이기」가 아니라 이 스위치가 정한다. */}
    <label className={styles.switchRow}>
      <span className={styles.switchText}><strong id={`${id}-skip`}>{t("애니메이션 건너뛰기", "Skip animations")}</strong><small id={`${id}-skip-note`}>{t("켜면 계획 확인 화면이 단계별 재생 없이 바로 떠요.", "When on, the plan check appears at once, without the step-by-step replay.")}</small></span>
      <input type="checkbox" role="switch" className={styles.switch} checked={skipAnimation} aria-labelledby={`${id}-skip`} aria-describedby={`${id}-skip-note`}
        onChange={(event) => updateSettings({ skipAnimation: event.target.checked })} />
    </label>
  </div>;
}
