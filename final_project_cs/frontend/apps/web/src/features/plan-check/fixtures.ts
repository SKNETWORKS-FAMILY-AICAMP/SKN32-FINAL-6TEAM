import type { CheckRow, PlanCheckView, PlanItem, PlanLine, PlanMove } from "./model";

/**
 * ★Example data for the preview page only — the mockup's example (`mockups/tripilot-plan-check-streaming.html`), not a
 *   server answer. Place names, times, hours and distances are made up; the coordinates are the real landmarks'.
 */
const row = (kind: CheckRow["kind"], result: CheckRow["result"], text: string): CheckRow => ({ kind, result, text });

const items: PlanItem[] = [
  { id: "a", day: 1, date: "2026-10-01", startsAt: "10:00", endsAt: "11:30", title: "경복궁", place: "경복궁", noPlace: false, coordinates: { lat: 37.5796, lng: 126.977 }, verdict: "keep",
    checks: [row("place", "ok", "관광공사 정보로 찾았어요"), row("hours", "ok", "09:00–18:00 안에 머물러요"), row("closed", "ok", "화요일 휴무 · 방문은 목요일")] },
  { id: "b", day: 1, date: "2026-10-01", startsAt: "11:00", endsAt: "", title: "올리브영", place: "", noPlace: false, coordinates: null, verdict: "review",
    checks: [row("place", "bad", "지점이 여러 곳이라 정하지 못했어요"), row("time", "warn", "경복궁 관람과 30분 겹쳐요 · 등록 때 막힐 수 있어요"),
      row("hours", "unknown", "지점을 고르면 확인해요"), row("closed", "unknown", "지점을 고르면 확인해요")] },
  { id: "c", day: 1, date: "2026-10-01", startsAt: "12:30", endsAt: "13:30", title: "광장시장", place: "광장시장", noPlace: false, coordinates: { lat: 37.57, lng: 126.9996 }, verdict: "adjusted",
    checks: [row("place", "ok", "가게 이름이 없어 광장시장으로 잡았어요"), row("time", "filled", "끝 시각이 없어 식사 1시간으로 채웠어요"),
      row("hours", "ok", "09:00–23:00 안에 머물러요"), row("closed", "unknown", "점포마다 달라요")] },
  { id: "d", day: 2, date: "2026-10-02", startsAt: "15:00", endsAt: "", title: "N서울타워", place: "N서울타워", noPlace: false, coordinates: { lat: 37.5512, lng: 126.9882 }, verdict: "keep",
    checks: [row("place", "ok", "「남산타워」를 N서울타워로 찾았어요"), row("hours", "ok", "10:00–23:00 안에 머물러요"), row("closed", "ok", "연중무휴")] },
];

const moves: PlanMove[] = [
  { id: "a-b", fromId: "a", toId: "b", day: 1, departAt: "11:30", mode: "도보", summary: "12분 · 0.8km", verdict: "review",
    checks: [row("route", "warn", "올리브영 지점이 미정이라 가장 가까운 광화문점 기준이에요"), row("mode", "ok", "도보 12분 · 0.8km · 이 구간은 걷는 게 가장 빨라요"),
      row("arrival", "warn", "관람이 11:30에 끝나면 11:42 도착 · 일정보다 42분 늦어요")] },
  { id: "b-c", fromId: "b", toId: "c", day: 1, departAt: "12:00", mode: "지하철", summary: "18분 · 1호선 2정거장", verdict: "keep",
    checks: [row("route", "ok", "종각역 → 종로5가역 · 1호선 2정거장"), row("mode", "ok", "지하철 18분(걷기 7분 포함) · 택시보다 시간이 일정해요"),
      row("arrival", "ok", "12:00에 나서면 12:18 도착 · 12분 여유")] },
];

const lines: PlanLine[] = [
  { no: 1, text: "10월 1일 서울 여행", read: true, found: { kind: "date", date: "2026-10-01" } },
  { no: 2, text: "10시 경복궁 관람 1시간 반", read: true, found: { kind: "item", day: 1, startsAt: "10:00", title: "경복궁" } },
  { no: 3, text: "11시 올리브영", read: true, found: { kind: "item", day: 1, startsAt: "11:00", title: "올리브영" } },
  { no: 4, text: "12시 반 광장시장 빈대떡", read: true, found: { kind: "item", day: 1, startsAt: "12:30", title: "광장시장" } },
  { no: 5, text: "둘째 날 3시 남산타워", read: true, found: { kind: "item", day: 2, startsAt: "15:00", title: "남산타워" } },
];

const days = [{ day: 1, date: "2026-10-01" }, { day: 2, date: "2026-10-02" }];

/** The final state: every check in, the trip titled. */
export const exampleDone: PlanCheckView = { stage: "done", title: "10월 서울 여행", days, lines, items, moves };

/**
 * What a server might send, in four coarse snapshots — received, every line read, every check in, done. The screen
 * draws the changes between them one at a time (`nextStep`), as it would with a stream burst or a re-read.
 */
export const exampleSnapshots: { at: number; view: PlanCheckView }[] = [
  { at: 0, view: { stage: "received", title: null, days: [], lines: lines.map((line) => ({ ...line, read: false, found: null })), items: [], moves: [] } },
  { at: 400, view: { stage: "reading", title: null, days, lines, items: [], moves: [] } },
  { at: 1200, view: { ...exampleDone, stage: "checking", title: null } },
  { at: 1500, view: exampleDone },
];
