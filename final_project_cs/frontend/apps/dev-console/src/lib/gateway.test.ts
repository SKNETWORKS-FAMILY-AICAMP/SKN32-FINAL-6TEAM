import { afterEach, describe, expect, it, vi } from "vitest";
import { defaultRequest } from "./model";

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe("explicit data mode selection", () => {
  it.each([undefined, "api", "", "DEMO"])("does not silently use demo for %s mode", async (mode) => {
    vi.stubEnv("NEXT_PUBLIC_CONSOLE_DATA_MODE", mode);
    vi.resetModules();
    const { gateway, dataMode } = await import("./gateway");
    expect(dataMode).toBe("unconfigured");
    await expect(gateway.createRun(defaultRequest("activity"))).rejects.toThrow("실제 코어 API 어댑터는 아직 구현되지 않았습니다");
  });

  it("uses demo only when explicitly selected and defers browser storage access", async () => {
    vi.stubEnv("NEXT_PUBLIC_CONSOLE_DATA_MODE", "demo");
    vi.resetModules();
    const { dataMode } = await import("./gateway");
    expect(dataMode).toBe("demo");
  });
});
