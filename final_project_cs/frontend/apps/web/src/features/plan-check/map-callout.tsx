"use client";

import { X } from "lucide-react";
import { useT } from "@/lib/settings";
import type { PlanItem, PlanMove } from "./model";
import styles from "./map-callout.module.css";

/** 「확인 필요」 reads as a warning, 「통과」 as fine; nothing yet (still checking) says nothing. */
function verdictChip(verdict: PlanItem["verdict"], t: ReturnType<typeof useT>): { text: string; tone: "ok" | "warn" | "changed" } | null {
  if (verdict === "review") return { text: t("확인 필요", "Needs a look"), tone: "warn" };
  if (verdict === "adjusted") return { text: t("바뀜", "Changed"), tone: "changed" };
  if (verdict === "keep") return { text: t("통과", "OK"), tone: "ok" };
  return null;
}

/** The first thing the check found that is not fine, as one line 「장소 · 이름이 여러 곳이라…」. */
function firstIssue(checks: PlanItem["checks"]): string | null {
  const bad = checks.find((check) => check.result !== "ok" && check.text.trim());
  return bad ? bad.text.trim() : null;
}

/**
 * `[2026-10-06 사용자 지시 — 마커를 누르면 그 마커의 설명이 나오고, 경로를 누르면 그 경로가 나온다]` The small card over the map for what was just pressed on it: a pin (its number, name, when, where, what the check
 * found) or a route line (from → to, how, how long, when to leave and arrive). Only what the plan check already holds is shown - nothing is made up. 「목록에서 보기」 brings the same stop or leg up in the sheet; ✕ lets it go.
 */
export function MapCallout({ stop, move, onList, onClose }: {
  stop?: { order: number; item: PlanItem } | null;
  move?: { move: PlanMove; from: string; to: string } | null;
  onList: () => void;
  onClose: () => void;
}) {
  const t = useT();
  if (!stop && !move) return null;
  const verdict = verdictChip(stop ? stop.item.verdict : move!.move.verdict, t);
  const issue = stop ? firstIssue(stop.item.checks) : firstIssue(move!.move.checks);
  return <section className={styles.callout} role="status" aria-label={stop ? t(`${stop.order}번 일정 설명`, `Stop ${stop.order}`) : t("이동 경로 설명", "Route")}>
    {stop ? <>
      <span className={styles.badge} aria-hidden="true">{stop.order}</span>
      <div className={styles.text}>
        <strong>{stop.item.title}{verdict && <em data-tone={verdict.tone}>{verdict.text}</em>}</strong>
        <span>{stop.item.startsAt}{stop.item.endsAt ? `–${stop.item.endsAt}` : ""}{stop.item.place && stop.item.place !== stop.item.title ? ` · ${stop.item.place}` : ""}</span>
        {stop.item.info?.address && <span>{stop.item.info.address}</span>}
        {issue && <span className={styles.issue}>{issue}</span>}
      </div>
    </> : <>
      <span className={styles.badge} data-route aria-hidden="true">→</span>
      <div className={styles.text}>
        <strong>{move!.from} → {move!.to}{verdict && <em data-tone={verdict.tone}>{verdict.text}</em>}</strong>
        <span>{move!.move.summary.includes(move!.move.mode) ? move!.move.summary : `${move!.move.mode}${move!.move.summary ? ` · ${move!.move.summary}` : ""}`}</span>
        {(move!.move.departAt || move!.move.arriveAt) && <span>{move!.move.departAt && t(`${move!.move.departAt} 출발`, `Leave ${move!.move.departAt}`)}{move!.move.arriveAt && ` → ${t(`${move!.move.arriveAt} 도착`, `arrive ${move!.move.arriveAt}`)}`}{move!.move.estimated && ` · ${t("직선 거리로 어림한 시간", "estimated from the straight distance")}`}</span>}
        {issue && <span className={styles.issue}>{issue}</span>}
      </div>
    </>}
    <button type="button" className={styles.close} onClick={onClose} aria-label={t("닫기", "Close")}><X size={18} strokeWidth={1.8} aria-hidden="true" /></button>
    <button type="button" className={styles.list} onClick={onList}>{t("목록에서 보기", "Show in list")}</button>
  </section>;
}
