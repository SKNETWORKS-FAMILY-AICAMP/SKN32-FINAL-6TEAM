import { afterEach, describe, expect, it, vi } from "vitest";
import { getPlacePhotos, type Candidate, type ReviewedIntakeView } from "@/lib/live/intake-review";
import { useServerReview } from "./use-server-review";

// `[2026-10-20 사용자 지시]` 수정 화면은 저장만 하고(시각 · 장소 · 대안), 무거운 검사는 「다시 제출」 때 한 번에 — 대안은 다시 제출 전까지 처음 받은 셋을 그대로 보인다.
const harness = vi.hoisted(() => ({
  slots: [] as { value?: unknown; deps?: readonly unknown[]; cleanup?: () => void }[], cursor: 0,
  effects: [] as (() => void)[], edit: vi.fn(), stream: vi.fn(), revalidate: vi.fn(), autofix: vi.fn(), interpret: vi.fn(),
}));
vi.mock("@/lib/live/intake", () => ({ editIntake: harness.edit, restoreIntake: vi.fn(), answerInterpretations: harness.interpret }));
vi.mock("@/lib/live/intake-review", async (original) => ({
  ...await original<typeof import("@/lib/live/intake-review")>(),
  streamCandidates: harness.stream, revalidateIntake: harness.revalidate, autofixIntake: harness.autofix,
  getPlacePhotos: vi.fn().mockResolvedValue({ photos: [], source_note: null }),
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

function plan(revision = 3, checked?: boolean, needs = 0): ReviewedIntakeView {
  return { intake_id: "deferred-intake", revision, status: "review", sources: [{ source_id: "source-a", trip: {}, items: [] }],
    review: { revision, needs: { total: needs }, ...(checked === undefined ? {} : { checked }), items: [{ id: "0-0", source_id: "source-a", index: 0, kind: "activity",
      title: "경복궁", date: "2030-01-05", starts_at: "12:00", ends_at: "13:30", place: null, locked: false }] } } as unknown as ReviewedIntakeView;
}

function candidate(name: string, rank: number): Candidate {
  return { rank, place: { name, kind: "activity", source: "tour_api", latitude: 37.57, longitude: 126.98,
    address: null, category: null, ref: `tour:${rank}`, content_id: String(rank), content_type_id: null },
    rows: [], fits: true, status: "ok", distance_m: null, reference: null, slack: { before: null, after: null }, estimated: false };
}

function draw(view: ReviewedIntakeView, apply = vi.fn(), waitWarmUp = false) {
  harness.cursor = 0; harness.effects = [];
  // eslint-disable-next-line react-hooks/rules-of-hooks -- Real action boundaries use controlled React storage in this Node harness.
  const screen = useServerReview({ intakeId: view.intake_id, view, apply, reread: vi.fn(), language: "ko", waitWarmUp });
  for (const run of harness.effects) run();
  return screen;
}

afterEach(() => {
  for (const slot of harness.slots) slot.cleanup?.();
  harness.slots = []; harness.cursor = 0; harness.effects = [];
  harness.edit.mockReset(); harness.stream.mockReset(); harness.revalidate.mockReset(); harness.autofix.mockReset(); harness.interpret.mockReset();
});

describe("plan check saves changes and checks them once, when sent again", () => {
  it("saves a time change without the check and keeps a lock checked", async () => {
    harness.edit.mockResolvedValue(plan(4, false));
    const screen = draw(plan());
    await screen.actions.retime!([{ id: "0-0", start: "13:00", end: "14:30" }]);
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 3, expect.any(Array), "ko", { check: false });
    harness.edit.mockResolvedValue(plan(5));
    await screen.actions.lock!("0-0", true);
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 4, [{ source_id: "source-a", field: "items[0].locked", value: true }], "ko");
  });

  it("keeps 「다시 제출」 for a revision only saved, and asks no recommendation for it", () => {
    const screen = draw(plan(4, false, 1));
    expect(screen.dirty).toBe(true);
    expect(harness.autofix).not.toHaveBeenCalled();
    harness.autofix.mockReturnValue(new Promise(() => undefined));
    expect(draw(plan(5, true, 1)).dirty).toBe(false);
    expect(harness.autofix).toHaveBeenCalledOnce();
  });

  it("shows the same three alternatives after one is picked, and asks again only after the plan is sent again", async () => {
    harness.stream.mockResolvedValue({ candidates: [candidate("창덕궁", 1), candidate("덕수궁", 2), candidate("창경궁", 3)], notes: [] });
    let view = plan();
    const screen = draw(view, vi.fn((next: ReviewedIntakeView) => { view = next; }));
    const first = await screen.actions.candidates!("0-0");
    expect(first.map((card) => card.name)).toEqual(["창덕궁", "덕수궁", "창경궁"]);
    harness.edit.mockResolvedValue(plan(4, false));
    await screen.actions.replace!("0-0", { candidate: first[1] });
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 3, expect.any(Array), "ko", { check: false });
    draw(view);
    const again = await screen.actions.candidates!("0-0");
    expect(again.map((card) => card.name)).toEqual(["창덕궁", "덕수궁", "창경궁"]);
    expect(harness.stream).toHaveBeenCalledOnce();
    harness.revalidate.mockResolvedValue(plan(4, true));
    await screen.actions.recheck!();
    await screen.actions.candidates!("0-0");
    expect(harness.stream).toHaveBeenCalledTimes(2);
  });

  it("`[2026-10-20 C안]` saves a pick inside the first check's question WITH the check — no 「다시 제출」, no undo, the alternatives asked again", async () => {
    harness.stream.mockResolvedValue({ candidates: [candidate("창덕궁", 1), candidate("덕수궁", 2)], notes: [] });
    let view = plan();
    const screen = draw(view, vi.fn((next: ReviewedIntakeView) => { view = next; }));
    const first = await screen.actions.candidates!("0-0");
    harness.edit.mockResolvedValue(plan(4, true));
    await screen.actions.replace!("0-0", { candidate: first[1] }, { flow: true });
    // `[2026-10-25 이동 확인 C안대로]` checked, the other stops' times kept — a late leg is asked about by the card it comes into
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 3, expect.any(Array), "ko", { keepTimes: true });
    const after = draw(view);
    expect(after.dirty).toBe(false);
    expect(after.actions.canUndo!()).toBe(false);
    await after.actions.candidates!("0-0");
    expect(harness.stream).toHaveBeenCalledTimes(2);
  });

  it("`[2026-10-20 C안]` keeps the place the server took for now as the customer's pick", async () => {
    const taken = { ...plan(), review: { ...plan().review!, items: [{ ...plan().review!.items[0], place_state: "picked_nearest",
      place: { name: "올리브영 광화문점", latitude: 37.571, longitude: 126.976, source: "kakao", kind: null } }] } } as unknown as ReviewedIntakeView;
    harness.edit.mockResolvedValue(plan(4, true));
    const screen = draw(taken);
    await screen.actions.confirmPlace!("0-0", { flow: true });
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 3,
      [{ source_id: "source-a", field: "items[0].place", value: { name: "올리브영 광화문점", latitude: 37.571, longitude: 126.976, source: "kakao" } }], "ko", { keepTimes: true });
  });
});

