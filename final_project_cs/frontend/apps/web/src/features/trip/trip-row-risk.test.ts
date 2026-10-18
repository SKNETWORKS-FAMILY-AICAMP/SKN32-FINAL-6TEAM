import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { itemRiskOf } from "@/lib/live/risks";
import type { TripStop } from "./model";
import { StopRow } from "./trip-rows";

vi.mock("@/lib/settings", () => ({ useT: () => (ko: string) => ko }));
const stop: TripStop = { id: "current-activity", date: "2026-10-18", time: "15:15", endTime: "17:00",
  title: "야외 활동", booking: "unknown", notes: "", kind: "activity" };
const risk = itemRiskOf({ item_id: stop.id, status: "problem", problems: [
  { category: "weather_warning", label: "기상 특보", message: "강풍주의보" },
  { category: "traffic_control", label: "교통 통제", message: "행사 구간 전면 통제" },
] })!;
const render = (patch: Partial<Parameters<typeof StopRow>[0]> = {}) => renderToStaticMarkup(createElement(StopRow, {
  stop, open: false, selected: false, onToggle: () => {}, onDetail: () => {}, onMapApps: () => {}, risk, onRisk: () => {}, ...patch,
}));

describe("현재·예정 일정 카드의 위험 접근", () => {
  it("접힌 카드에서도 원인 유형과 자세히 보기 동작을 보여 준다", () => {
    const html = render();
    expect(html).toContain('data-stop-risk="current-activity"');
    expect(html).toContain("강풍주의보 · 행사 구간 전면 통제");
    expect(html).toContain('aria-label="야외 활동 위험·대안 보기"');
    expect(html).not.toContain('id="stop-detail-current-activity"');
  });
  it("카드가 열리거나 지도에서 선택되어도 경고가 유지된다", () => {
    expect(render({ open: true, selected: true })).toContain("위험·대안 보기");
  });
  it.each([
    ["지난 일정", { past: true }],
    ["다른 항목", { risk: { ...risk, itemId: "another-stop" } }],
    ["미확인", { risk: { ...risk, status: "unknown" as const } }],
    ["정상", { risk: { ...risk, status: "clear" as const } }],
    ["미응답", { risk: undefined }],
  ])("%s을 새 위험으로 표시하지 않는다", (_name, patch) => {
    expect(render(patch)).not.toContain("data-stop-risk");
  });
  it("자료 유형명이 없으면 실제 원문을 쓰고 내용이 비어도 정상으로 표시하지 않는다", () => {
    expect(render({ risk: { ...risk, problems: risk.problems.map((problem) => ({ ...problem, label: "" })) } })).toContain("강풍주의보 · 행사 구간 전면 통제");
    expect(render({ risk: { ...risk, problems: [] } })).toContain("확인된 위험이 있어요");
  });
});
