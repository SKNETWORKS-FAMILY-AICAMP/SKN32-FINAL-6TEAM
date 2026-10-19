"use client";

import { useId } from "react";
import { Check, Palette } from "lucide-react";
import { updateSettings, useDeviceDark, useSettings, useT } from "@/lib/settings";
import { appliedTheme, themes, type Theme } from "@/lib/theme";
import styles from "./theme-picker.module.css";

/**
 * Theme card of the menu: 「기기 설정 따르기」 on top (the default — `[2026-10-17]`), then both themes side by side, each with a sample drawn
 * in its own colours. Choosing one applies it to every screen at once and is saved with the other menu settings.
 */
export function ThemePicker() {
  const t = useT();
  const { theme } = useSettings();
  const deviceDark = useDeviceDark();
  const id = useId();
  const names: Record<Theme, string> = { system: t("기기 설정 따르기", "Match device"), green: t("그린", "Green"), dark: t("다크", "Dark") };

  return <div className={styles.card} role="group" aria-labelledby={`${id}-title`}>
    <p className={styles.head} id={`${id}-title`}><Palette size={18} aria-hidden="true" /><span><small>THEME · <span lang="ko">테마</span></small><strong>{theme === "system" ? `${names.system} · ${names[appliedTheme(theme, deviceDark)]}` : names[theme]}</strong></span></p>
    <div className={styles.options}>{themes.map((value) => (
      <button key={value} type="button" className={styles.option} aria-pressed={theme === value} onClick={() => updateSettings({ theme: value })}>
        {/* The sample sets its own theme, so it shows that theme's colours whatever is chosen now; the device's choice shows both halves. */}
        {value === "system"
          ? <span className={styles.sample} data-split aria-hidden="true"><span data-theme="green" /><span data-theme="dark" /></span>
          : <span className={styles.sample} data-theme={value} aria-hidden="true"><span /></span>}
        {names[value]}{theme === value && <Check size={16} aria-hidden="true" />}
      </button>
    ))}</div>
  </div>;
}
