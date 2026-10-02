import { describe, expect, it } from "vitest";
import { connectionAfter, FAILURES_BEFORE_POLLING, needsPolling, SILENT_AFTER_MS, type StreamConnection } from "./stream-connection";

describe("how the check screen hears about the reading", () => {
  it("is live as soon as anything arrives, from any state but closed", () => {
    for (const from of ["connecting", "lost", "polling", "live"] as StreamConnection[]) {
      expect(connectionAfter(from, { kind: "heard" })).toBe("live");
    }
  });

  it("goes quiet after two missed heartbeats (6 s) and not before", () => {
    expect(SILENT_AFTER_MS).toBe(6_000);
    expect(connectionAfter("live", { kind: "silent", ms: SILENT_AFTER_MS - 1 })).toBe("live");
    expect(connectionAfter("live", { kind: "silent", ms: SILENT_AFTER_MS })).toBe("lost");
  });

  it("calls a stream that never said anything lost too — the first byte is the 'received' event", () => {
    expect(connectionAfter("connecting", { kind: "silent", ms: 7_000 })).toBe("lost");
  });

  it("leaves a screen that is already polling or reconnecting where it is when the silence goes on", () => {
    expect(connectionAfter("polling", { kind: "silent", ms: 60_000 })).toBe("polling");
    expect(connectionAfter("lost", { kind: "silent", ms: 60_000 })).toBe("lost");
  });

  it("goes straight to polling when this server has no stream", () => {
    expect(connectionAfter("connecting", { kind: "ended", end: "unsupported", failures: 1 })).toBe("polling");
  });

  it("shows 'reconnecting' for the first failures and polling once it keeps failing", () => {
    expect(connectionAfter("live", { kind: "ended", end: "failed", failures: 1 })).toBe("lost");
    expect(connectionAfter("lost", { kind: "ended", end: "closed", failures: FAILURES_BEFORE_POLLING - 1 })).toBe("lost");
    expect(connectionAfter("lost", { kind: "ended", end: "failed", failures: FAILURES_BEFORE_POLLING })).toBe("polling");
  });

  it("stays closed once the reading is over", () => {
    for (const signal of [{ kind: "heard" }, { kind: "silent", ms: 99_999 }, { kind: "ended", end: "failed", failures: 9 }] as const) {
      expect(connectionAfter("closed", signal)).toBe("closed");
    }
  });

  it("polls whenever the stream is not carrying the reading — never while it is, never once it ended", () => {
    expect(needsPolling("live")).toBe(false);
    expect(needsPolling("closed")).toBe(false);
    for (const state of ["connecting", "lost", "polling"] as const) expect(needsPolling(state)).toBe(true);
  });
});
