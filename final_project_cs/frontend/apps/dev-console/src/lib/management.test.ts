import { afterEach, describe, expect, it, vi } from "vitest";
import { createDemoManagementGateway } from "./demo/management";
import { filterIncidents, incidentEventCount, incidentSources, type IncidentFilters } from "./management";

const emptyFilters: IncidentFilters = { query: "", status: "", severity: "", source: "" };
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe("management sample boundaries", () => {
  it.each([undefined, "live", "", "DEMO"])("never exposes sample incidents without explicit demo mode (%s)", async mode => {
    vi.stubEnv("NEXT_PUBLIC_CONSOLE_DATA_MODE", mode);
    vi.resetModules();
    const { managementGateway } = await import("./management-gateway");
    await expect(managementGateway.getSnapshot()).rejects.toThrow("데이터 연결이 설정되지 않았습니다");
  });

  it("returns independent fictional snapshots and retains zero separately from missing user counts", async () => {
    const gateway = createDemoManagementGateway();
    const first = await gateway.getSnapshot();
    const kma = first.incidents.find(item => item.id === "fp_kma")!;
    expect(kma.affectedUsers).toBe(0);
    kma.affectedUsers = null;
    expect((await gateway.getSnapshot()).incidents.find(item => item.id === "fp_kma")?.affectedUsers).toBe(0);
    expect(first.source).toBe("demo");
  });

  it("keeps aggregate occurrences distinct from the six supplied detail examples", async () => {
    const { incidents } = await createDemoManagementGateway().getSnapshot();
    const llm = incidents.find(item => item.id === "fp_llm")!;
    expect(incidentEventCount(llm)).toBe(37);
    expect(llm.occurrences).toHaveLength(6);
    expect(incidents.reduce((total, item) => total + incidentEventCount(item), 0)).toBe(51);
  });
});

describe("incident discovery", () => {
  it.each(["err-7f3a2c", "tr_01JA9Q7M3K2X", "llm_timeout", "채팅 분류", " ERR-7F3A2C "])("finds the original group for %s", async query => {
    const { incidents } = await createDemoManagementGateway().getSnapshot();
    expect(filterIncidents(incidents, { ...emptyFilters, query }).map(item => item.id)).toEqual(["fp_llm"]);
  });

  it("combines status, severity and occurrence sources without dropping a job inside a server group", async () => {
    const { incidents } = await createDemoManagementGateway().getSnapshot();
    expect(incidentSources(incidents[0])).toEqual(["server", "job"]);
    expect(filterIncidents(incidents, { query: "ERR-7F1D20", status: "new", severity: "high", source: "job" }).map(item => item.id)).toEqual(["fp_llm"]);
    expect(filterIncidents(incidents, { query: "", status: "investigating", severity: "medium", source: "job" }).map(item => item.id)).toEqual(["fp_kma"]);
  });

  it("preserves no matches instead of substituting another incident", async () => {
    const { incidents } = await createDemoManagementGateway().getSnapshot();
    expect(filterIncidents(incidents, { ...emptyFilters, query: "ERR-UNKNOWN" })).toEqual([]);
    expect(filterIncidents(incidents, { ...emptyFilters, status: "resolved" })).toEqual([]);
    expect(incidents.find(item => item.id === "not-an-incident")).toBeUndefined();
  });
});
