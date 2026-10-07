"use client";

import type { CSSProperties, ReactNode } from "react";
import type { Translate } from "@/lib/i18n";
import { useT } from "@/lib/settings";
import type { CheckKind, CheckResult, CheckRow, PlaceInfo, Verdict } from "./model";
import type { Grab } from "./use-time-edit";
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

/**
 * `[2026-10-07 사용자 지시 — 카드의 둘째 줄에 사용자 입력이 필요한 요소를 ✕ 장소 처럼]` What of a stop the customer still has to deal with, one chip each (「✕ 장소」 · 「! 시간」), so a card that is shut still says what is wrong with it.
 * Only the checks that went wrong (`bad` · `warn`) - a fine one, one still being checked and one waiting on the place (`unknown`) are not the customer's to do.
 */
export function needsOf(rows: CheckRow[]): CheckRow[] { return rows.filter((row) => row.result === "bad" || row.result === "warn"); }
export function NeedsLine({ rows, inline = false }: { rows: CheckRow[]; inline?: boolean }) {
  const t = useT();
  const wrong = needsOf(rows);
  if (!wrong.length) return null;
  const Box = inline ? "span" : "p";
  return <Box className={inline ? styles.needsInline : styles.needs}>{wrong.map((row, index) =>
    <span key={`${row.kind}-${index}`} className={styles.need} data-result={row.result}>
      <span className={styles.mark} data-result={row.result} aria-hidden="true">{GLYPH[row.result]}</span>
      <b>{kindLabel(row.kind, t)}</b><span className="sr-only">{resultLabel(row.result, t)}</span>
    </span>)}</Box>;
}

/** ★`[2026-10-04 사용자 지시]` Only 「확인 필요」 is said: a stop that is simply fine (or was adjusted a little by the server) carries no word — the old 「조정」 told no one anything. */
export function VerdictPill({ verdict }: { verdict: Verdict }) {
  const t = useT();
  return verdict === "review" ? <span className={styles.pill} data-state="review">{verdictLabel(verdict, t)}</span> : null;
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
    place: t("장소", "Place"), time: t("시간", "Time"), hours: t("운영시간", "Hours"), closed: t("휴무일", "Closed"), booking: t("예약", "Booking"),
    route: t("경로", "Route"), mode: t("수단", "Mode"), arrival: t("도착", "Arrival"),
  }[kind];
}

export function verdictLabel(verdict: Verdict, t: Translate): string {
  return { keep: t("유지", "Kept"), adjusted: t("조정", "Adjusted"), review: t("확인 필요", "Check") }[verdict];
}

/** 「식당」 · 「활동」 — what kind of stop a place is. It is the server's own class; the server says nothing finer than that yet. */
export function placeKindLabel(kind: string | null | undefined, t: Translate): string | null {
  if (kind === "dining") return t("식당", "Food");
  if (kind === "activity") return t("활동", "Activity");
  return null;
}

/** `[2026-10-07 사용자 지시]` The word under a picked pin on the map: 「액티비티」 for a thing to do, 「식당」 for a meal; none when the server does not class the stop. */
export function pinKindLabel(kind: string | null | undefined, t: Translate): string | null {
  if (kind === "dining") return t("식당", "Food");
  if (kind === "activity") return t("액티비티", "Activity");
  return null;
}

/** Where the server found a place (its `source`) — shown small beside the name, so a result says what it came from. */
export function sourceLabel(origin: string | null | undefined, t: Translate): string | null {
  switch (origin) {
    case undefined: case null: case "": return null;
    case "places": return t("우리 장소 목록", "Our places");
    case "tour_api": return t("관광공사", "Tourism org.");
    case "kakao": return t("카카오 지도", "Kakao Map");
    case "customer_pick": case "customer": return t("직접 고른 곳", "Picked by you");
    default: return t("장소 정보", "Place data");
  }
}

/** One line under a place's name: its kind, what the server calls it, where it is — only what the server gave. */
export function placeMeta(info: PlaceInfo | null | undefined, t: Translate): string {
  if (!info) return "";
  return [placeKindLabel(info.kind, t), info.category, info.address].filter(Boolean).join(" · ");
}

/** The small tag beside a place's name saying where it was found. */
export function SourceTag({ origin }: { origin: string | null | undefined }) {
  const t = useT();
  const label = sourceLabel(origin, t);
  return label ? <span className={styles.sourceTag} data-origin={origin ?? undefined}>{label}</span> : null;
}