describe("`[2026-10-21 사용자 결정]` the answer to what a line means, and a deletion saved at once", () => {
  it("sends the answer with the plan's revision and takes what comes back — the plan as it now is", async () => {
    const apply = vi.fn();
    harness.interpret.mockResolvedValue(plan(4));
    const screen = draw(plan(), apply);
    await screen.actions.interpret!("q-0-5", "item");
    expect(harness.interpret).toHaveBeenCalledWith("deferred-intake", 3, { "q-0-5": "item" }, "ko");
    expect(apply).toHaveBeenLastCalledWith(expect.objectContaining({ revision: 4 }));
    expect(harness.edit).not.toHaveBeenCalled();
  });

  it("takes a stop out saved only, and its 「되돌리기」 puts it back the same way — by the keys kept when it went (the plan no longer holds it)", async () => {
    harness.edit.mockResolvedValue({ ...plan(4, false), review: { ...plan(4, false).review!, items: [] } });
    const screen = draw(plan());
    await screen.actions.remove!("0-0");
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 3, [{ source_id: "source-a", field: "items[0].removed", value: true }], "ko", { check: false });
    harness.edit.mockResolvedValue(plan(5, false));
    await screen.actions.putBack!("0-0");
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 4, [{ source_id: "source-a", field: "items[0].removed", value: false }], "ko", { check: false });
    await expect(screen.actions.putBack!("0-0")).rejects.toThrow();                // put back already: nothing kept to put back
  });
});

