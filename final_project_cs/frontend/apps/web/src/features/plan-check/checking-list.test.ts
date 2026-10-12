import { describe, expect, it } from "vitest";
import { checkingList } from "./checking-list";
import { exampleDone } from "./test-views";
import type { PlanCheckView, PlanLine } from "./model";

const empty = (): PlanCheckView => ({ ...exampleDone, stage: "checking", days: [], lines: [], items: [], moves: [] });
const line = (id: string, no: number, extra: Partial<Extract<NonNullable<PlanLine["found"]>, { kind: "item" }>> = {}): PlanLine => ({
  no, text: "읽힌 여행 일정", read: true, found: { kind: "item", id, day: 1, date: "2026-10-01", startsAt: "10:00", title: "경복궁", ...extra },
});

describe("검증보다 먼저 읽힌 일정 목록", () => {
  it("최종 응답이 먼저 와도 미래 결과·이동을 미리 보여주지 않고 전체 카드를 유지한다", () => {
    const shown = { ...empty(), items: [{ ...exampleDone.items[0], verdict: null, checks: [] }] };
    const list = checkingList(shown, exampleDone);
    expect(list.view.items).toHaveLength(4);
    expect(list.activeId).toBe("a");
    expect([...list.waiting]).toEqual(["b", "c", "d"]);
    expect(list.view.items[0]).toBe(shown.items[0]);
    expect(list.view.moves).toHaveLength(0);
    for (const item of list.view.items.slice(1)) expect(item).toMatchObject({ checks: [], verdict: null, coordinates: null, info: null, suggestion: null });
    expect(exampleDone.items[1].verdict).toBe("review");
  });
  it("검증 item이 하나도 없어도 이미 읽힌 제목·시각만 표시한다", () => {
    const source = { ...empty(), lines: [line("a", 1), line("b", 2, { startsAt: "12:00", title: "광장시장" })] };
    const list = checkingList(empty(), source);
    expect(list.view.items.map(item => [item.id, item.title, item.startsAt])).toEqual([["a", "경복궁", "10:00"], ["b", "광장시장", "12:00"]]);
    expect(list.activeId).toBeNull();
    expect(list.waiting.size).toBe(2);
    expect(list.view.items.every(item => !item.endsAt && !item.place && !item.coordinates && item.verdict === null)).toBe(true);
  });
  it("같은 제목 두 개를 id로 구분하고 실제 검증 도착 시 같은 카드를 대체한다", () => {
    const source = { ...empty(), lines: [line("a", 1), line("b", 2)], items: [{ ...exampleDone.items[0], id: "b" }] };
    const list = checkingList({ ...empty(), items: source.items }, source);
    expect(list.view.items.map(item => item.id)).toEqual(["a", "b"]);
    expect(list.view.items[1]).toBe(source.items[0]);
    expect([...list.waiting]).toEqual(["a"]);
    expect(list.activeId).toBe("b");
  });
  it("날짜·일차·시각이 없으면 지어내지 않고 미정 그룹으로 둔다", () => {
    const list = checkingList(empty(), { ...empty(), lines: [line("a", 1, { day: null, date: null, startsAt: null })] });
    expect(list.view.days).toEqual([{ day: 0, date: "" }]);
    expect(list.view.items[0]).toMatchObject({ day: 0, date: "", startsAt: "", endsAt: "" });
  });
  it("읽지 않은 줄·날짜 줄·일정으로 인식되지 않은 이동 원문은 카드로 만들지 않는다", () => {
    const lines: PlanLine[] = [{ ...line("a", 1), read: false }, { no: 2, text: "10월1일", read: true, found: { kind: "date", date: "2026-10-01" } }, { no: 3, text: "지하철로 이동", read: true, found: null }];
    expect(checkingList(empty(), { ...empty(), lines }).view.items).toEqual([]);
  });
  it("완료 재방문은 전체 결과와 기존 view를 즉시 그대로 사용한다", () => {
    const list = checkingList(exampleDone, exampleDone);
    expect(list.view).toBe(exampleDone);
    expect(list.waiting.size).toBe(0);
    expect(list.activeId).toBeNull();
  });
  it("검증 중인 이동을 따라가며 미래 카드로 점프하지 않는다", () => {
    const shown = { ...empty(), items: [exampleDone.items[0]], moves: [exampleDone.moves[0]] };
    const list = checkingList(shown, exampleDone);
    expect(list.activeId).toBe("a-b");
    expect(list.view.moves).toBe(shown.moves);
  });
  it("기존 intake 결과의 별도 source key도 같은 일정으로 합친다", () => {
    const source = { ...empty(), lines: [line("0-0", 1, { sourceKey: "source:0" })], items: [{ ...exampleDone.items[0], id: "source:0" }] };
    expect(checkingList(empty(), source).view.items.map(item => item.id)).toEqual(["source:0"]);
  });
});
