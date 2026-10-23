import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { itemRiskOf } from "@/lib/live/risks";
import { panelRisks, RiskPanel, riskTime } from "./risk-panel";

vi.mock("@/lib/settings", () => ({ useT: () => (ko: string) => ko }));
const render = (patch: Partial<Parameters<typeof RiskPanel>[0]>) => renderToStaticMarkup(createElement(RiskPanel, { items: [], ...patch }));

describe("위험 안내 카드", () => {
  // `[2026-10-22 사용자 지시]` 운영자가 점검 칸을 끄면 알림 센터에는 실제 위험만 — 확인 불가 · 위험 없음은 빠진다
  it("스위치를 끄면 실제 위험 일정만 남긴다", () => {
    const danger = itemRiskOf({ item_id: "i1", status: "problem", problems: [{ category: "weather", message: "호우 경보" }] })!;
    const unknown = itemRiskOf({ item_id: "i2", status: "unknown", unknown_categories: [{ label: "교통 통제" }] })!;
    const clear = itemRiskOf({ item_id: "i3", status: "clear" })!;
    expect(panelRisks([danger, unknown, clear], true)).toEqual([danger, unknown, clear]);
    expect(panelRisks([danger, unknown, clear], false)).toEqual([danger]);
    expect(panelRisks([unknown, clear], false)).toEqual([]);
  });

  it("도로통제 원문과 종료 시각·실내 대안 동작을 첫 화면에 남긴다", () => {
    const item = itemRiskOf({ item_id: "i1", title: "여행 활동", status: "problem", problems: [
      { category: "traffic_control", message: "행사 구간 양방향 전면 통제", source: "UTIC", ends_at: "2026-10-18T23:00:00+09:00" },
    ] })!;
    const html = render({ items: [item], onAlternatives: () => {} });
    expect(html).toContain("주의할 일정 1개");
    expect(html).toContain("행사 구간 양방향 전면 통제");
    expect(html).toContain("UTIC");
    expect(html).toContain("23:00");
    expect(html).toContain("실내 대안 보기");
  });
  it("확인 불가·조회 오류·점검 대상 없음 모두를 위험 없음과 구별한다", () => {
    const unknown = itemRiskOf({ item_id: "i1", status: "unknown", unknown_categories: [{ label: "교통 통제" }] })!;
    expect(render({ items: [unknown] })).toContain("교통 통제");
    expect(render({ items: [unknown] })).not.toContain("겹치는 위험이 없어요");
    expect(render({ error: true, retry: () => {} })).toContain("현재 위험을 확인하지 못했어요");
    expect(render({})).toContain("현재 점검 대상 일정이 없어요");
  });
  it("오래된 확인 결과와 아직 먼 방문 시각의 현재 상황을 구별한다", () => {
    const item = itemRiskOf({ item_id: "i1", status: "problem", stale: true, data_confirmed_at: "2026-10-18T12:00:00+09:00",
      problems: [{ category: "weather_warning", kind: "강풍주의보", as_of_now: true }] })!;
    const html = render({ items: [item] });
    expect(html).toContain("이전 확인 결과");
    expect(html).toContain("현재 상황이며 방문 시각에 다시 확인");
    expect(html).toContain("자료 확인");
  });
  it("검증을 마친 정상 결과만 겹치는 위험 없음으로 표시한다", () => {
    expect(render({ items: [itemRiskOf({ item_id: "i1", status: "clear" })!] })).toContain("최근 확인에서 겹치는 위험이 없어요");
    expect(riskTime("not-a-date")).toBeNull();
  });
  it("첫 조회 개수 상한으로 제외된 일정을 정상으로 표현하지 않는다", () => {
    const items = [itemRiskOf({ item_id: "i1", status: "clear" })!];
    const html = render({ items, scope: { tripId: "t1", version: 1, mode: "fresh", at: null, items, horizonHours: 6,
      skipped: [{ title: "다음 방문지", reason: "over_limit", note: "한 번에 최대 1개까지 점검해요" }] } });
    expect(html).toContain("아직 확인하지 못한 일정");
    expect(html).toContain("6시간 이내 대상");
    expect(html).toContain("제외 1개");
    expect(html).not.toContain("겹치는 위험이 없어요");
  });
});
