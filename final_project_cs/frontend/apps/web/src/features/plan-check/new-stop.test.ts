import { afterEach, describe, expect, it, vi } from "vitest";
import type { IntakeSource } from "@/lib/live/intake";
import type { Candidate, ReviewedIntakeView } from "@/lib/live/intake-review";
import { LiveError } from "@/lib/live/client";
import { newStopEdits, type NewStop } from "./new-stop";
import { useServerReview } from "./use-server-review";

const harness = vi.hoisted(() => ({
  slots: [] as { value?: unknown; deps?: readonly unknown[]; cleanup?: () => void }[], cursor: 0,
  effects: [] as (() => void)[], edit: vi.fn(), search: vi.fn(),
}));
vi.mock("@/lib/live/intake", () => ({ editIntake: harness.edit, restoreIntake: vi.fn() }));
vi.mock("@/lib/live/intake-review", async (original) => ({
  ...await original<typeof import("@/lib/live/intake-review")>(), searchPlaces: harness.search,
}));
vi.mock("react", () => ({
  useState: (value: unknown) => {
    const at = harness.cursor++, slot = harness.slots[at] ??= { value };
    return [slot.value, (next: unknown) => { slot.value = typeof next === "function" ? next(slot.value) : next; }];
  },
  useRef: (value: unknown) => (harness.slots[harness.cursor++] ??= { value: { current: value } }).value,
  useMemo: (make: () => unknown, deps: readonly unknown[]) => {
    const at = harness.cursor++, old = harness.slots[at];
    if (!old?.deps || deps.some((value, index) => !Object.is(value, old.deps![index]))) harness.slots[at] = { value: make(), deps };
    return harness.slots[at].value;
  },
  useEffect: (run: () => void | (() => void), deps?: readonly unknown[]) => {
    const slot = harness.slots[harness.cursor++] ??= {};
    if (deps && slot.deps && deps.every((value, index) => Object.is(value, slot.deps![index]))) return;
    slot.deps = deps;
    harness.effects.push(() => { slot.cleanup?.(); const cleanup = run(); slot.cleanup = typeof cleanup === "function" ? cleanup : undefined; });
  },
}));

const chosen = { name: "광장시장 식당 지점", latitude: 37.5701, longitude: 126.9991, source: "tour_api" as const, kind: "dining", content_id: "tour-place-123" };
const draft: NewStop = { title: "점심 식사", date: "2026-10-15", start: "11:40", end: "12:30", place: "잘못된 옛 이름", kind: "dining", pickedPlace: chosen };
const source = { source_id: "source-a", trip: {}, items: [
  { index: 0, fields: { title: { value: "경복궁" } } },
  { index: 4, fields: { removed: { value: true } } },
] } as IntakeSource;
function plan(id = "intake-a", revision = 7): ReviewedIntakeView {
  return { intake_id: id, revision, status: "review", sources: [source], review: {
    revision, items: [{ id: "0-0", source_id: "source-a", index: 0 }], needs: { total: 0 },
  } } as ReviewedIntakeView;
}
function draw(view = plan(), apply = vi.fn(), reread = vi.fn()) {
  harness.cursor = 0; harness.effects = [];
  // eslint-disable-next-line react-hooks/rules-of-hooks -- 실제 hook의 요청 경계를 React 저장소 대역으로 검사한다.
  const screen = useServerReview({ view, intakeId: view.intake_id, apply, reread, language: "ko" });
  harness.effects.forEach((run) => run());
  return screen;
}
function result(located = true): Candidate {
  return { rank: 1, place: { ...chosen, latitude: located ? chosen.latitude : null, longitude: located ? chosen.longitude : null,
    category: "한식", address: "서울 종로구 시험 주소", ref: "tour:tour-place-123" }, rows: [], distance_m: 100, reference: "경복궁",
    fits: true, status: "ok", slack: { before: 20, after: 20 }, estimated: false };
}
afterEach(() => {
  harness.slots.forEach((slot) => slot.cleanup?.());
  harness.slots = []; harness.effects = []; harness.cursor = 0;
  harness.edit.mockReset(); harness.search.mockReset();
});

