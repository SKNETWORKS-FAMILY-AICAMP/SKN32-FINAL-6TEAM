import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveError } from "./client";
import { chooseProposal, getNotices, getProposals } from "./extras";

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

  it("reads the choices the server is waiting for and drops options that have no name", async () => {
    stub({ "tripilot.web.user-key.v1": "k" });
    replies.push(json({ trip_id: "t1", proposals: [{
      proposal_id: "p1", item_id: "i1", base_version: 3, reason: "closed", protected_by: null, safety: false, status: "open",
      expires_at: "2026-09-29T00:00:00+09:00", chosen_key: null, causes: [],
      options: [{ key: "a", rank: 1, name: "대체 식당", starts_at: "2026-09-28T12:30:00+09:00" }, { key: "b", rank: 2, name: null, starts_at: null }],
    }] }));
    const [proposal] = await getProposals("t1", "ko");
    expect(proposal).toMatchObject({ id: "p1", itemId: "i1", baseVersion: 3, status: "open", safety: false });
    expect(proposal.options.map((option) => option.key)).toEqual(["a"]);
  });

  it("reads the notices with the server's own sentence and links a proposal request to its proposal", async () => {
    stub({ "tripilot.web.user-key.v1": "k" });
    replies.push(json({ notices: [{ key: "n1", type: "proposal_request", kind: null, text: "식당이 문을 닫았어요. 하나 골라 주세요.", version: 3, proposal_id: "p1", options: [], delivery: "sent", at: "2026-09-28T12:30:00+09:00" }] }));
    expect(await getNotices("t1", "ko")).toEqual([{ key: "n1", type: "proposal_request", kind: null, text: "식당이 문을 닫았어요. 하나 골라 주세요.", version: 3, proposalId: "p1", delivery: "sent", at: "2026-09-28T12:30:00+09:00" }]);
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
