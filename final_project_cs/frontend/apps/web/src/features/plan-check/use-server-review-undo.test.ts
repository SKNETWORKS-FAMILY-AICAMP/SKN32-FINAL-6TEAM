import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { LiveError } from "@/lib/live/client";
import { useServerReview } from "./use-server-review";

const harness = vi.hoisted(() => ({
  slots: [] as { value?: unknown; deps?: readonly unknown[]; cleanup?: () => void }[], cursor: 0,
  effects: [] as (() => void)[], edit: vi.fn(), restore: vi.fn(),
}));
vi.mock("@/lib/live/intake", () => ({ editIntake: harness.edit, restoreIntake: harness.restore }));
vi.mock("react", () => ({
  useState: (value: unknown) => {
    const at = harness.cursor++;
    const slot = harness.slots[at] ??= { value };
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

function plan(id = "intake-a", revision = 1, removed = false): ReviewedIntakeView {
  return { intake_id: id, revision, status: "review", sources: [{ source_id: "source-a", trip: {}, items: [
    { index: 0, fields: { title: { value: "경복궁" }, ...(removed && { removed: { value: true } }) } },
  ] }], review: { revision, items: removed ? [] : [{ id: "0-0", source_id: "source-a", index: 0 }], needs: { total: 0 } } } as ReviewedIntakeView;
}

function draw(view: ReviewedIntakeView | undefined, apply = vi.fn(), reread = vi.fn(), intakeId = view!.intake_id) {
  harness.cursor = 0;
  harness.effects = [];
  // eslint-disable-next-line react-hooks/rules-of-hooks -- Node harness runs the real hook's action boundaries with mocked React storage.
  const result = useServerReview({ view, intakeId, apply, reread, language: "ko" });
  for (const run of harness.effects) run();
  return result;
}

afterEach(() => {
  for (const slot of harness.slots) slot.cleanup?.();
  harness.slots = []; harness.cursor = 0; harness.effects = [];
  harness.edit.mockReset(); harness.restore.mockReset();
});

describe("server review atomic whole undo", () => {
  it("unlocks every locked stop in one revision without changing times or undo availability", async () => {
    const original = plan(), apply = vi.fn();
    original.review!.items = [
      { ...original.review!.items[0], locked: true },
      { ...original.review!.items[0], id: "1-2", source_id: "source-b", index: 2, locked: true },
      { ...original.review!.items[0], id: "0-3", index: 3, locked: false },
    ];
    const next = { ...original, revision: 2, review: { ...original.review!, items: original.review!.items.map((item) => ({ ...item, locked: false })) } };
    harness.edit.mockResolvedValueOnce(next);
    let screen = draw(original, apply);
    expect(await screen.actions.unlockAll!()).toBe(2);
    expect(harness.edit).toHaveBeenCalledExactlyOnceWith("intake-a", 1, [
      { source_id: "source-a", field: "items[0].locked", value: false },
      { source_id: "source-b", field: "items[2].locked", value: false },
    ], "ko");
    screen = draw(next, apply);
    expect(screen.dirty).toBe(false);
    expect(screen.actions.canUndoAll!()).toBe(false);
  });

  it("keeps the current plan on a refused whole unlock and refreshes a stale revision", async () => {
    const original = plan(), apply = vi.fn(), reread = vi.fn();
    original.review!.items[0].locked = true;
    harness.edit.mockRejectedValueOnce(new LiveError("stale_revision", "새로 읽어 주세요"));
    const screen = draw(original, apply, reread);
    await expect(screen.actions.unlockAll!()).rejects.toMatchObject({ code: "stale_revision" });
    expect(apply).not.toHaveBeenCalled();expect(reread).toHaveBeenCalledOnce();
    expect(original.review!.items[0].locked).toBe(true);
  });

  it("does not send an edit when no stop is locked", async () => {
    const screen = draw(plan());
    expect(await screen.actions.unlockAll!()).toBe(0);
    expect(harness.edit).not.toHaveBeenCalled();
  });

  it("sends one historical restore and clears availability only after success", async () => {
    const apply = vi.fn(), original = plan(), changed = plan("intake-a", 2, true);
    let screen = draw(original, apply);
    harness.edit.mockResolvedValue(changed);
    await screen.actions.remove!("0-0");
    screen = draw(changed, apply);
    expect(screen.dirty).toBe(true);
    expect(screen.actions.canUndoAll!()).toBe(true);
    harness.restore.mockResolvedValue(plan("intake-a", 3));
    await screen.actions.undoAll!();
    expect(harness.restore).toHaveBeenCalledExactlyOnceWith("intake-a", 2, 1, "ko");
    expect(screen.actions.canUndoAll!()).toBe(false);
    expect(screen.actions.canUndo!()).toBe(false);
    expect(harness.edit).toHaveBeenCalledTimes(1);
    expect(draw(plan("intake-a", 3), apply).dirty).toBe(false);
  });

  it.each(["stale_revision", "item_locked", "item_booked"])("keeps all originals and current values after %s", async (code) => {
    const apply = vi.fn(), reread = vi.fn(), changed = plan("intake-a", 2, true);
    let screen = draw(plan(), apply, reread);
    harness.edit.mockResolvedValue(changed);
    await screen.actions.remove!("0-0");
    screen = draw(changed, apply, reread);
    expect(screen.dirty).toBe(true);
    apply.mockClear();
    harness.restore.mockRejectedValueOnce(new LiveError(code, "변경은 보존됨"));
    await expect(screen.actions.undoAll!()).rejects.toMatchObject({ code });
    expect(apply).not.toHaveBeenCalled();
    expect(screen.actions.canUndoAll!()).toBe(true);
    expect(draw(changed, apply, reread).dirty).toBe(true);
    expect(reread).toHaveBeenCalledTimes(code === "stale_revision" ? 1 : 0);
    harness.restore.mockResolvedValueOnce(plan("intake-a", 3));
    await screen.actions.undoAll!();
    expect(harness.restore).toHaveBeenLastCalledWith("intake-a", 2, 1, "ko");
  });

  it("does not capture a failed first edit and preserves the last-change undo", async () => {
    const original = plan(), apply = vi.fn();
    const screen = draw(original, apply);
    harness.edit.mockRejectedValueOnce(new LiveError("item_locked", "보호됨"));
    await expect(screen.actions.remove!("0-0")).rejects.toMatchObject({ code: "item_locked" });
    expect(screen.actions.canUndoAll!()).toBe(false);
    harness.edit.mockResolvedValueOnce(plan("intake-a", 2, true));
    await screen.actions.remove!("0-0");
    harness.edit.mockResolvedValueOnce(plan("intake-a", 3));
    await screen.actions.undo!();
    expect(harness.edit).toHaveBeenLastCalledWith("intake-a", 2, [{ source_id: "source-a", field: "items[0].removed", value: false }], "ko");
    expect(screen.actions.canUndoAll!()).toBe(false);
  });

  it("drops an old intake's delayed restore and resets dirty/undo for the new intake", async () => {
    const apply = vi.fn();
    const first = draw(plan(), apply);
    harness.edit.mockResolvedValueOnce(plan("intake-a", 2, true));
    await first.actions.remove!("0-0");
    let resolve: (next: ReviewedIntakeView) => void = () => undefined;
    harness.restore.mockImplementationOnce(() => new Promise<ReviewedIntakeView>((done) => { resolve = done; }));
    const pending = first.actions.undoAll!();
    const second = draw(plan("intake-b"), apply);
    apply.mockClear();
    resolve(plan("intake-a", 3));
    await pending;
    expect(apply).not.toHaveBeenCalled();
    expect(second.dirty).toBe(false);
    expect(second.actions.canUndoAll!()).toBe(false);
    expect(second.actions.canUndo!()).toBe(false);
  });
});
