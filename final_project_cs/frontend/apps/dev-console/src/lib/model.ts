export type TeamId = "activity" | "dining" | "mobility";
export type TestTarget = TeamId | "core";
export type SampleVersion = "A" | "B";
export type Transport = "bus" | "walk" | "taxi";
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export interface TestInput {
  time: string;
  durationMinutes: number;
  transport: Transport;
}

export interface TestRequest {
  target: TestTarget;
  version: SampleVersion;
  fixtureMode: "normal" | "tool-error";
  input: TestInput;
}

export interface FactRow {
  label: string;
  value: string;
  reference?: string;
}

export interface RunStep {
  id: string;
  label: string;
  owner: TestTarget;
  phase: number;
  status: "pending" | "running" | "completed" | "failed";
  input: JsonObject;
  observations: FactRow[];
  comparisons: FactRow[];
  output: JsonObject;
  evidenceRefs: string[];
  summary: string;
  error?: string;
}

export interface RunResult {
  actual: string;
  expected: string;
  matched: boolean;
  summary: string;
  output: JsonObject;
}

export interface Run {
  id: string;
  source: "demo";
  request: TestRequest;
  status: "running" | "completed" | "failed";
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
  steps: RunStep[];
  result?: RunResult;
  error?: string;
  retryOf?: string;
}

export interface TestCase {
  id: string;
  name: string;
  request: TestRequest;
  createdAt: string;
  builtIn: boolean;
}

export interface Comparison {
  id: string;
  caseSnapshot: TestCase;
  runAId: string;
  runBId: string;
  createdAt: string;
}

export interface DevConsoleGateway {
  createRun(request: TestRequest, retryOf?: string): Promise<Run>;
  getRun(id: string): Promise<Run>;
  listCases(): Promise<TestCase[]>;
  getCase(id: string): Promise<TestCase>;
  saveCase(runId: string, name: string): Promise<TestCase>;
  createComparison(caseId: string): Promise<Comparison>;
  getComparison(id: string): Promise<Comparison>;
}

export const TARGET_NAMES: Record<TestTarget, string> = {
  activity: "액티비티",
  dining: "요식업",
  mobility: "이동",
  core: "코어 통합",
};

export const TEAM_IDS: TeamId[] = ["activity", "dining", "mobility"];

export function defaultRequest(target: TestTarget): TestRequest {
  return {
    target,
    version: "B",
    fixtureMode: "normal",
    input: { time: target === "activity" ? "16:45" : target === "dining" ? "14:30" : "16:05", durationMinutes: 60, transport: "bus" },
  };
}