describe("`[2026-10-21 사용자 지적 — 멈춘 질문 칸이 「후보를 찾는 중…」에 오래 머묾]` the alternatives come to every ask at once", () => {
  it("gives a second ask of the same stop the first cards already come and each update after — not only the whole answer at its end", async () => {
    let first!: (list: unknown) => void;
    let update!: (change: unknown) => void;
    let end!: (list: unknown) => void;
    harness.stream.mockImplementation((_id: string, _item: unknown, _revision: number, _language: string, onFirst: (list: unknown) => void, onUpdate: (change: unknown) => void) => {
      first = onFirst; update = onUpdate;
      return new Promise((resolve) => { end = resolve; });
    });
    const screen = draw(plan());
    const one = screen.actions.candidates!("0-0", vi.fn());
    first({ candidates: [candidate("창덕궁", 1), candidate("덕수궁", 2)], notes: [] });
    const later = vi.fn();
    const two = screen.actions.candidates!("0-0", later);
    await vi.waitFor(() => expect(later).toHaveBeenCalled());
    expect(later.mock.calls.at(-1)![0].map((card: { name: string }) => card.name)).toEqual(["창덕궁", "덕수궁"]);
    update({ rank: 1, reason: "경복궁에서 가까워요", pending: { reason: false } });
    await vi.waitFor(() => expect(later.mock.calls.at(-1)![0][0].reason).toContain("경복궁에서 가까워요"));
    end({ candidates: [candidate("창덕궁", 1), candidate("덕수궁", 2)], notes: [] });
    await Promise.all([one, two]);
    expect(harness.stream).toHaveBeenCalledOnce();                                  // one live answer for both
  });

  it("shows prepared alternatives (they come whole) at once, before their photos come", async () => {
    // `[2026-10-24 ST4F-731]` the stopped question waited for six photo reads after the prepared alternatives had come (89.6 s → 97.3 s)
    harness.stream.mockResolvedValue({ candidates: [candidate("창덕궁", 1), candidate("덕수궁", 2)], notes: [] });
    vi.mocked(getPlacePhotos).mockImplementation(() => new Promise(() => undefined));
    try {
      const screen = draw(plan());
      const live = vi.fn();
      void screen.actions.candidates!("0-0", live);
      await vi.waitFor(() => expect(live).toHaveBeenCalled());
      expect(live.mock.calls[0][0].map((card: { name: string }) => card.name)).toEqual(["창덕궁", "덕수궁"]);
    } finally {
      vi.mocked(getPlacePhotos).mockResolvedValue({ ref: "", photos: [], source_note: null, reason: null });
    }
  });

  it("waits with the dry run while the page still shows the reading, and asks it once the page does not", () => {
    // `[2026-10-24 ST4F-731]` 「계획을 다 읽었어요」 is drawn without the plan check's calls — the page says so itself
    harness.autofix.mockReturnValue(new Promise(() => undefined));
    draw(plan(5, true, 1), vi.fn(), true);
    expect(harness.autofix).not.toHaveBeenCalled();
    draw(plan(5, true, 1), vi.fn(), false);
    expect(harness.autofix).toHaveBeenCalledOnce();
  });

  it("holds the 「전체 자동 추천」 dry run back while the page asks it to, and asks it once released", () => {
    harness.autofix.mockReturnValue(new Promise(() => undefined));
    const screen = draw({ ...plan(5, true, 1), status: "reading" } as ReviewedIntakeView);
    screen.actions.holdWarmUp!(true);
    draw(plan(5, true, 1));
    expect(harness.autofix).not.toHaveBeenCalled();
    screen.actions.holdWarmUp!(false);
    draw(plan(5, true, 1));
    expect(harness.autofix).toHaveBeenCalledOnce();
  });
});

