"use client";

import Link from "next/link";
import { CircleHelp } from "lucide-react";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import styles from "./language-picker.module.css";

/**
 * `[2026-10-22 사용자 결정 — ST4F-717]` The (?) next to the language globe: opens 「이용 방법」 — on a screen it explains, at that screen's part (`screen`).
 * It looks like the globe (the same button style) so the header's buttons stay alike.
 */
export function HelpButton({ screen }: { screen?: string }) {
  const t = useT();
  const label = t("이용 방법", "How to use");
  return <Link href={screen ? `${routes.help}?screen=${screen}` : routes.help} className={styles.globeButton} aria-label={label} title={label}><CircleHelp size={20} aria-hidden="true" /></Link>;
}
