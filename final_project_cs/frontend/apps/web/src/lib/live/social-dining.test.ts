import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { answeringSession } from "./session-kit";
import { applyDiningLinks, createDiningDraft, listDiningLinks, previewDiningLinks, resolveDiningLinks, updateDiningLink } from "./social-dining";

const memory = () => { const data = new Map<string, string>(); return { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => { data.set(key, value); }, removeItem: (key: string) => { data.delete(key); } }; };
describe("authenticated restaurant link calls", () => {
  let calls: { url: string; init: RequestInit }[];
  beforeEach(() => {
    calls = [];
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return Response.json({ revision: 3, links: [] }); }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });
  it("encodes the intake and link key and sends only explicit supplementation", async () => {
    await listDiningLinks("i /1", "ko");
    await updateDiningLink("i /1", "yt:one/a", { name: "성수 국수", area: "성수", priority: "must", restaurant_index: 1, selected_ref: "kakao:1" }, "ko");
    expect(new URL(calls[0].url).pathname).toBe("/v1/web/trip-intakes/i%20%2F1/dining-links");
    expect(new URL(calls[1].url).pathname).toBe("/v1/web/trip-intakes/i%20%2F1/dining-links/yt%3Aone%2Fa");
    expect(calls[1].init.method).toBe("PATCH");
    expect(JSON.parse(String(calls[1].init.body))).toEqual({ name: "성수 국수", area: "성수", priority: "must", restaurant_index: 1, selected_ref: "kakao:1" });
    expect(calls[0].init.credentials).toBe("include");
  });
  it("resolves several links through the progress stream without generating an itinerary", async () => {
    await resolveDiningLinks("i1", [{ url: "https://youtu.be/one", note: "국수", priority: "if_fits" }, { url: "https://www.instagram.com/p/two/" }], "en");
    expect(calls).toHaveLength(1);
    expect(calls[0].init.headers).toMatchObject({ Accept: "text/event-stream" });
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ links: [{ url: "https://youtu.be/one", note: "국수", priority: "if_fits" }, { url: "https://www.instagram.com/p/two/" }] });
  });
  it("separates a target meal preview from explicit application using the same revision", async () => {
    await previewDiningLinks("i1", 3, "ko", "0-2");
    await applyDiningLinks("i1", 3, "p1", "ko");
    expect(calls.map(({ url, init }) => [new URL(url).pathname, JSON.parse(String(init.body))])).toEqual([
      ["/v1/web/trip-intakes/i1/dining-links/preview", { revision: 3, target_item_id: "0-2" }],
      ["/v1/web/trip-intakes/i1/dining-links/apply", { revision: 3, proposal_id: "p1" }],
    ]);
    // [2026-10-15 브라우저 실측] 적용은 1분을 넘길 수 있다 — 일반 응답 시간 제한에 끊기지 않게 진행 상태(SSE)로 받는다.
    expect(calls[1].init.headers).toMatchObject({ Accept: "text/event-stream" });
  });
  it("creates a review-only draft on the intake that already stores the restaurant wishlist", async () => {
    await createDiningDraft("same-intake", 8, { start_date: "2026-10-20", days: 3, party_size: 2 }, "ko");
    expect(new URL(calls[0].url).pathname).toBe("/v1/web/trip-intakes/same-intake/plan");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ revision: 8, start_date: "2026-10-20", days: 3, party_size: 2, keep_read_items: true, review_only: true });
  });
});
