import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { agentKeyOf, connectCommand, createAgentKey, isAgentKeysUnsupported, isMemberOnly, listAgentKeys, revokeAgentKey } from "./agent-keys";
import { LiveError, resetSessionState } from "./client";
import { planDownloadUrl } from "./plan-download";
import { answeringSession, CSRF } from "./session-kit";

const row = (patch: Record<string, unknown> = {}) => ({
  key_id: "k1", name: "내 노트북", scope: "read", created_at: "2026-10-04T10:00:00+09:00", expires_at: "2027-01-02T10:00:00+09:00", last_used_at: null, status: "active", ...patch,
});
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("reading an agent key", () => {
  it("keeps what the list gives — and never a key text, which the list does not have", () => {
    expect(agentKeyOf(row())).toEqual({ id: "k1", name: "내 노트북", scope: "read", createdAt: "2026-10-04T10:00:00+09:00", expiresAt: "2027-01-02T10:00:00+09:00", lastUsedAt: null, status: "active" });
    expect(agentKeyOf(row({ scope: "write", status: "revoked", last_used_at: "2026-10-05T01:00:00+09:00" }))).toMatchObject({ scope: "write", status: "revoked", lastUsedAt: "2026-10-05T01:00:00+09:00" });
  });

  it("drops a row without an id or a name, and reads a status it does not know as unusable — never as active", () => {
    expect(agentKeyOf(row({ key_id: "" }))).toBeNull();
    expect(agentKeyOf(row({ name: "  " }))).toBeNull();
    expect(agentKeyOf(null)).toBeNull();
    expect(agentKeyOf(row({ status: "weird" }))?.status).toBe("expired");
    expect(agentKeyOf(row({ scope: "admin" }))?.scope).toBe("read");                    // an unknown scope is the narrower one
  });
});

describe("the agent key calls", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];

  beforeEach(() => {
    calls = [];
    replies = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return replies.shift() ?? json({}); }, { kind: "member" }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("lists the keys of the member (a read: cookie, no CSRF token)", async () => {
    replies.push(json({ keys: [row(), row({ key_id: "k2", name: "서버", status: "expired" }), { nonsense: true }] }));
    const keys = await listAgentKeys("ko");
    expect(keys.map((key) => [key.id, key.status])).toEqual([["k1", "active"], ["k2", "expired"]]);
    expect(calls[0].init.credentials).toBe("include");
    expect(calls[0].init.headers as Record<string, string>).not.toHaveProperty("X-CSRF-Token");
  });

  it("makes a key with the name, the scope and the days — a write: the CSRF token goes along — and hands back the key text once", async () => {
    replies.push(json({ ...row({ name: "클로드 코드" }), key: "acop_a_secret", notice: "한 번만 보여요" }, 201));
    const made = await createAgentKey({ name: "  클로드 코드  ", scope: "write", expiresDays: 30 }, "ko");
    expect(made).toMatchObject({ id: "k1", name: "클로드 코드", key: "acop_a_secret", notice: "한 번만 보여요", status: "active" });
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ name: "클로드 코드", scope: "write", expires_days: 30 });
    expect((calls[0].init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
    expect(calls[0].init.method).toBe("POST");
  });

  it("leaves expires_days out when none is chosen (the server uses 90), and refuses an answer that has no key text — a key that cannot be shown is not a key", async () => {
    replies.push(json({ ...row(), key: "acop_a_x" }, 201));
    await createAgentKey({ name: "a", scope: "read" }, "ko");
    expect(JSON.parse(String(calls[0].init.body))).not.toHaveProperty("expires_days");
    replies.push(json(row(), 201));
    await expect(createAgentKey({ name: "a", scope: "read" }, "ko")).rejects.toMatchObject({ code: "bad_agent_key" });
  });

  it("revokes one key by its id", async () => {
    replies.push(json({ key_id: "k 1", status: "revoked" }));
    await revokeAgentKey("k 1", "ko");
    expect(calls[0].url).toMatch(/\/v1\/web\/agent-keys\/k%201$/);
    expect(calls[0].init.method).toBe("DELETE");
    expect((calls[0].init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
  });

  it("tells an older server (no such route) and a guest's refusal apart from other failures", async () => {
    replies.push(json({ detail: "Not Found" }, 404));
    expect(isAgentKeysUnsupported(await listAgentKeys("ko").catch((error: unknown) => error))).toBe(true);
    replies.push(json({ error: { code: "member_only", message: "로그인한 사용자만", login_required: true } }, 403));
    const refused = await createAgentKey({ name: "a", scope: "read" }, "ko").catch((error: unknown) => error);
    expect(isMemberOnly(refused)).toBe(true);
    expect(isAgentKeysUnsupported(refused)).toBe(false);
    expect(isMemberOnly(new LiveError("agent_key_limit", "x"))).toBe(false);
  });
});

describe("the line that connects Claude Code", () => {
  it("carries the key in a header and never in the address", () => {
    const line = connectCommand("https://example.test/", "acop_a_abc");
    expect(line).toBe('claude mcp add --transport http tripilot https://example.test/mcp/ --header "Authorization: Bearer acop_a_abc"');
    expect(line.split(" ").find((part) => part.startsWith("https://"))).not.toContain("acop_a_abc");
  });
});

describe("the trip plan as a file", () => {
  it("adds download=1 to the plan link and keeps everything else (the token, the path)", () => {
    expect(planDownloadUrl("https://example.test/plan/t1?t=abc")).toBe("https://example.test/plan/t1?t=abc&download=1");
    expect(planDownloadUrl("http://127.0.0.1:8042/plan/t1?t=abc&download=0")).toBe("http://127.0.0.1:8042/plan/t1?t=abc&download=1");
  });

  it("gives no link for an address that is not http(s) — never a script or data address", () => {
    expect(planDownloadUrl("javascript:alert(1)")).toBeNull();
    expect(planDownloadUrl("data:text/html,x")).toBeNull();
    expect(planDownloadUrl("not a url")).toBeNull();
  });
});
