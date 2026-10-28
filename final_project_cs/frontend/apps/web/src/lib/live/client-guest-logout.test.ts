import { afterEach, describe, expect, it, vi } from "vitest";
import { api, currentSession, ensureSession, logout, resetSessionState, takeSession } from "./client";
import { sessionBody } from "./session-kit";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("ST4F-728 guest response after logout", () => {
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it.each(["session", "write"])("stops a pending %s when logout finishes before guest creation replies", async (kind) => {
    let release!: (response: Response) => void;
    let started!: () => void;
    const waiting = new Promise<void>((resolve) => { started = resolve; });
    const writes: string[] = [];
    vi.stubGlobal("fetch", async (url: string) => {
      const path = new URL(url).pathname;
      if (path.endsWith("/auth/me")) return json({ error: { code: "unauthenticated" } }, 401);
      if (path.endsWith("/auth/session")) {
        started();
        return new Promise<Response>((resolve) => { release = resolve; });
      }
      if (path.endsWith("/auth/logout")) return json({ status: "signed_out" });
      writes.push(path);
      return json({ saved: true });
    });
    const pending = (kind === "session" ? ensureSession("ko") : api("/v1/web/trip-intakes", "ko", { method: "POST", body: "{}" }))
      .then((value) => ({ value }), (error: unknown) => ({ error }));
    await waiting;
    await logout("ko");
    expect(currentSession()).toBeNull();
    release(json(sessionBody(), 201));
    expect(await pending).toMatchObject({ error: { code: "session_changed" } });
    expect(currentSession()).toBeNull();
    expect(writes).toEqual([]);
  });

  it("keeps a member who signed in while guest creation waited", async () => {
    let release!: (response: Response) => void;
    let started!: () => void;
    const waiting = new Promise<void>((resolve) => { started = resolve; });
    vi.stubGlobal("fetch", async (url: string) => {
      if (new URL(url).pathname.endsWith("/auth/me")) return json({ error: { code: "unauthenticated" } }, 401);
      started();
      return new Promise<Response>((resolve) => { release = resolve; });
    });
    const pending = ensureSession("ko");
    await waiting;
    const member = { kind: "member" as const, csrf: "new-member", guestIdleHours: null, idleExpiresAt: null, absoluteExpiresAt: null };
    takeSession(member);
    release(json(sessionBody(), 201));
    expect(await pending).toBe(member);
    expect(currentSession()).toBe(member);
  });
});
