import { z } from "zod";
import type { Comparison, DevConsoleGateway, Run, RunStep, TestCase, TestRequest } from "../model";
import { defaultRequest } from "../model";
import { testRequestSchema } from "../validation";
import { buildScenario } from "./scenarios";

export const DEMO_STORAGE_KEY = "tripilot-dev-console:v1";
export const DEMO_PHASE_MS = 1000;

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

interface DemoDependencies {
  storage: () => StorageLike;
  now?: () => number;
  id?: () => string;
}

const timestamp = z.iso.datetime();
const storedRunSchema = z.object({
  id: z.string().min(1), request: testRequestSchema, createdAt: timestamp, retryOf: z.string().min(1).optional(),
}).strict();
const caseSchema = z.object({
  id: z.string().min(1), name: z.string().trim().min(1).max(100), request: testRequestSchema,
  createdAt: timestamp, builtIn: z.boolean(),
}).strict();
const comparisonSchema = z.object({
  id: z.string().min(1), caseSnapshot: caseSchema, runAId: z.string().min(1), runBId: z.string().min(1), createdAt: timestamp,
}).strict();
const storeSchema = z.object({
  version: z.literal(1), runs: z.array(storedRunSchema), cases: z.array(caseSchema), comparisons: z.array(comparisonSchema),
}).strict().superRefine((value, context) => {
  const unique = (items: { id: string }[]) => new Set(items.map((item) => item.id)).size === items.length;
  const runIds = new Set(value.runs.map((run) => run.id));
  if (!unique(value.runs) || !unique(value.cases) || !unique(value.comparisons) ||
    value.runs.some((run) => run.retryOf && !runIds.has(run.retryOf)) ||
    value.comparisons.some((comparison) => !runIds.has(comparison.runAId) || !runIds.has(comparison.runBId))) {
    context.addIssue({ code: "custom", message: "저장된 실행 참조가 올바르지 않습니다." });
  }
});
type Store = z.infer<typeof storeSchema>;
type StoredRun = z.infer<typeof storedRunSchema>;

const builtInCases: TestCase[] = [
  { id: "builtin-activity", name: "입장 마감 후 도착", request: defaultRequest("activity"), createdAt: "2026-09-21T00:00:00.000Z", builtIn: true },
  { id: "builtin-dining", name: "식사와 휴게시간 겹침", request: defaultRequest("dining"), createdAt: "2026-09-21T00:00:00.000Z", builtIn: true },
  { id: "builtin-mobility", name: "선호 이동수단 유지", request: defaultRequest("mobility"), createdAt: "2026-09-21T00:00:00.000Z", builtIn: true },
];

function projectRun(seed: StoredRun, now: number): Run {
  const created = Date.parse(seed.createdAt);
  const elapsed = Math.max(0, now - created);
  const failed = seed.request.fixtureMode === "tool-error" && elapsed >= DEMO_PHASE_MS * 2;
  const completed = !failed && elapsed >= DEMO_PHASE_MS * 4;
  const phase = Math.floor(elapsed / DEMO_PHASE_MS);
  const scenario = buildScenario(seed.id, seed.request);
  const error = "샘플 도구 응답 실패를 재현했습니다. 입력과 오류를 확인한 뒤 새 실행으로 다시 테스트해 주세요.";
  const steps: RunStep[] = scenario.steps.map((full) => {
    const status = failed
      ? full.id === scenario.failureStepId ? "failed" : full.phase < 2 ? "completed" : "pending"
      : full.phase < phase ? "completed" : full.phase === phase ? "running" : "pending";
    if (status === "completed") return { ...full, status };
    return { ...full, status, input: status === "pending" ? {} : full.input,
      observations: [], comparisons: [], output: {}, evidenceRefs: [],
      summary: status === "pending" ? "아직 시작하지 않은 단계입니다." : status === "failed" ? error : "샘플 실행 단계를 처리하고 있습니다.",
      ...(status === "failed" ? { error } : {}),
    };
  });
  const finishedAt = created + DEMO_PHASE_MS * (failed ? 2 : 4);
  return {
    id: seed.id, source: "demo", request: testRequestSchema.parse(seed.request), createdAt: seed.createdAt,
    updatedAt: new Date(Math.max(created, Math.min(now, finishedAt))).toISOString(),
    status: failed ? "failed" : completed ? "completed" : "running", steps,
    ...(seed.retryOf ? { retryOf: seed.retryOf } : {}),
    ...(failed || completed ? { completedAt: new Date(finishedAt).toISOString() } : {}),
    ...(failed ? { error } : completed ? { result: scenario.result } : {}),
  };
}

