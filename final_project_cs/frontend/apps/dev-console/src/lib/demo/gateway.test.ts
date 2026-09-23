import { describe, expect, it } from "vitest";
import { defaultRequest } from "../model";
import type { TestRequest } from "../model";
import { createDemoGateway, DEMO_STORAGE_KEY, type StorageLike } from "./gateway";

function setup() {
  const values = new Map<string, string>();
  let time = Date.parse("2026-09-21T06:00:00.000Z");
  let sequence = 0;
  const storage: StorageLike = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); } };
  const dependencies = { storage: () => storage, now: () => time, id: () => `run-${++sequence}` };
  return { gateway: createDemoGateway(dependencies), reload: () => createDemoGateway(dependencies), storage, values, advance: (milliseconds: number) => { time += milliseconds; } };
}

describe("demo executions", () => {
  it("progresses through four phases and does not expose future observations or results", async () => {
    const { gateway, advance } = setup();
    const start = await gateway.createRun(defaultRequest("activity"));
    expect(start.status).toBe("running");
    expect(start.steps.map((step) => step.status)).toEqual(["running", "pending", "pending", "pending"]);
    expect(start.result).toBeUndefined();
    expect(start.steps.flatMap((step) => step.observations)).toEqual([]);
    expect(start.steps[2].input).toEqual({});
    advance(1000);
    const lookup = await gateway.getRun(start.id);
    expect(lookup.steps[1].status).toBe("running");
    expect(lookup.steps[1].observations).toEqual([]);
    advance(1000);
    const compare = await gateway.getRun(start.id);
    expect(compare.steps[1].observations[0].value).toBe("16:30");
    expect(compare.steps[2].comparisons).toEqual([]);
    expect(compare.result).toBeUndefined();
    advance(2000);
    const completed = await gateway.getRun(start.id);
    expect(completed.status).toBe("completed");
    expect(completed.steps.every((step) => step.status === "completed")).toBe(true);
    expect(completed.result?.actual).toBe("마감 조건 초과");
    expect(completed.result?.matched).toBe(true);
    expect(completed.completedAt).toBe("2026-09-21T06:00:04.000Z");
  });

  it("runs Dining and Mobility in parallel before Activity consumes the route output", async () => {
    const { gateway, advance } = setup();
    const run = await gateway.createRun(defaultRequest("core"));
    advance(1000);
    const parallel = await gateway.getRun(run.id);
    expect(parallel.steps.filter((step) => step.status === "running").map((step) => step.owner)).toEqual(["dining", "mobility"]);
    expect(parallel.steps[3].input).toEqual({});
    advance(1000);
    const activity = await gateway.getRun(run.id);
    expect(activity.steps[3].input.arrival).toBe("16:45");
    expect(activity.steps[3].input.arrival_source_step).toBe(activity.steps[2].id);
    expect(activity.steps[1].output.reservation_time).toBe("14:30");
    advance(2000);
    const finished = await gateway.getRun(run.id);
    expect(finished.steps[3].owner).toBe("activity");
    expect(finished.steps[3].comparisons[0].value).toContain("15분 초과");
    expect(finished.steps[4].owner).toBe("core");
    expect(finished.steps[4].comparisons.map((row) => row.label)).toEqual(["결과 연결", "근거 참조"]);
  });

  it("persists request snapshots and resumes elapsed progress after gateway recreation", async () => {
    const { gateway, reload, advance } = setup();
    const request = defaultRequest("activity");
    const run = await gateway.createRun(request);
    request.input.time = "08:00";
    expect(Object.isFrozen(run.request)).toBe(true);
    expect(Object.isFrozen(run.request.input)).toBe(true);
    run.steps[0].input.arrival = "09:00";
    advance(4000);
    const restored = await reload().getRun(run.id);
    expect(restored.request.input.time).toBe("16:45");
    expect(restored.steps[0].input.arrival).toBe("16:45");
    expect(restored.status).toBe("completed");
  });

  it("separates successful execution from an incorrect A-version business result", async () => {
    const { gateway, advance } = setup();
    const run = await gateway.createRun({ ...defaultRequest("activity"), version: "A" });
    advance(4000);
    const result = await gateway.getRun(run.id);
    expect(result.status).toBe("completed");
    expect(result.result).toMatchObject({ actual: "마감 조건 충족", expected: "마감 조건 초과", matched: false });
  });

  it("uses requested visit duration and marks closing-time conflicts in both versions", async () => {
    const { gateway, advance } = setup();
    const request = defaultRequest("activity");
    request.version = "A";
    request.input.durationMinutes = 120;
    const run = await gateway.createRun(request);
    advance(4000);
    const result = await gateway.getRun(run.id);
    expect(result.result).toMatchObject({ actual: "마감 조건 초과", matched: true });
    expect(result.result?.output.visit_end).toBe("18:45");
  });

  it("preserves uncertain reservation exceptions and the original dining reservation", async () => {
    const { gateway, advance } = setup();
    const run = await gateway.createRun(defaultRequest("dining"));
    advance(4000);
    expect((await gateway.getRun(run.id)).result?.output).toMatchObject({ reservation_time: "14:30", reservation_preserved: true, reservation_exception: null, overlap_minutes: 30, status: "needs_confirmation" });
  });

  it("uses Core's duration for both the fixed meal reservation and the later visit", async () => {
    const { gateway, advance } = setup();
    const request = defaultRequest("core");
    request.input.durationMinutes = 30;
    const run = await gateway.createRun(request);
    advance(4000);
    const completed = await gateway.getRun(run.id);
    expect(completed.steps[1].input.meal_minutes).toBe(30);
    expect(completed.steps[1].output).toMatchObject({ reservation_time: "14:30", overlap_minutes: 0, status: "no_overlap" });
    expect(completed.steps[3].input.visit_minutes).toBe(30);
    expect(completed.steps[3].output).toMatchObject({ arrival: "16:45", visit_end: "17:15" });
  });

  it("selects the preferred transport rather than the fastest option", async () => {
    const { gateway, advance } = setup();
    const request = defaultRequest("mobility");
    request.input.transport = "walk";
    const run = await gateway.createRun(request);
    advance(4000);
    expect((await gateway.getRun(run.id)).result?.output).toMatchObject({ mode: "walk", duration_minutes: 55, arrival: "17:00" });
  });

  it("keeps next-day times distinct and does not interpret them as an earlier arrival", async () => {
    const { gateway, advance } = setup();
    const request = defaultRequest("core");
    request.input.time = "23:50";
    const run = await gateway.createRun(request);
    advance(4000);
    const completed = await gateway.getRun(run.id);
    expect(completed.steps[3].input.arrival).toBe("다음 날 00:30");
    expect(completed.result?.actual).toContain("마감 조건 초과");
  });

  it("leaves no fake output after an explicit tool failure and creates a linked retry", async () => {
    const { gateway, advance } = setup();
    const request: TestRequest = { ...defaultRequest("activity"), fixtureMode: "tool-error" };
    const run = await gateway.createRun(request);
    await expect(gateway.createRun(request, run.id)).rejects.toThrow("진행 중");
    advance(2000);
    const failed = await gateway.getRun(run.id);
    expect(failed.status).toBe("failed");
    expect(failed.result).toBeUndefined();
    expect(failed.steps.map((step) => step.status)).toEqual(["completed", "failed", "pending", "pending"]);
    expect(failed.steps[1].output).toEqual({});
    expect(failed.steps[1].error).toContain("샘플 도구 응답 실패");
    const retry = await gateway.createRun(request, run.id);
    expect(retry.id).not.toBe(run.id);
    expect(retry.retryOf).toBe(run.id);
    expect(retry.status).toBe("running");
    expect((await gateway.getRun(run.id)).status).toBe("failed");
  });

  it("does not run dependent Core tasks after Mobility fails", async () => {
    const { gateway, advance } = setup();
    const run = await gateway.createRun({ ...defaultRequest("core"), fixtureMode: "tool-error" });
    advance(9000);
    const failed = await gateway.getRun(run.id);
    expect(failed.steps.map((step) => step.status)).toEqual(["completed", "completed", "failed", "pending", "pending"]);
    expect(failed.result).toBeUndefined();
    expect(failed.completedAt).toBe("2026-09-21T06:00:02.000Z");
  });
});

