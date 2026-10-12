import { afterEach, describe, expect, it, vi } from "vitest";

const KEY = "tripilot.web.noticeReads.v1";
const storage = new Map<string, string>();

/** The store keeps what it read in the module: each case loads it afresh over this page's storage. */
async function load(throwing = false) {
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => { if (throwing) throw new Error("blocked"); return storage.get(key) ?? null; },
      setItem: (key: string, value: string) => { if (throwing) throw new Error("blocked"); storage.set(key, value); },
    },
  });
  vi.resetModules();
  return import("./notice-reads");
}

describe("notice reads (this browser only)", () => {
  afterEach(() => { vi.unstubAllGlobals(); storage.clear(); });

  it("keeps the seen notices per trip and adds only the new ones", async () => {
    const { markNoticesSeen } = await load();
    markNoticesSeen("t1", ["n-1", "n-2"]);
    markNoticesSeen("t1", ["n-2", "n-3"]);
    markNoticesSeen("t2", ["n-9"]);
    expect(JSON.parse(storage.get(KEY)!)).toEqual({ t1: ["n-1", "n-2", "n-3"], t2: ["n-9"] });
  });

  it("reads what an earlier page kept, and leaves out a stored value that is not a list of keys", async () => {
    storage.set(KEY, JSON.stringify({ t1: ["n-1"], broken: "n-2", mixed: ["n-3", 4] }));
    const { markNoticesSeen } = await load();
    markNoticesSeen("t1", ["n-2"]);
    expect(JSON.parse(storage.get(KEY)!)).toEqual({ t1: ["n-1", "n-2"] });
  });

  it("does not fail where storage is blocked (private window): the reads are kept for this page only", async () => {
    const { markNoticesSeen } = await load(true);
    expect(() => markNoticesSeen("t1", ["n-1"])).not.toThrow();
    expect(storage.size).toBe(0);
  });
});
