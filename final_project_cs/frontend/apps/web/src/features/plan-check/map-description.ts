import type { Translate } from "@/lib/i18n";
import type { BusToast } from "@/lib/toast-bus";
import type { PlanItem, PlanMove } from "./model";

/** A description has more to read than 「되돌렸어요」: it stays this long (the pointer on its button keeps it). */
const READ_MS = 7_000;

/** 「확인 필요」 reads as a warning, 「통과」 as fine; nothing yet (still checking) says nothing. */
function verdictChip(verdict: PlanItem["verdict"], t: Translate): BusToast["chip"] | undefined {
  if (verdict === "review") return { text: t("확인 필요", "Needs a look"), tone: "warn" };
  if (verdict === "adjusted") return { text: t("바뀜", "Changed"), tone: "changed" };
  if (verdict === "keep") return { text: t("통과", "OK"), tone: "ok" };
  return undefined;
}

/** The first thing the check found that is not fine, as one line 「이름이 여러 곳이라…」. */
function firstIssue(checks: PlanItem["checks"]): string | undefined {
  const bad = checks.find((check) => check.result !== "ok" && check.text.trim());
  return bad ? bad.text.trim() : undefined;
}

/**
 * `[2026-10-06 사용자 지시 — 마커를 누르면 그 설명이, 경로를 누르면 그 경로가 나온다 · 알림은 하나의 포맷으로]` What a pin or a route line pressed on the map says, as the same notice every screen uses
 * (`components/toast-view.tsx`) - not a card of its own. Only what the plan check already holds is shown; nothing is made up. 「목록에서 보기」 brings the same stop or leg up in the sheet.
 */
export function stopToast(stop: { order: number; item: PlanItem }, t: Translate, onList: () => void): BusToast {
  const { item } = stop;
  const when = `${item.startsAt}${item.endsAt ? `–${item.endsAt}` : ""}${item.place && item.place !== item.title ? ` · ${item.place}` : ""}`;
  return {
    badge: String(stop.order),
    text: item.title,
    chip: verdictChip(item.verdict, t),
    sub: [when, item.info?.address].filter(Boolean).join("\n"),
    note: firstIssue(item.checks),
    action: { label: t("목록에서 보기", "Show in list"), run: onList },
    ms: READ_MS,
  };
}

export function moveToast(leg: { move: PlanMove; from: string; to: string }, t: Translate, onList: () => void): BusToast {
  const { move } = leg;
  const how = move.summary.includes(move.mode) ? move.summary : `${move.mode}${move.summary ? ` · ${move.summary}` : ""}`;
  const times = move.departAt || move.arriveAt
    ? `${move.departAt ? t(`${move.departAt} 출발`, `Leave ${move.departAt}`) : ""}${move.arriveAt ? `${move.departAt ? " → " : ""}${t(`${move.arriveAt} 도착`, `arrive ${move.arriveAt}`)}` : ""}${move.estimated ? ` · ${t("직선 거리로 어림한 시간", "estimated from the straight distance")}` : ""}` : null;
  return {
    badge: "→",
    text: `${leg.from} → ${leg.to}`,
    chip: verdictChip(move.verdict, t),
    sub: [how, times].filter(Boolean).join("\n"),
    note: firstIssue(move.checks),
    action: { label: t("목록에서 보기", "Show in list"), run: onList },
    ms: READ_MS,
  };
}