describe("신규 일정의 선택 장소 저장", () => {
  it("삭제 이력 최대 번호 다음에 정확한 장소를 여섯 필드와 함께 저장한다", () => {
    const added = newStopEdits(source, draft);
    expect(added.index).toBe(5);
    expect(added.edits).toHaveLength(6);
    expect(added.edits.every((edit) => edit.source_id === "source-a" && edit.field.startsWith("items[5]."))).toBe(true);
    expect(added.edits.find((edit) => edit.field.endsWith(".place"))?.value).toBe(chosen);
    expect(added.edits.find((edit) => edit.field.endsWith(".starts_at"))?.value).toBe("11:40");
    expect(source.items).toHaveLength(2);
  });
  it("빈 계획의 기존 이름 입력 계약도 유지한다", () => {
    const added = newStopEdits({ ...source, items: [] }, { ...draft, pickedPlace: undefined, place: "서울숲" });
    expect(added.index).toBe(0);
    expect(added.edits.find((edit) => edit.field.endsWith(".place"))?.value).toEqual({ name: "서울숲" });
  });
  it("실제 추가 action은 선택 원값을 이름 검색으로 바꾸지 않고 최신 응답을 적용한다", async () => {
    const apply = vi.fn(), screen = draw(plan(), apply);
    harness.edit.mockResolvedValue(plan("intake-a", 8));
    await screen.actions.add!(draft);
    expect(harness.edit).toHaveBeenCalledExactlyOnceWith("intake-a", 7, newStopEdits(source, draft).edits, "ko");
    expect(apply).toHaveBeenCalledWith(expect.objectContaining({ revision: 8 }));
    expect(draw(plan("intake-a", 8)).dirty).toBe(true);
    expect(harness.search).not.toHaveBeenCalled();
  });
  it("추가 실패는 현재 판과 전체 되돌리기 원판을 바꾸지 않는다", async () => {
    const apply = vi.fn(), screen = draw(plan(), apply);
    harness.edit.mockRejectedValueOnce(new LiveError("schedule_conflict", "예약 일정과 겹쳐요"));
    await expect(screen.actions.add!(draft)).rejects.toMatchObject({ code: "schedule_conflict" });
    expect(apply).not.toHaveBeenCalled();
    expect(screen.actions.canUndoAll!()).toBe(false);
    expect(draw().dirty).toBe(false);
  });
});

describe("일정 경계를 기준으로 장소 검색", () => {
  it("경계의 실제 일정과 최신 판을 보내고 출처·좌표·관광 식별값을 모두 보존한다", async () => {
    const screen = draw();
    harness.search.mockResolvedValue({ results: [result()] });
    const found = await screen.actions.searchToAdd!("0-0", "광장시장");
    expect(harness.search).toHaveBeenCalledExactlyOnceWith("intake-a", expect.objectContaining({ source_id: "source-a", index: 0 }), 7, "광장시장", "ko");
    expect(found[0].pickedPlace).toEqual(chosen);
    expect(found[0].info?.address).toBe("서울 종로구 시험 주소");
    expect(harness.edit).not.toHaveBeenCalled();
  });
  it("좌표 없는 검색 결과는 선택 가능한 장소로 만들지 않는다", async () => {
    const screen = draw();
    harness.search.mockResolvedValue({ results: [result(false)] });
    expect((await screen.actions.searchToAdd!("0-0", "광장시장"))[0].pickedPlace).toBeNull();
  });
  it("오래된 판 검색 거절은 다시 읽고 쓰기 요청을 만들지 않는다", async () => {
    const reread = vi.fn(), screen = draw(plan(), vi.fn(), reread);
    harness.search.mockRejectedValueOnce(new LiveError("stale_revision", "다시 읽어요"));
    await expect(screen.actions.searchToAdd!("0-0", "광장시장")).rejects.toMatchObject({ code: "stale_revision" });
    expect(reread).toHaveBeenCalledOnce();
    expect(harness.edit).not.toHaveBeenCalled();
  });
  it("다른 접수로 이동한 뒤 도착한 검색 결과는 이전 입력기로 돌려주지 않는다", async () => {
    const first = draw();
    let release: (value: { results: Candidate[] }) => void = () => undefined;
    harness.search.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
    const pending = first.actions.searchToAdd!("0-0", "광장시장");
    draw(plan("intake-b"));
    release({ results: [result()] });
    await expect(pending).rejects.toMatchObject({ code: "item_gone" });
    expect(harness.edit).not.toHaveBeenCalled();
  });
});