/** Why a step did not happen, in the server's own words when it said no (`LiveError.message`). */
export const reason = (error: unknown) => error instanceof Error ? error.message : String(error);

/** A button that stays reachable when it cannot act: pressing it says why (mockup: 「꺼진 버튼을 누르면 이유를 알려 준다」). */
export function Act({ why, onPress, explain, className, children, title, ...rest }: {
  why: string | null; onPress: () => void; explain: (why: string) => void; className?: string; children: ReactNode;
  id?: string; title?: string; "aria-label"?: string; "aria-pressed"?: boolean; "data-primary"?: boolean; "data-edge"?: string; style?: CSSProperties;
  /** `[2026-10-05]` Something a time is dragged by: the pointer handlers of a drag, and the mark for the cursor and the touch (`data-grab`). */
  "data-grab"?: boolean; onPointerDown?: Grab["onPointerDown"]; onPointerMove?: Grab["onPointerMove"]; onPointerUp?: Grab["onPointerUp"]; onPointerCancel?: Grab["onPointerCancel"];
}) {
  return <button type="button" className={className} aria-disabled={why ? true : undefined} title={why ?? title} {...rest}
    onClick={() => why ? explain(why) : onPress()}>{children}</button>;
}

/** 「A」 「B」 「C」 for the change screen's cards and pins (the current stop is card 0). */
export const letter = (index: number) => "ABCDEFGH"[index - 1] ?? String(index);

/** What the list can be narrowed to by pressing a count in the sheet's head: only what needs a look, or only what was changed. */
export type ListFilter = "needs" | "changed";

/**
 * ★`[2026-10-04 사용자 지시]` The sheet's head says the state in marks and numbers, not a sentence that wrapped to a second line (「장소 3곳 확인 필요」):
 * 「! 3」 = three need a look, 「✎ 2」 = two were changed — each can be pressed to see only those. Nothing to say: a single ✓.
 */
export function HeadBadges({ needs, changed, filter, onFilter, registered, rechecking, needsOnMap = false }: {
  needs: number; changed: number; filter: ListFilter | null; onFilter: (next: ListFilter | null) => void;
  registered: boolean; rechecking: { at: number; of: number } | null;
  /** `[2026-10-07]` The 「! n」 count stands on the map instead of here. */
  needsOnMap?: boolean;
}) {
  const t = useT();
  if (registered) return <span className={styles.headBadge} data-kind="ok"><span className={styles.mark} data-result="ok" aria-hidden="true">✓</span>{t("등록 완료", "Registered")}</span>;
  if (rechecking) return <span className={styles.headBadge} data-kind="wait" role="status"><span className={styles.spinner} aria-hidden="true" />{rechecking.at}/{rechecking.of}<span className="sr-only">{t("재검증 중", "Checking again")}</span></span>;
  const toggle = (kind: ListFilter) => onFilter(filter === kind ? null : kind);
  return <span className={styles.headBadges}>
    {needs > 0 && !needsOnMap && <button type="button" className={styles.headBadge} data-kind="needs" aria-pressed={filter === "needs"} onClick={() => toggle("needs")}
      aria-label={t(`확인 필요 ${needs}곳`, `${needs} to check`)} title={filter === "needs" ? t("눌러서 전체 일정 보기", "Press to show every stop") : t("눌러서 확인이 필요한 곳만 모아 보기", "Press to show only what needs a look")}>
      <span className={styles.mark} data-result="warn" aria-hidden="true">!</span><b>{needs}</b></button>}
    {changed > 0 && <button type="button" className={styles.headBadge} data-kind="changed" aria-pressed={filter === "changed"} onClick={() => toggle("changed")}
      aria-label={t(`바뀐 일정 ${changed}곳`, `${changed} changed`)} title={filter === "changed" ? t("눌러서 전체 일정 보기", "Press to show every stop") : t("눌러서 바뀐 곳만 모아 보기", "Press to show only what changed")}>
      <span className={styles.mark} data-result="filled" aria-hidden="true">✎</span><b>{changed}</b></button>}
    {needs === 0 && changed === 0 && <span className={styles.headBadge} data-kind="ok"><span className={styles.mark} data-result="ok" aria-hidden="true">✓</span><span className="sr-only">{t("고칠 곳이 없어요", "Nothing to fix")}</span></span>}
  </span>;
}