// `[2026-10-25 사용자 결정 — 뒤 일정까지 함께 미루기]` 늦추기는 `push` 로 묻고, 서버가 뒤 일정까지 늦춘 판 · 못 늦춘 이유를 그대로 받는다 — 고르면 그 `edits` 를 그대로 저장한다
describe("`[2026-10-25 사용자 결정 — D1~D6]` the later start of a late arrival, pushing the stops after it", () => {
  const change = (id: string, from: string, to: string, pushed?: boolean) => ({ id, source_id: "source-a", index: Number(id.slice(2)), title: id === "0-0" ? "경복궁" : "광장시장",
    from: { place: null, starts_at: from, ends_at: null }, to: { place: null, starts_at: to, ends_at: null }, reason: "time" as const, ...(pushed ? { pushed } : {}) });
  const edits = [{ source_id: "source-a", field: "items[0].starts_at", value: "12:30" }, { source_id: "source-a", field: "items[1].starts_at", value: "14:30" }];

  it("asks with push, and takes the server's pushed plan with its edits", async () => {
    const screen = draw(plan(3, true));
    harness.autofix.mockResolvedValueOnce({ applied: false, revision: 3, kept: [], view: plan(4), edits,
      changed: [change("0-0", "12:00", "12:30"), change("0-1", "14:00", "14:30", true)] });
    expect(harness.autofix).not.toHaveBeenCalled();                                         // 확인할 것이 없는 판 — 「전체 자동 추천」 미리 보기는 묻지 않는다
    const later = await screen.actions.laterStart!("0-0");
    expect(harness.autofix).toHaveBeenLastCalledWith("deferred-intake", 3, "ko", true, "0-0", true);
    expect(later).toEqual({ start: "12:30", end: "", push: { edits, stops: [
      { id: "0-0", title: "경복궁", from: "12:00", start: "12:30", end: "" }, { id: "0-1", title: "광장시장", from: "14:00", start: "14:30", end: "" }] } });
  });

  it("takes a push the server refused with its sentence", async () => {
    const screen = draw(plan(3, true));
    harness.autofix.mockResolvedValueOnce({ applied: false, revision: 3, changed: [], view: plan(3),
      kept: [{ id: "0-0", title: "경복궁", reason: "push_refused", starts_at: "12:30", ends_at: "14:00", message: "뒤 일정을 미루면 하루를 넘어서 저장하지 않았어요." }] });
    expect(await screen.actions.laterStart!("0-0")).toEqual({ start: "12:30", end: "14:00", refused: "뒤 일정을 미루면 하루를 넘어서 저장하지 않았어요." });
  });

  it("saves the pushed plan's edits as they are, checked and keeping their times", async () => {
    harness.autofix.mockReturnValue(new Promise(() => undefined));
    harness.edit.mockResolvedValue(plan(4, true));
    const screen = draw(plan(3, true));
    await screen.actions.applyPush!(edits, { flow: true });
    expect(harness.edit).toHaveBeenLastCalledWith("deferred-intake", 3, edits, "ko", { keepTimes: true });
  });
});
