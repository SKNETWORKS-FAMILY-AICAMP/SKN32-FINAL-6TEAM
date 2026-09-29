import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveError } from "./client";
import { chooseProposal, getNotices, getProposals, mapLoad, undoChange, warmup } from "./extras";

function memory(initial: Record<string, string> = {}) {
  const items = new Map<string, string>(Object.entries(initial));
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}

describe("the rest of the server's web API", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];

  function stub(storage: Record<string, string>) {
    vi.stubGlobal("window", { localStorage: memory(storage), sessionStorage: memory() });
  }

  beforeEach(() => {
    calls = [];
    replies = [];
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/v1/web/session")) return new Response(JSON.stringify({ user_key: "acop_u_new" }), { status: 201 });
      return replies.shift() ?? new Response("{}", { status: 200 });
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

  it("wakes the model with the stored key and reads what the server said, including a failed load", async () => {
    stub({ "tripilot.web.user-key.v1": "acop_u_mine" });
    replies.push(json({ status: "warming", model: "gemma4:12b", last_attempt: { ok: false, seconds: 28.4, at: "2026-09-29T10:00:00+09:00", reason: "out of memory" }, deduped: true }));
    expect(await warmup("ko")).toEqual({ status: "warming", model: "gemma4:12b", deduped: true, lastAttempt: { ok: false, seconds: 28.4, at: "2026-09-29T10:00:00+09:00", reason: "out of memory" } });
    expect(calls[0].url).toMatch(/\/v1\/web\/warmup$/);
    expect(calls[0].init.method).toBe("POST");
    expect(new Headers(calls[0].init.headers).get("X-User-Key")).toBe("acop_u_mine");
  });

  it("asks the server before a Google map load and reads its count; any failure means not allowed", async () => {
    stub({ "tripilot.web.user-key.v1": "acop_u_mine" });
    replies.push(json({ provider: "google", allowed: true, meter: "google_maps_dynamic_maps", used: { day: 3, month: 40 }, cap: { day: 312, month: 9688 }, fallback: null }));
    expect(await mapLoad("ko")).toEqual({ allowed: true, provider: "google", reason: null, used: { day: 3, month: 40 }, cap: { day: 312, month: 9688 } });
    expect(calls[0].url).toMatch(/\/v1\/web\/map-load$/);
    expect(calls[0].init.method).toBe("POST");
    expect(new Headers(calls[0].init.headers).get("X-User-Key")).toBe("acop_u_mine");

    replies.push(json({ allowed: false, used: { day: 312, month: 900 }, cap: { day: 312, month: 9688 }, fallback: "free_map" }));
    expect(await mapLoad("ko")).toMatchObject({ allowed: false, reason: "cap" });     // an older server: a refusal was the cap
    replies.push(json({ provider: "osm", allowed: false, reason: "setting" }));
    expect(await mapLoad("ko")).toMatchObject({ allowed: false, provider: "osm", reason: "setting" });
    replies.push(json({ provider: "osm", allowed: true }));                          // ★the setting wins over a stray allowed
    expect(await mapLoad("ko")).toMatchObject({ allowed: false, reason: "setting" });
    replies.push(json({ allowed: "yes" }));                       // ★anything but true is not permission
    expect((await mapLoad("ko")).allowed).toBe(false);
    replies.push(json({ error: { code: "unauthorized" } }, 401));
    expect(await mapLoad("ko")).toMatchObject({ allowed: false, reason: "error" });
  });

  it("never asks — and never allows Google — when this browser has no key", async () => {
    stub({});
    expect((await mapLoad("ko")).allowed).toBe(false);
    expect(calls).toHaveLength(0);
  });

  it("does not wake anything — nor create a user — when this browser has no key", async () => {
    stub({});
    expect(await warmup("ko")).toBeNull();
    expect(calls).toHaveLength(0);
  });

  it("reads the choices the server is waiting for and drops options that have no name", async () => {
    stub({ "tripilot.web.user-key.v1": "k" });
    replies.push(json({ trip_id: "t1", proposals: [{
      proposal_id: "p1", item_id: "i1", base_version: 3, reason: "closed", protected_by: null, safety: false, status: "open",
      expires_at: "2026-09-29T00:00:00+09:00", chosen_key: null, causes: [],
      options: [{ key: "a", rank: 1, name: "대체 식당", starts_at: "2026-09-28T12:30:00+09:00", note: "09:00으로 늦추면" }, { key: "b", rank: 2, name: null, starts_at: null },
        { key: "c", rank: 3, name: "근처 식당", starts_at: null, note: "  " }],
    }] }));
    const [proposal] = await getProposals("t1", "ko");
    expect(proposal).toMatchObject({ id: "p1", itemId: "i1", baseVersion: 3, status: "open", safety: false });
    expect(proposal.options.map((option) => option.key)).toEqual(["a", "c"]);
    // how an option bends the request, in the server's words — an empty note is no note
    expect(proposal.options.map((option) => option.note)).toEqual(["09:00으로 늦추면", null]);
  });

  it("reads the notices with the server's own sentence and links a proposal request to its proposal", async () => {
    stub({ "tripilot.web.user-key.v1": "k" });
    replies.push(json({ notices: [{ key: "n1", type: "proposal_request", kind: null, text: "식당이 문을 닫았어요. 하나 골라 주세요.", version: 3, proposal_id: "p1", options: [], delivery: "sent", at: "2026-09-28T12:30:00+09:00" }] }));
    expect(await getNotices("t1", "ko")).toEqual([{ key: "n1", type: "proposal_request", kind: null, text: "식당이 문을 닫았어요. 하나 골라 주세요.", version: 3, proposalId: "p1", delivery: "sent", at: "2026-09-28T12:30:00+09:00", rollback: null }]);
  });

  it("reads the undo an automatic change carries and sends it back as the server gave it", async () => {
    stub({ "tripilot.web.user-key.v1": "k" });
    replies.push(json({ notices: [
      { key: "n1", type: "change_notice", text: "비가 와서 실내로 바꿨어요.", version: 3, delivery: "sent", at: "2026-09-28T12:30:00+09:00",
        rollback: { base_version: 3, to_version: 2, request_id: "rollback:v3->v2", label: "되돌리기", path: "/rollback" } },
      { key: "n2", type: "change_notice", text: "x", version: 2, delivery: "sent", at: "2026-09-28T11:30:00+09:00", rollback: { base_version: "3" } },   // malformed — no button
    ] }));
    const [withUndo, broken] = await getNotices("t1", "ko");
    expect(withUndo.rollback).toEqual({ baseVersion: 3, toVersion: 2, requestId: "rollback:v3->v2" });
    expect(broken.rollback).toBeNull();
    replies.push(json({ status: "rolled_back", answer: "되돌렸어요." }));
    await undoChange("t1", withUndo.rollback!, "ko");
    const call = calls.at(-1)!;
    expect(call.url).toMatch(/\/v1\/web\/trips\/t1\/rollback$/);
    expect(JSON.parse(String(call.init.body))).toEqual({ request_id: "rollback:v3->v2", base_version: 3, to_version: 2 });
  });

  it("chooses an option by its key, and null keeps the plan", async () => {
    stub({ "tripilot.web.user-key.v1": "k" });
    replies.push(json({ status: "adjusted" }), json({ status: "kept" }));
    await chooseProposal("t1", "p1", "a", "ko");
    await chooseProposal("t1", "p1", null, "ko");
    expect(calls.map((call) => [call.url.replace(/^.*\/v1/, "/v1"), JSON.parse(String(call.init.body))])).toEqual([
      ["/v1/web/trips/t1/proposals/p1/choose", { key: "a" }],
      ["/v1/web/trips/t1/proposals/p1/choose", { key: null }],
    ]);
  });

  it("passes the server's refusal through with its code, so the screen can say someone got there first", async () => {
    stub({ "tripilot.web.user-key.v1": "k" });
    replies.push(json({ error: { code: "already_decided", message: "안을 고르지 못했다 — 아무것도 바뀌지 않았다" } }, 409));
    await expect(chooseProposal("t1", "p1", "a", "ko")).rejects.toMatchObject({ code: "already_decided" });
    replies.push(json({ error: { code: "stale", message: "x" } }, 409));
    await expect(chooseProposal("t1", "p1", "a", "ko")).rejects.toBeInstanceOf(LiveError);
  });
});