export function createDemoGateway(dependencies: DemoDependencies): DevConsoleGateway {
  const now = dependencies.now ?? Date.now;
  const makeId = dependencies.id ?? (() => crypto.randomUUID());
  const storage = () => {
    try { return dependencies.storage(); }
    catch { throw new Error("브라우저 세션 저장소에 접근할 수 없습니다. 사이트 저장소 허용 설정을 확인해 주세요."); }
  };
  function read(): Store {
    let raw: string | null;
    try { raw = storage().getItem(DEMO_STORAGE_KEY); }
    catch { throw new Error("브라우저 세션 저장소를 읽을 수 없습니다. 사이트 저장소 허용 설정을 확인해 주세요."); }
    if (raw === null) return { version: 1, runs: [], cases: [], comparisons: [] };
    try { return storeSchema.parse(JSON.parse(raw)); }
    catch { throw new Error(`저장된 데모 데이터 형식이 올바르지 않습니다. 브라우저 개발자 도구에서 필요한 세션 저장소 값을 복사한 뒤 ${DEMO_STORAGE_KEY} 항목을 삭제하고 새로고침해 주세요.`); }
  }
  function write(value: Store) {
    const serialized = JSON.stringify(storeSchema.parse(value));
    try { storage().setItem(DEMO_STORAGE_KEY, serialized); }
    catch { throw new Error("데모 기록을 저장하지 못했습니다. 브라우저 저장 공간과 사이트 저장소 허용 설정을 확인해 주세요. 이번 작업은 저장되지 않았습니다."); }
  }
  function findRun(value: Store, id: string): StoredRun {
    const found = value.runs.find((run) => run.id === id);
    if (!found) throw new Error("실행 기록을 찾을 수 없습니다. 실행한 브라우저 탭에서 확인하거나 새 테스트를 실행해 주세요.");
    return found;
  }
  function findCase(value: Store, id: string): TestCase {
    const found = [...value.cases, ...builtInCases].find((testCase) => testCase.id === id);
    if (!found) throw new Error("테스트 사례를 찾을 수 없습니다. 사례 목록에서 다시 선택해 주세요.");
    return caseSchema.parse(found);
  }
  function newSeed(request: TestRequest, time: number, retryOf?: string): StoredRun {
    return storedRunSchema.parse({ id: makeId(), request, createdAt: new Date(time).toISOString(), ...(retryOf ? { retryOf } : {}) });
  }
  return {
    async createRun(request, retryOf) {
      const parsed = testRequestSchema.safeParse(request);
      if (!parsed.success) throw new Error(`테스트 입력을 확인해 주세요. ${parsed.error.issues.map((issue) => issue.message).join(" ")}`);
      const value = read();
      if (retryOf && projectRun(findRun(value, retryOf), now()).status === "running") throw new Error("진행 중인 실행은 재실행할 수 없습니다. 완료 또는 실패 후 다시 실행해 주세요.");
      const time = now();
      const run = newSeed(parsed.data, time, retryOf);
      value.runs.push(run);
      write(value);
      return projectRun(run, time);
    },
    async getRun(id) { return projectRun(findRun(read(), id), now()); },
    async listCases() { return [...read().cases, ...builtInCases].map((testCase) => caseSchema.parse(testCase)); },
    async getCase(id) { return findCase(read(), id); },
    async saveCase(runId, name) {
      const value = read();
      const run = findRun(value, runId);
      if (projectRun(run, now()).status === "running") throw new Error("진행 중인 실행은 저장할 수 없습니다. 완료 또는 실패 후 저장해 주세요.");
      const parsed = caseSchema.safeParse({ id: makeId(), name, request: run.request, createdAt: new Date(now()).toISOString(), builtIn: false });
      if (!parsed.success) throw new Error("사례 이름을 1~100자로 입력해 주세요.");
      value.cases.unshift(parsed.data);
      write(value);
      return caseSchema.parse(parsed.data);
    },
    async createComparison(caseId) {
      const value = read();
      const caseSnapshot = findCase(value, caseId);
      const time = now();
      const a = newSeed({ ...caseSnapshot.request, version: "A" }, time);
      const b = newSeed({ ...caseSnapshot.request, version: "B" }, time);
      const comparison = comparisonSchema.parse({ id: makeId(), caseSnapshot, runAId: a.id, runBId: b.id, createdAt: new Date(time).toISOString() });
      value.runs.push(a, b);
      value.comparisons.push(comparison);
      write(value);
      return comparison;
    },
    async getComparison(id): Promise<Comparison> {
      const found = read().comparisons.find((comparison) => comparison.id === id);
      if (!found) throw new Error("비교 기록을 찾을 수 없습니다. 테스트 사례에서 새 비교를 실행해 주세요.");
      return comparisonSchema.parse(found);
    },
  };
}
