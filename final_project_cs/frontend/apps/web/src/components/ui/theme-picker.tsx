"use client";

import { useId } from "react";
import { Check, Palette } from "lucide-react";
import { updateSettings, useSettings, useT } from "@/lib/settings";
import { themes, type Theme } from "@/lib/theme";
import styles from "./theme-picker.module.css";

/**
 * Theme card of the menu: both themes side by side, each with a sample drawn in its own colours.
 * Choosing one applies it to every screen at once and is saved with the other menu settings.
 */
export function ThemePicker() {
  const t = useT();
  const { theme } = useSettings();
  const id = useId();
  const names: Record<Theme, string> = { green: t("그린", "Green"), neutral: t("화이트", "White") };

  return <div className={styles.card} role="group" aria-labelledby={`${id}-title`}>
    <p className={styles.head} id={`${id}-title`}><Palette size={18} aria-hidden="true" /><span><small>THEME · <span lang="ko">테마</span></small><strong>{names[theme]}</strong></span></p>
    <div className={styles.options}>{themes.map((value) => (
      <button key={value} type="button" className={styles.option} aria-pressed={theme === value} onClick={() => updateSettings({ theme: value })}>
        {/* The sample sets its own theme, so it shows that theme's colours whatever is chosen now. */}
        <span className={styles.sample} data-theme={value} aria-hidden="true"><span /></span>
        {names[value]}{theme === value && <Check size={16} aria-hidden="true" />}
      </button>
    ))}</div>
  </div>;
}