describe("cases and comparisons", () => {
  it("offers three built-in cases and returns independent snapshots", async () => {
    const { gateway } = setup();
    const cases = await gateway.listCases();
    expect(cases.map((testCase) => testCase.request.target)).toEqual(["activity", "dining", "mobility"]);
    cases[0].name = "changed";
    expect((await gateway.getCase("builtin-activity")).name).toBe("입장 마감 후 도착");
  });

  it("saves completed and failed executions with their original requests", async () => {
    const { gateway, advance } = setup();
    const completed = await gateway.createRun(defaultRequest("mobility"));
    const failed = await gateway.createRun({ ...defaultRequest("dining"), fixtureMode: "tool-error" });
    await expect(gateway.saveCase(completed.id, "too soon")).rejects.toThrow("진행 중");
    advance(4000);
    const saved = await gateway.saveCase(completed.id, "  이동 회귀 사례  ");
    expect(saved.name).toBe("이동 회귀 사례");
    expect(saved.builtIn).toBe(false);
    const savedFailure = await gateway.saveCase(failed.id, "도구 실패 사례");
    expect(savedFailure.request.fixtureMode).toBe("tool-error");
    expect(await gateway.listCases()).toHaveLength(5);
    await expect(gateway.saveCase(completed.id, " ")).rejects.toThrow("1~100자");
  });

  it("compares A and B using the same immutable case input and fixture", async () => {
    const { gateway, advance, reload } = setup();
    const comparison = await gateway.createComparison("builtin-activity");
    const a = await gateway.getRun(comparison.runAId);
    const b = await gateway.getRun(comparison.runBId);
    expect(a.request.version).toBe("A");
    expect(b.request.version).toBe("B");
    expect(a.request.input).toEqual(b.request.input);
    expect(a.request.fixtureMode).toBe(b.request.fixtureMode);
    expect(a.createdAt).toBe(b.createdAt);
    expect(a.id).not.toBe(b.id);
    comparison.caseSnapshot.name = "Changed externally";
    advance(4000);
    expect((await reload().getComparison(comparison.id)).caseSnapshot.name).toBe("입장 마감 후 도착");
    expect((await gateway.getRun(a.id)).result?.matched).toBe(false);
    expect((await gateway.getRun(b.id)).result?.matched).toBe(true);
  });

  it("preserves tool-error fixtures in comparisons without fabricating evaluation results", async () => {
    const { gateway, advance } = setup();
    const run = await gateway.createRun({ ...defaultRequest("dining"), fixtureMode: "tool-error" });
    advance(2000);
    const testCase = await gateway.saveCase(run.id, "실패 비교");
    const comparison = await gateway.createComparison(testCase.id);
    advance(4000);
    for (const id of [comparison.runAId, comparison.runBId]) {
      const failure = await gateway.getRun(id);
      expect(failure.status).toBe("failed");
      expect(failure.result).toBeUndefined();
    }
  });
});

