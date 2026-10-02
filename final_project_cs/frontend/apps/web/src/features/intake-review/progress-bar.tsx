"use client";

import type { CSSProperties } from "react";
import { useT } from "@/lib/settings";
import type { StepState } from "./reading-model";
import styles from "./progress-bar.module.css";

/**
 * The progress on one straight line (mockup `.pb`): a dot per step, a green head that moves as far as `percent`, a checked
 * dot for each finished step. `compact` is the thin version inside the bar that floats over the map.
 *
 * The steps are a list — the one being done carries `aria-current="step"` and every step says in words whether it is done.
 */
export function ProgressBar({ steps, percent, compact = false, label }: {
  steps: { label: string; state: StepState }[];
  percent: number;
  compact?: boolean;
  label: string;
}) {
  const t = useT();
  const clamped = Math.min(100, Math.max(0, percent));
  const last = steps.length - 1;
  const said: Record<StepState, string> = { todo: t("기다리는 중", "waiting"), cur: t("진행 중", "in progress"), done: t("끝", "done") };
  return <div className={`${styles.bar}${compact ? ` ${styles.compact}` : ""}`}>
    <ol className={styles.track} aria-label={label}>
      <li className={styles.rail} aria-hidden="true">
        <i className={styles.line} />
        <i className={styles.fill} style={{ width: `${clamped}%` }} />
        <i className={`${styles.head}${clamped > 0 && clamped < 100 ? ` ${styles.headOn}` : ""}`} style={{ left: `${clamped}%` }} />
      </li>
      {steps.map((step, index) => <li key={index} className={styles.step} style={{ left: `${index * 100 / last}%` } as CSSProperties} aria-current={step.state === "cur" ? "step" : undefined}>
        <span className={`${styles.node} ${styles[step.state]}`} aria-hidden="true" />
        <span className={`${styles.lab} ${styles[`lab_${step.state}`]}${index === 0 ? ` ${styles.labFirst}` : ""}${index === last ? ` ${styles.labLast}` : ""}`}>{step.label}</span>
        <span className="sr-only"> — {said[step.state]}</span>
      </li>)}
    </ol>
  </div>;
}
