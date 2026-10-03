"use client";

import type { ReactNode } from "react";
import type { Translate } from "@/lib/i18n";
import { useT } from "@/lib/settings";
import type { CheckKind, CheckResult, CheckRow, Verdict } from "./model";
import styles from "./plan-check.module.css";

/** Shared by the result's cards and the change screen's cards. */

export const GLYPH: Record<CheckResult, string> = { ok: "✓", filled: "✎", warn: "!", bad: "✕", unknown: "–", pending: "" };

export function Checks({ id, rows }: { id?: string; rows: CheckRow[] }) {
  const t = useT();
  return <ul id={id} className={styles.checks}>{rows.map((row, index) =>
    <li key={`${row.kind}-${index}`} className={styles.check} data-result={row.result}>
      <span className={styles.mark} aria-hidden="true">{GLYPH[row.result]}</span>
      <b className={styles.checkKind}>{kindLabel(row.kind, t)}</b>
      <span className={styles.checkText}>{row.result === "pending" ? t("확인하는 중…", "Checking…") : row.text}</span>
      <span className="sr-only">{resultLabel(row.result, t)}</span>
    </li>)}</ul>;
}

export function VerdictPill({ verdict }: { verdict: Verdict }) {
  const t = useT();
  return <span className={styles.pill} data-verdict={verdict}>{verdictLabel(verdict, t)}</span>;
}

export function VerdictMark({ verdict }: { verdict: Verdict }) {
  const t = useT();
  const result: CheckResult = verdict === "keep" ? "ok" : verdict === "adjusted" ? "filled" : "warn";
  return <span className={styles.mark} data-result={result} role="img" aria-label={verdictLabel(verdict, t)}>{GLYPH[result]}</span>;
}

/** A mark with a short line, for the sheet's head (「! 장소 1곳 확인 필요」). */
export function Status({ result, children }: { result: CheckResult; children: ReactNode }) {
  return <span className={styles.status}><span className={styles.mark} data-result={result} aria-hidden="true">{GLYPH[result]}</span><span>{children}</span></span>;
}

export function resultLabel(result: CheckResult, t: Translate): string {
  return {
    ok: t("통과", "passed"), filled: t("채움", "filled in"), warn: t("주의", "warning"), bad: t("고쳐야 함", "needs fixing"),
    unknown: t("아직 모름", "not known yet"), pending: t("확인하는 중", "checking"),
  }[result];
}

export function kindLabel(kind: CheckKind, t: Translate): string {
  return {
    place: t("장소", "Place"), time: t("시간", "Time"), hours: t("운영시간", "Hours"), closed: t("휴무일", "Closed"),
    route: t("경로", "Route"), mode: t("수단", "Mode"), arrival: t("도착", "Arrival"),
  }[kind];
}

export function verdictLabel(verdict: Verdict, t: Translate): string {
  return { keep: t("유지", "Kept"), adjusted: t("조정", "Adjusted"), review: t("확인 필요", "Check") }[verdict];
}

/** Why a step did not happen, in the server's own words when it said no (`LiveError.message`). */
export const reason = (error: unknown) => error instanceof Error ? error.message : String(error);

/** A button that stays reachable when it cannot act: pressing it says why (mockup: 「꺼진 버튼을 누르면 이유를 알려 준다」). */
export function Act({ why, onPress, explain, className, children, title, ...rest }: {
  why: string | null; onPress: () => void; explain: (why: string) => void; className?: string; children: ReactNode;
  id?: string; title?: string; "aria-label"?: string; "aria-pressed"?: boolean; "data-primary"?: boolean;
}) {
  return <button type="button" className={className} aria-disabled={why ? true : undefined} title={why ?? title} {...rest}
    onClick={() => why ? explain(why) : onPress()}>{children}</button>;
}

/** 「A」 「B」 「C」 for the change screen's cards and pins (the current stop is card 0). */
export const letter = (index: number) => "ABCDEFGH"[index - 1] ?? String(index);
