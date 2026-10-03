import { describe, expect, it, vi } from "vitest";
import { LiveError } from "./client";
import type { IntakeView } from "./intake";
import { planFromIntake, READ_LIMIT_MS, READ_POLL_MS, type PlanDeps, type PlanHooks } from "./intake-plan";
import type { PlanRequest } from "./intake-start";

const ask: PlanRequest = { start_date: "2026-10-05", days: 3, party_size: 2, wish: "조용한 곳" };
const view = (status: IntakeView["status"], revision = 1, extra: Partial<IntakeView> = {}): IntakeView =>
  ({ intake_id: "i1", status, stage: status, stage_label: status === "reading" ? "일정 읽는 중" : "확인해 주세요", revision, fatal: null, trip_id: null, sources: [], check: null, needs_review: [], ...extra });

function setup(views: IntakeView[], over: Partial<PlanDeps> = {}, cancelledAfter = Infinity) {
  const calls: string[] = [];
  let reads = 0;
  let clock = 0;
  const deps: PlanDeps = {
    getIntake: vi.fn(async () => { calls.push("get"); return views[Math.min(reads++, views.length - 1)]; }),
    planIntake: vi.fn(async () => { calls.push("plan"); return { status: "confirmed" as const, trip: { trip_id: "t-1" } }; }),
    sleep: vi.fn(async (ms: number) => { calls.push("sleep"); clock += ms; }),
    now: () => clock,
    ...over,
  };
  let asked = 0;
  const hooks: PlanHooks = {
    phase: vi.fn(), progress: vi.fn(),
    cancelled: () => { asked += 1; return asked > cancelledAfter; },
  };
  return { deps, hooks, calls };
}

describe("planFromIntake — wait until the server has read the text, then ask it to plan", () => {
  it("an intake that is already read: plans at once with that revision, keeping nothing the server read", async () => {
    const { deps, hooks, calls } = setup([view("review", 4)]);
    await expect(planFromIntake("i1", ask, "ko", hooks, deps)).resolves.toBe("t-1");
    expect(calls).toEqual(["get", "plan"]);
    expect(deps.planIntake).toHaveBeenCalledWith("i1", 4, { start_date: "2026-10-05", days: 3, party_size: 2, keep_read_items: false }, "ko", hooks.progress);
    expect(hooks.phase).toHaveBeenLastCalledWith("planning");
  });

  it("while the server still reads, asks again after a pause and plans for the revision it ends on", async () => {
    const { deps, hooks, calls } = setup([view("reading", 1), view("reading", 1), view("review", 3)]);
    await expect(planFromIntake("i1", ask, "ko", hooks, deps)).resolves.toBe("t-1");
    expect(calls).toEqual(["get", "sleep", "get", "sleep", "get", "plan"]);
    expect(deps.sleep).toHaveBeenCalledWith(READ_POLL_MS);
    expect(deps.planIntake).toHaveBeenCalledWith("i1", 3, expect.anything(), "ko", hooks.progress);
    expect(hooks.phase).toHaveBeenCalledWith("reading", "일정 읽는 중");
  });

  it("carries the onboarding survey when there is one", async () => {
    const survey = { version: "2026-09-24.v1", pace: "relaxed" } as PlanRequest["survey"];
    const { deps, hooks } = setup([view("review")]);
    await planFromIntake("i1", { ...ask, survey }, "ko", hooks, deps);
    expect(deps.planIntake).toHaveBeenCalledWith("i1", 1, { start_date: "2026-10-05", days: 3, party_size: 2, keep_read_items: false, survey }, "ko", hooks.progress);
  });

  it("the customer leaves while it waits: no plan is requested and it ends quietly", async () => {
    const { deps, hooks, calls } = setup([view("reading"), view("review")], {}, 0);
    await expect(planFromIntake("i1", ask, "ko", hooks, deps)).resolves.toBeNull();
    expect(calls).not.toContain("plan");
  });

  it("a read that failed is the server's sentence", async () => {
    const { deps, hooks } = setup([view("fatal", 1, { fatal: { code: "unreadable", detail: "글자를 찾지 못했어요" } })]);
    await expect(planFromIntake("i1", ask, "ko", hooks, deps)).rejects.toMatchObject({ code: "unreadable", message: "글자를 찾지 못했어요" });
    expect(deps.planIntake).not.toHaveBeenCalled();
  });

  it("a read that never ends is given up on, with a sentence", async () => {
    const { deps, hooks } = setup([view("reading")]);
    const failure = await planFromIntake("i1", ask, "ko", hooks, deps).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(LiveError);
    expect(failure).toMatchObject({ code: "read_timeout" });
    expect((deps.sleep as ReturnType<typeof vi.fn>).mock.calls.length * READ_POLL_MS).toBeGreaterThanOrEqual(READ_LIMIT_MS);
    expect(deps.planIntake).not.toHaveBeenCalled();
  });

  it("the server's refusal of the plan reaches the caller untouched", async () => {
    const refusal = new LiveError("plan_refused", "이 조건으로는 짤 수 없어요", { relax: ["days"] });
    const { deps, hooks } = setup([view("review")], { planIntake: vi.fn(async () => { throw refusal; }) });
    await expect(planFromIntake("i1", ask, "ko", hooks, deps)).rejects.toBe(refusal);
  });
});
