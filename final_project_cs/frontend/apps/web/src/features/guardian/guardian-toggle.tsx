"use client";

import { useT } from "@/lib/settings";
import { ShieldIcon } from "./guardian-card";
import styles from "./guardian-toggle.module.css";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 · 목업 v9 §3-3]` The Course Keeper icon at the top of the screen (left of the menu button). A 44 px icon button.
 * - On: a pale green disc, a dot and a green shield. Off: no disc, a faint outline. The state is not told by colour alone (disc + dot).
 * - Its NAME says what pressing does (「항로 지킴이 끄기」 / 「항로 지킴이 켜기」); the present state is read out as hidden text (「지금 켜져 있어요」). The tooltip says the same name.
 * - Pressing it while on turns it off at once (the screen then shows an undo line); while off it asks to turn it on (`aria-haspopup="dialog"`: the card).
 */
export function GuardianToggle({ on, onPress }: { on: boolean; onPress: () => void }) {
  const t = useT();
  const name = on ? t("항로 지킴이 끄기", "Turn Course Keeper off") : t("항로 지킴이 켜기", "Turn Course Keeper on");
  return <button type="button" className={styles.toggle} data-on={on || undefined} onClick={onPress} aria-label={name} data-tip={name} aria-haspopup={on ? undefined : "dialog"}>
    <ShieldIcon size={24} />
    <span className="sr-only">{on ? t("지금 켜져 있어요", "It is on now") : t("지금 꺼져 있어요", "It is off now")}</span>
  </button>;
}
