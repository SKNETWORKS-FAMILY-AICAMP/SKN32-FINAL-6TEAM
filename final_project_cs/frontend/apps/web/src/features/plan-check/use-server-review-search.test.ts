import { afterEach, describe, expect, it, vi } from "vitest";
import type { Candidate, ReviewedIntakeView } from "@/lib/live/intake-review";
import { LiveError } from "@/lib/live/client";
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

function plan(): ReviewedIntakeView {
  return { intake_id: "search-intake", revision: 3, status: "review", sources: [{ source_id: "source-a", trip: {}, items: [] }],
    review: { revision: 3, needs: { total: 0 }, items: [{ id: "0-0", source_id: "source-a", index: 0, kind: "activity",
      title: "전시 공간", date: "2030-01-05", starts_at: "12:00", ends_at: "13:30", place: null }] } } as unknown as ReviewedIntakeView;
}

function restaurant(name = "레몬그라스타이 가점"): Candidate {
  return { rank: 1, place: { name, kind: "dining", source: "kakao", latitude: 37.55, longitude: 127,
    address: "서울 시험구", category: "음식점 > 태국음식", ref: `kakao:${name}`, content_id: null, content_type_id: null },
    rows: [], fits: false, status: "warn", distance_m: null, reference: null,
    slack: { before: null, after: null }, estimated: false };
}

function draw(view = plan(), apply = vi.fn()) {
  harness.cursor = 0; harness.effects = [];
  // eslint-disable-next-line react-hooks/rules-of-hooks -- Real action boundaries use controlled React storage in this Node harness.
  const screen = useServerReview({ intakeId: view.intake_id, view, apply, reread: vi.fn(), language: "ko" });
  for (const run of harness.effects) run();
  return screen;
}

afterEach(() => {
  for (const slot of harness.slots) slot.cleanup?.();
  harness.slots = []; harness.cursor = 0; harness.effects = [];
  harness.search.mockReset(); harness.edit.mockReset();
});

describe("explicit restaurant search actions", () => {
  it("keeps branches unchosen and sends actual dining kind only with the customer's selected place", async () => {
    harness.search.mockResolvedValue({ results: [restaurant(), { ...restaurant("레몬그라스타이 나점"), rank: 2 }], notes: [] });
    const original = plan(), screen = draw(original);
    const cards = await screen.actions.search!("0-0", "레몬그라스");
    expect(cards).toHaveLength(2); expect(cards.every((card) => card.placeKind === "dining")).toBe(true);
    expect(harness.edit).not.toHaveBeenCalled();
    harness.edit.mockResolvedValue({ ...plan(), revision: 4 });
    await screen.actions.replace!("0-0", { candidate: cards[1] });
    expect(harness.edit).toHaveBeenCalledExactlyOnceWith("search-intake", 3, [
      { source_id: "source-a", field: "items[0].place", value: expect.objectContaining({ name: "레몬그라스타이 나점" }) },
      { source_id: "source-a", field: "items[0].kind", value: "dining" },
    ], "ko", { check: false });
    expect(original.review!.items[0]).toMatchObject({ kind: "activity", starts_at: "12:00", ends_at: "13:30" });
  });

  it("keeps existing state when protected-item validation refuses the selected place", async () => {
    harness.search.mockResolvedValue({ results: [restaurant()], notes: [] });
    const original = plan(), apply = vi.fn(), screen = draw(original, apply);
    const [card] = await screen.actions.search!("0-0", "레몬그라스");
    harness.edit.mockRejectedValue(new LiveError("item_locked", "고정된 일정이에요"));
    await expect(screen.actions.replace!("0-0", { candidate: card })).rejects.toMatchObject({ code: "item_locked" });
    expect(apply).not.toHaveBeenCalled(); expect(screen.dirty).toBe(false);
    expect(original.review!.items[0].kind).toBe("activity");
  });

  it("`[2026-10-22]` keeps the nearest list and the best-name-match list apart, even when one place stands in both", async () => {
    const near = { ...restaurant("레몬그라스타이 가점"), order: "distance" as const, distance_m: 300, reference: "경복궁" };
    const exact = { ...restaurant("레몬그라스타이"), rank: 2, order: "distance" as const, distance_m: 6200, reference: "경복궁" };
    harness.search.mockResolvedValue({ results: [near, exact], relevance: [{ ...exact, rank: 1, order: "relevance" }, { ...near, rank: 2, order: "relevance" }],
      center: { name: "경복궁", basis: "selected" }, notes: [] });
    const cards = await draw().actions.search!("0-0", "레몬그라스");
    expect(cards.map((card) => [card.name, card.order])).toEqual([
      ["레몬그라스타이 가점", "distance"], ["레몬그라스타이", "distance"], ["레몬그라스타이", "relevance"], ["레몬그라스타이 가점", "relevance"]]);
    expect(new Set(cards.map((card) => card.id)).size).toBe(4);
    expect(cards[0].distance).toEqual({ km: 0.3, from: "경복궁" });
  });

  it("draws an older server's single list as it was (no order tags)", async () => {
    harness.search.mockResolvedValue({ results: [restaurant()], notes: [] });
    const [card] = await draw().actions.search!("0-0", "레몬그라스");
    expect(card.order).toBeUndefined(); expect(card.id.endsWith(":distance")).toBe(false);
  });

  it.each(["search", "searchToAdd"] as const)("shows a source failure from %s instead of an absent shop", async (action) => {
    harness.search.mockResolvedValue({ results: [], notes: ["kakao:timeout"] });
    const screen = draw();
    await expect(screen.actions[action]!("0-0", "레몬그라스")).rejects.toMatchObject({ code: "place_search_unavailable" });
    expect(harness.edit).not.toHaveBeenCalled();
  });
});
