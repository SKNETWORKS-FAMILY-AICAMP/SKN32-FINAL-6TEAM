"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { DeviceFrame } from "@/components/layout/device-frame";
import { routes } from "@/lib/routes";
import { useT } from "@/lib/settings";
import { useDocumentTitle } from "@/lib/use-document-title";
import { exampleDone, exampleSnapshots } from "./fixtures";
import type { PlanCheckView } from "./model";
import { PlanCheck } from "./plan-check";
import styles from "./preview.module.css";

/** Plays the example snapshots on their own clock, as a server would send them. */
function Player({ start }: { start: "play" | "done" }) {
  const router = useRouter();
  const [view, setView] = useState<PlanCheckView>(start === "done" ? exampleDone : exampleSnapshots[0].view);
  useEffect(() => {
    if (start === "done") return;
    const timers = exampleSnapshots.slice(1).map(({ at, view: next }) => setTimeout(() => setView(next), at));
    return () => timers.forEach(clearTimeout);
  }, [start]);
  return <PlanCheck view={view} onBack={() => router.push(routes.newTrip)} />;
}

/**
 * ★Preview of the plan-check screen with the mockup's example data — not connected to the server, and labelled so.
 *   For building and handing over the screen; the backend wires the real route (2026-10-03 user decision).
 */
export function PlanCheckPreview() {
  const t = useT();
  useDocumentTitle(t("triPilot · 계획 확인 미리보기", "triPilot · Plan check preview"));
  const [run, setRun] = useState<{ id: number; start: "play" | "done" }>({ id: 0, start: "play" });
  return <>
    <DeviceFrame><Player key={run.id} start={run.start} /></DeviceFrame>
    <aside className={styles.preview} aria-label={t("미리보기 조작", "Preview controls")}>
      <span>{t("미리보기 · 예시 데이터 · 서버 미연결", "Preview · example data · not connected")}</span>
      <button type="button" onClick={() => setRun((current) => ({ id: current.id + 1, start: "play" }))}>{t("처음부터 재생", "Replay")}</button>
      <button type="button" onClick={() => setRun((current) => ({ id: current.id + 1, start: "done" }))}>{t("결과 바로 보기", "Show result")}</button>
    </aside>
  </>;
}
