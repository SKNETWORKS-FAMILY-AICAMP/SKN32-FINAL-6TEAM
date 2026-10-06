"use client";

import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { DeviceFrame } from "@/components/layout/device-frame";
import { progressText, type OpProgress } from "@/lib/live/stream";
import { useT } from "@/lib/settings";
import base from "./plan-check.module.css";
import styles from "./planning-progress.module.css";

/** `sending`: the conditions are on their way. `reading`: the server reads the short text. `planning`: the plan call is out (it cannot be taken back). */
export type PlanningPhase = "sending" | "reading" | "planning";

/** The stages the server says while it plans (`planning` → `checking` when it merges with read stops → `registering`). */
const STEPS = ["planning", "checking", "registering"] as const;

/**
 * `[2026-10-03 사용자 지시]` The progress screen of 「계획 짜 주기」: 「일정을 짜는 중이에요」 and, under it, the stage the server says it is in
 * (`progressText` — the same words the chat and the old review used). Unlike the plan check there are no lines of a plan to draw: the
 * customer gave conditions, not a plan.
 *
 * ★Nothing here is invented progress: the three points follow the stages the server reports, and the bar stands where the stage is.
 *   `checking` is only reported when the server merges its plan with stops it read, so it can be skipped — it then shows as done once
 *   `registering` arrives.
 *
 * While the server plans (`phase="planning"`) there is no back arrow: the request is out and the server registers the trip when it is done,
 * so leaving would only hide that.
 */
export function PlanningProgress({ phase, progress, waiting, notice, onBack }: {
  phase: PlanningPhase;
  progress: OpProgress | null;
  /** The line before the server has said a stage (what is being waited on). */
  waiting: [string, string];
  /** A slim line above the screen — e.g. that the server is slow to answer. */
  notice?: ReactNode;
  /** Absent once the plan is being made. */
  onBack?: () => void;
}) {
  const t = useT();
  const stage = progress?.stage ? STEPS.indexOf(progress.stage as (typeof STEPS)[number]) : -1;
  // The plan call is out: the first point is the current one even before the server names a stage.
  const current = phase === "planning" ? Math.max(0, stage) : -1;
  const value = current <= 0 ? 0 : Math.round(current / (STEPS.length - 1) * 100);
  const labels = [t("일정 짜기", "Planning"), t("조건 확인", "Checking"), t("여행 등록", "Registering")];
  return <DeviceFrame guardianIcon>
    <div className={base.screen} data-phase={phase}>
      {notice}
      <div className={base.reading}>
        <header className={base.head}>
          <div className={base.headRow}>
            {onBack && <button type="button" className={base.back} onClick={onBack} aria-label={t("뒤로", "Back")}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>}
            <h1 className={base.title}>{t("일정을 짜는 중이에요", "Planning your trip")}</h1>
          </div>
          <p className={base.desc}>{t("서버가 조건에 맞는 일정을 짜서 확인하고, 통과하면 곧바로 여행으로 등록해요. 1분쯤 걸려요.", "The server plans the days, checks them and registers the trip right away. It takes about a minute.")}</p>
          <div className={base.progress} data-size="large" role="progressbar" aria-label={t("일정 짜기 진행", "Planning progress")}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-valuetext={current < 0 ? t("아직 시작 전", "Not started yet") : `${labels[current]} · ${value}%`}>
            <div className={base.track}><span className={base.fill} style={{ width: `${value}%` }} /></div>
            <ol className={base.steps}>{labels.map((label, index) =>
              <li key={label} data-state={index < current ? "done" : index === current ? "current" : "waiting"}>
                <span className={base.node} aria-hidden="true" /><span className={base.stepLabel}>{label}</span>
              </li>)}</ol>
          </div>
        </header>
        <p className={styles.status} role="status" data-lost={progress?.lost || undefined}>{phase === "planning" ? progressText(progress, t, waiting) : t(...waiting)}</p>
        {phase === "planning" && <p className={styles.hint}>{t("서버가 일정을 짜는 동안에는 이 화면을 열어 두세요. 끝나면 여행 화면으로 가요.", "Keep this page open while the server plans. It moves on to your trip when it is done.")}</p>}
      </div>
    </div>
  </DeviceFrame>;
}
