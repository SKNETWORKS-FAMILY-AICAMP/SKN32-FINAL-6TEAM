import { describe, expect, it, vi, afterEach } from "vitest";
import { requestIdentity, serviceStatus } from "./client";

afterEach(() => vi.unstubAllGlobals());
describe("inquiry identity after an uncertain response", () => {
  it("uses the original identity for retries of the same trimmed draft", () => {
    const makeId = vi.fn(() => "request-one");
    const first = requestIdentity(null, " Where? ", " My trip ", "en", makeId);
    expect(requestIdentity(first, "Where?", "My trip", "en", makeId)).toBe(first);
    expect(makeId).toHaveBeenCalledTimes(1);
  });
  it("creates a new identity when content or language changes", () => {
    const first = requestIdentity(null, "Where?", "My trip", "en", () => "one");
    expect(requestIdentity(first, "Where?", "Another trip", "en", () => "two").requestId).toBe("two");
    expect(requestIdentity(first, "Where?", "My trip", "ko", () => "three").requestId).toBe("three");
  });
});
describe("public notices", () => {
  it("omits credentials and reads the actual response", async () => {
    const status = { notices: [], maintenance: { enabled: true, message: "점검" } };
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(status)));
    vi.stubGlobal("fetch", fetcher);
    expect(await serviceStatus("ko")).toEqual(status);
    expect(fetcher.mock.calls[0][1].credentials).toBe("omit");
  });
  it("does not turn a failed read into an empty notice list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "unavailable", message: "점검 중" } }), { status: 503 })));
    await expect(serviceStatus("ko")).rejects.toThrow("점검 중");
  });
});
