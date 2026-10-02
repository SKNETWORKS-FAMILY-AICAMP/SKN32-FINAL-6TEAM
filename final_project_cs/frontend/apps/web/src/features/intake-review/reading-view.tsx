"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { SettingsMenu } from "@/components/layout/settings-menu";
import { useT } from "@/lib/settings";
import { ProgressBar } from "./progress-bar";
import type { ReadingLine, StepState } from "./reading-model";
import styles from "./reading-view.module.css";

export interface ReadingViewProps {
  title: string;
  description: string;
  /** Said in place of the description while it holds — the line dropped, or the model is slow. */
  notice?: { tone: "info" | "warn"; text: string } | null;
  backHref: string;
  backLabel: string;
  steps: { label: string; state: StepState }[];
  percent: number;
  lines: ReadingLine[];
  found: number;
}

/**
 * Screens ①② of the mockup: the uploaded text, line by line, turning from grey to checked as the server reads it, with the
 * four-step line above. Nothing here is made up — a line is checked only when the server read it.
 */
export function ReadingView({ title, description, notice, backHref, backLabel, steps, percent, lines, found }: ReadingViewProps) {
  const t = useT();
  const stateWord: Record<ReadingLine["state"], string> = { todo: t("아직 안 읽음", "not read yet"), cur: t("읽는 중", "reading"), read: t("읽음", "read") };
  return <div className={styles.view}>
    <header className={styles.head}>
      <div className={styles.row}>
        <Link href={backHref} className={styles.back} aria-label={backLabel}><ChevronLeft size={24} strokeWidth={1.8} aria-hidden="true" /></Link>
        <h1 className={styles.title}>{title}</h1>
        <SettingsMenu />
      </div>
      <p className={styles.desc} role="status" data-tone={notice?.tone}>{notice ? notice.text : description}</p>
      <ProgressBar steps={steps} percent={percent} label={t("확인 진행", "Check progress")} />
    </header>
    <section className={styles.read} aria-label={t("올린 계획", "Your plan")}>
      <p className={styles.readLab}>{t("올린 계획", "Your plan")}</p>
      <ol className={styles.doc}>
        {lines.map((line) => <li key={line.key} className={styles.ln} data-state={line.state}>
          <span className={styles.li} aria-hidden="true" />
          <span>
            <span className={styles.lt}>{line.text}</span>
            {line.tag && <span className={styles.tg}>→ {line.tag}</span>}
            <span className="sr-only"> — {stateWord[line.state]}</span>
          </span>
        </li>)}
      </ol>
      <p className={styles.readSum}>{t("찾은 일정", "Stops found")} <b>{found}</b>{t("개", "")}</p>
    </section>
  </div>;
}
