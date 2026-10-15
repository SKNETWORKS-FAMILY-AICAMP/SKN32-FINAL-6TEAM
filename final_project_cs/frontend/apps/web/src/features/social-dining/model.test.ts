import { describe, expect, it, vi } from "vitest";
import { SocialDiningController, diningMeals, linkEntries, safeSourceUrl } from "./model";
import type { DiningLinksView, DiningPreview, SocialDiningApi } from "@/lib/live/social-dining";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import type { PlanItem } from "@/features/plan-check/model";

const links: DiningLinksView = { revision: 3, links: [{ key: "yt:one", platform: "youtube", source_urls: ["https://youtu.be/one"], status: "identified", reason: null,
  restaurants: [{ name: "성수 국수", area: "성수", branch: null, menu: [], evidence: [{ source: "metadata", quote: "성수 국수" }] }], priority: "must", checked_at: "2026-10-15T01:00:00Z" }] };
const proposal: DiningPreview = { ...links, proposal_id: "p1", changes: [{ key: "yt:one", item_id: "0-1", from: { name: "원래 식당" }, to: { name: "성수 국수", ref: "kakao:1" }, reason: "fits" }], unplaced: [] };
const next = { intake_id: "i1", revision: 4 } as ReviewedIntakeView;
function setup(patch: Partial<SocialDiningApi> = {}) {
  let applied: ReviewedIntakeView | null = null;
  let refreshes = 0;
  const api: SocialDiningApi = { list: async () => links, resolve: async () => links, update: async () => links, preview: async () => proposal, apply: async () => next, ...patch };
  const controller = new SocialDiningController("i1", 3, "ko", { applied: (view) => { applied = view; }, refresh: () => { refreshes++; } }, api);
  return { controller, applied: () => applied, refreshes: () => refreshes };
}

describe("restaurant links shared by the plan check and trip edit", () => {
  it("offers only remaining unbooked unlocked meals as explicit targets", () => {
    const item = (patch: Partial<PlanItem>): PlanItem => ({ id: "meal", date: "2026-10-20", startsAt: "12:00", title: "점심", kind: "dining", locked: false, past: false, booked: false, ...patch }) as PlanItem;
    expect(diningMeals([item({}), item({ id: "booked", booked: true }), item({ id: "locked", locked: true }), item({ id: "past", past: true }), item({ id: "walk", kind: "activity" })])).toEqual([{ id: "meal", label: "2026-10-20 · 12:00 · 점심" }]);
  });
  it("keeps each pasted URL and its note without treating pasted prose as a URL", () => {
    expect(linkEntries(" https://youtu.be/one\n\nhttps://www.instagram.com/p/two/ ", " 창가 자리 ")).toEqual([
      { url: "https://youtu.be/one", note: "창가 자리", priority: "if_fits" }, { url: "https://www.instagram.com/p/two/", note: "창가 자리", priority: "if_fits" },
    ]);
    expect(() => linkEntries("성수 국수")).toThrow();
  });
  it("does not turn a link's source text into executable navigation", () => {
    expect(safeSourceUrl("javascript:alert(1)")).toBeNull();
    expect(safeSourceUrl("https://youtu.be/one")).toBe("https://youtu.be/one");
  });
  it("saving links and previewing never change the parent's itinerary", async () => {
    const { controller, applied } = setup();
    await controller.resolve(linkEntries("https://youtu.be/one"));
    expect(controller.snapshot().links).toEqual(links.links);
    expect(applied()).toBeNull();
    await controller.preview();
    expect(controller.snapshot().proposal?.changes[0].to.name).toBe("성수 국수");
    expect(applied()).toBeNull();
  });
  it("applies only after the customer explicitly accepts a preview", async () => {
    const { controller, applied } = setup();
    expect(await controller.apply()).toBe(false);
    expect(applied()).toBeNull();
    await controller.preview("0-1");
    expect(await controller.apply()).toBe(true);
    expect(applied()).toEqual(next);
    expect(controller.snapshot().proposal).toBeNull();
  });
  it("keeps unplaced must-go restaurants visible instead of claiming everything fit", async () => {
    const unplaced = [{ key: "yt:one", name: "성수 국수", priority: "must" as const, reason: "does_not_fit", message: "식사 시간 안에 도착할 수 없어요." }];
    const { controller } = setup({ preview: async () => ({ ...proposal, changes: [], unplaced }) });
    await controller.preview();
    expect(controller.snapshot().proposal?.unplaced).toEqual(unplaced);
    expect(await controller.apply()).toBe(false);
  });
  it("invalidates the proposal when the itinerary revision changes", async () => {
    const apply = vi.fn(async () => next);
    const { controller } = setup({ apply });
    await controller.preview();
    controller.setRevision(4);
    expect(controller.snapshot().proposal).toBeNull();
    expect(await controller.apply()).toBe(false);
    expect(apply).not.toHaveBeenCalled();
  });
  it("a branch or restaurant selection invalidates the previous proposal", async () => {
    const { controller } = setup();
    await controller.preview();
    await controller.update("yt:one", { restaurant_index: 0, selected_ref: "kakao:1", priority: "must" });
    expect(controller.snapshot().proposal).toBeNull();
    expect(controller.snapshot().links).toEqual(links.links);
  });
  it("preserves saved candidates and reports a failed supplement", async () => {
    const { controller } = setup({ update: async () => { throw new Error("연결이 끊겼어요"); } });
    await controller.load();
    expect(await controller.update("yt:one", { name: "성수 국수", area: "성수" })).toBe(false);
    expect(controller.snapshot().links).toEqual(links.links);
    expect(controller.snapshot().error).toBe("연결이 끊겼어요");
  });
  it("a stale apply asks the parent to refresh and preserves candidates", async () => {
    const { controller, applied, refreshes } = setup({ apply: async () => { throw Object.assign(new Error("일정이 바뀌었어요"), { code: "stale_revision" }); } });
    await controller.preview();
    expect(await controller.apply()).toBe(false);
    expect(applied()).toBeNull();
    expect(controller.snapshot().links).toEqual(links.links);
    expect(controller.snapshot().proposal).toBeNull();
    expect(refreshes()).toBe(1);
  });
  it("ignores a preview response for an itinerary changed while it was loading", async () => {
    let finish!: (value: DiningPreview) => void;
    const { controller } = setup({ preview: () => new Promise((resolve) => { finish = resolve; }) });
    const pending = controller.preview();
    controller.setRevision(4);
    finish(proposal);
    expect(await pending).toBe(false);
    expect(controller.snapshot().proposal).toBeNull();
    expect(controller.snapshot().error).toContain("일정이 바뀌");
  });
  it("choosing another target meal discards the old proposal before it can be applied", async () => {
    const { controller, applied } = setup();
    await controller.preview("0-1");
    controller.clearProposal();
    expect(await controller.apply()).toBe(false);
    expect(applied()).toBeNull();
  });
});