describe("validation and persistence failures", () => {
  it.each(["24:00", "16:60", "9:00", "noon"])("rejects invalid input time %s before storing a run", async (time) => {
    const { gateway, values } = setup();
    const request = defaultRequest("activity");
    request.input.time = time;
    await expect(gateway.createRun(request)).rejects.toThrow("테스트 입력");
    expect(values.size).toBe(0);
  });

  it.each([0, 241, 1.5, Number.NaN])("rejects invalid duration %s", async (durationMinutes) => {
    const { gateway } = setup();
    const request = defaultRequest("activity");
    request.input.durationMinutes = durationMinutes;
    await expect(gateway.createRun(request)).rejects.toThrow("테스트 입력");
  });

  it("rejects missing run, case, comparison, and retry IDs", async () => {
    const { gateway } = setup();
    await expect(gateway.getRun("missing")).rejects.toThrow("실행 기록");
    await expect(gateway.getCase("missing")).rejects.toThrow("테스트 사례");
    await expect(gateway.getComparison("missing")).rejects.toThrow("비교 기록");
    await expect(gateway.createRun(defaultRequest("activity"), "missing")).rejects.toThrow("실행 기록");
    await expect(gateway.createComparison("missing")).rejects.toThrow("테스트 사례");
  });

  it.each(["not-json", JSON.stringify({ version: 2, runs: [], cases: [], comparisons: [] }), JSON.stringify({ version: 1, runs: [{ id: "bad" }], cases: [], comparisons: [] })])("does not reset corrupt persisted state", async (raw) => {
    const { gateway, values } = setup();
    values.set(DEMO_STORAGE_KEY, raw);
    await expect(gateway.createRun(defaultRequest("activity"))).rejects.toThrow("데모 데이터 형식");
    expect(values.get(DEMO_STORAGE_KEY)).toBe(raw);
  });

  it("rejects inaccessible storage with a useful action", async () => {
    const gateway = createDemoGateway({ storage: () => { throw new Error("SecurityError"); } });
    await expect(gateway.listCases()).rejects.toThrow("사이트 저장소 허용 설정");
  });

  it("does not claim a run was saved when storage is full", async () => {
    const { gateway, storage, values } = setup();
    storage.setItem = () => { throw new Error("QuotaExceededError"); };
    await expect(gateway.createRun(defaultRequest("activity"))).rejects.toThrow("이번 작업은 저장되지 않았습니다");
    expect(values.size).toBe(0);
  });

  it("writes A/B runs and their comparison atomically", async () => {
    const { gateway, storage, values } = setup();
    storage.setItem = () => { throw new Error("QuotaExceededError"); };
    await expect(gateway.createComparison("builtin-activity")).rejects.toThrow("저장하지 못했습니다");
    expect(values.size).toBe(0);
  });
});
