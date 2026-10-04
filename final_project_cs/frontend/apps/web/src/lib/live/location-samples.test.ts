import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LocationFix } from "../location";
import { CONSENT_REQUIRED_EVENT, LiveError, resetSessionState } from "./client";
import {
  CALLS_PER_SEND, createLocationSampler, deleteLocationSamples, FIXES_PER_CALL, getLocationStops, outcomeOf, readLocationStops,
  type LocationSampleWire,
} from "./location-samples";
import { answeringSession, CSRF } from "./session-kit";

/** A fix `seconds` after 10:00:00Z, `north` metres north of a point in Seoul (1° of latitude ≈ 111 195 m). */
const BASE = Date.parse("2026-10-05T01:00:00.000Z");
const fix = (seconds: number, north = 0, accuracyM: number | null = 12): LocationFix => ({
  lat: 37.5796 + north / 111_195, lng: 126.977, accuracyM, at: new Date(BASE + seconds * 1000).toISOString(),
});

describe("which positions are kept for the server (30 m or 60 s, never the same fix twice)", () => {
  it("keeps the first fix, then one 30 m away or 60 s later — not a small move a few seconds later", () => {
    const sampler = createLocationSampler("t1", { post: async () => ({}) });
    expect(sampler.add(fix(0))).toBe(true);
    expect(sampler.add(fix(10, 20))).toBe(false);           // 20 m, 10 s: same place
    expect(sampler.add(fix(20, 31))).toBe(true);            // 31 m from the last one kept
    expect(sampler.add(fix(50, 35))).toBe(false);           // 4 m, 30 s later
    expect(sampler.add(fix(80, 35))).toBe(true);            // standing still, but 60 s since the last one kept
    expect(sampler.pending).toBe(3);
  });

  it("never keeps the same fix twice, nor an older one (a browser may hand back a cached answer)", () => {
    const sampler = createLocationSampler("t1", { post: async () => ({}) });
    expect(sampler.add(fix(0))).toBe(true);
    expect(sampler.add(fix(0, 500))).toBe(false);           // same time: the same fix
    expect(sampler.add(fix(-5, 500))).toBe(false);          // older
    expect(sampler.pending).toBe(1);
  });

  it("refuses what is not a position (not finite, out of range, no time)", () => {
    const sampler = createLocationSampler("t1", { post: async () => ({}) });
    expect(sampler.add({ ...fix(0), lat: Number.NaN })).toBe(false);
    expect(sampler.add({ ...fix(0), lat: 91 })).toBe(false);
    expect(sampler.add({ ...fix(0), at: "yesterday" })).toBe(false);
    expect(sampler.pending).toBe(0);
  });

  it("sends the contract's shape: lat, lng, accuracy_m (left out when the browser did not say), at", async () => {
    const sent: LocationSampleWire[][] = [];
    const sampler = createLocationSampler("t1", { post: async (fixes) => { sent.push(fixes); } });
    sampler.add(fix(0));
    sampler.add(fix(60, 0, null));
    expect(await sampler.flush()).toBe("sent");
    expect(sent).toEqual([[
      { lat: 37.5796, lng: 126.977, accuracy_m: 12, at: "2026-10-05T01:00:00.000Z" },
      { lat: 37.5796, lng: 126.977, at: "2026-10-05T01:01:00.000Z" },
    ]]);
    expect(sampler.pending).toBe(0);
    expect(await sampler.flush()).toBe("nothing");          // what went is not sent again
    expect(sent).toHaveLength(1);
  });
});

describe("sending (20 a call, and what each refusal means)", () => {
  it("splits a backlog into calls of at most 20, and at most three calls a send — the rest goes next time", async () => {
    const sent: number[] = [];
    const sampler = createLocationSampler("t1", { post: async (fixes) => { sent.push(fixes.length); } });
    for (let index = 0; index < 75; index += 1) sampler.add(fix(index * 60));
    expect(await sampler.flush()).toBe("sent");
    expect(sent).toEqual([FIXES_PER_CALL, FIXES_PER_CALL, FIXES_PER_CALL]);
    expect(sent).toHaveLength(CALLS_PER_SEND);
    expect(sampler.pending).toBe(15);
    await sampler.flush();
    expect(sent).toEqual([20, 20, 20, 15]);
    expect(sampler.pending).toBe(0);
  });

  it("keeps the points when the server could not be reached, and sends them next time — once", async () => {
    let fail = true;
    const sent: string[][] = [];
    const sampler = createLocationSampler("t1", { post: async (fixes) => {
      if (fail) throw new LiveError("network", "서버에 연결하지 못했어요.");
      sent.push(fixes.map((item) => item.at));
    } });
    sampler.add(fix(0));
    expect(await sampler.flush()).toBe("retry");
    expect(sampler.pending).toBe(1);
    sampler.add(fix(60));
    fail = false;
    expect(await sampler.flush()).toBe("sent");
    expect(sent).toEqual([[fix(0).at, fix(60).at]]);
  });

  it("403 consent_required: stops for good, forgets the points, and says so once", async () => {
    let told = 0;
    let calls = 0;
    const sampler = createLocationSampler("t1", {
      post: async () => { calls += 1; throw new LiveError("consent_required", "약관에 동의해야 쓸 수 있어요"); },
      onConsentRequired: () => { told += 1; },
    });
    sampler.add(fix(0));
    expect(await sampler.flush()).toBe("stopped");
    expect(sampler.state).toBe("consent_required");
    expect(sampler.pending).toBe(0);
    expect(told).toBe(1);
    expect(sampler.add(fix(60, 100))).toBe(false);           // nothing more is kept…
    expect(await sampler.flush()).toBe("stopped");           // …or sent
    expect(calls).toBe(1);
  });

  it("404/405 (a server without the route): stops quietly — no retry every minute", async () => {
    for (const code of ["HTTP_404", "HTTP_405", "not_found"]) {
      let calls = 0;
      const sampler = createLocationSampler("t1", { post: async () => { calls += 1; throw new LiveError(code, "x"); } });
      sampler.add(fix(0));
      expect(await sampler.flush()).toBe("stopped");
      expect(sampler.state).toBe("unsupported");
      sampler.add(fix(120, 100));
      await sampler.flush();
      expect(calls).toBe(1);
    }
  });

  it("drops points the server will never take (422) instead of sending them again, and goes on with the rest", async () => {
    const sent: number[] = [];
    let first = true;
    const sampler = createLocationSampler("t1", { post: async (fixes) => {
      if (first) { first = false; throw new LiveError("HTTP_422", "x"); }
      sent.push(fixes.length);
    } });
    for (let index = 0; index < 25; index += 1) sampler.add(fix(index * 60));
    expect(await sampler.flush()).toBe("sent");
    expect(sent).toEqual([5]);                                // the first 20 were refused and dropped
    expect(sampler.pending).toBe(0);
  });

  it("a session that ended stops the sending (sending again would make a new guest)", async () => {
    const sampler = createLocationSampler("t1", { post: async () => { throw new LiveError("session_expired", "x"); } });
    sampler.add(fix(0));
    expect(await sampler.flush()).toBe("stopped");
    expect(sampler.state).toBe("ended");
  });

  it("two sends at once share one call; stop() forgets what is kept", async () => {
    let release!: () => void;
    let calls = 0;
    const sampler = createLocationSampler("t1", { post: () => { calls += 1; return new Promise<void>((resolve) => { release = resolve; }); } });
    sampler.add(fix(0));
    const one = sampler.flush(), two = sampler.flush();
    release();
    expect(await one).toBe("sent");
    expect(await two).toBe("sent");
    expect(calls).toBe(1);
    sampler.add(fix(60));
    sampler.stop();
    expect(sampler.pending).toBe(0);
    expect(await sampler.flush()).toBe("stopped");
  });

  it("names each refusal", () => {
    expect(outcomeOf(new LiveError("timeout", "x"))).toBe("retry");
    expect(outcomeOf(new LiveError("internal_error", "x"))).toBe("retry");
    expect(outcomeOf(new LiveError("HTTP_429", "x"))).toBe("retry");
    expect(outcomeOf(new TypeError("fetch failed"))).toBe("retry");
    expect(outcomeOf(new LiveError("invalid_fixes", "x"))).toBe("drop");
    expect(outcomeOf(new LiveError("forbidden", "x"))).toBe("ended");
  });
});

describe("the server calls (through the session: cookie, and the CSRF token on a write)", () => {
  let replies: Response[];
  let calls: { url: string; init: RequestInit }[];
  let events: string[];

  beforeEach(() => {
    replies = [];
    calls = [];
    events = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: (event: Event) => { events.push(event.type); return true; } });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return replies.shift() ?? new Response("{}", { status: 200 }); }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("POST /v1/web/trips/{id}/location with {fixes} and the CSRF token", async () => {
    replies.push(new Response(JSON.stringify({ saved: 1, skipped: 0 }), { status: 200 }));
    const sampler = createLocationSampler("t 1");
    sampler.add(fix(0));
    expect(await sampler.flush()).toBe("sent");
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toMatch(/\/v1\/web\/trips\/t%201\/location$/);
    expect(calls[0].init.method).toBe("POST");
    expect((calls[0].init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
    expect(calls[0].init.credentials).toBe("include");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ fixes: [{ lat: 37.5796, lng: 126.977, accuracy_m: 12, at: "2026-10-05T01:00:00.000Z" }] });
    expect(calls[0].url).not.toContain("37.5");               // ★never a position in the address
  });

  it("a real 403 consent_required body stops the sampler and the page is told to read the consent again; FastAPI's 404 {detail} stops it quietly", async () => {
    replies.push(new Response(JSON.stringify({ error: { code: "consent_required", message: "약관에 동의해야 쓸 수 있어요", current_version: "2026-10-05", required: ["location"] } }), { status: 403 }));
    const refused = createLocationSampler("t1");
    refused.add(fix(0));
    expect(await refused.flush()).toBe("stopped");
    expect(refused.state).toBe("consent_required");
    expect(events).toContain(CONSENT_REQUIRED_EVENT);         // `api` tells the consent gate, which reads the server's record again
    replies.push(new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }));
    const older = createLocationSampler("t1");
    older.add(fix(0));
    expect(await older.flush()).toBe("stopped");
    expect(older.state).toBe("unsupported");
  });

  it("DELETE /v1/web/trips/{id}/location → {deleted}; a server without the route → null", async () => {
    replies.push(new Response(JSON.stringify({ deleted: 7 }), { status: 200 }));
    expect(await deleteLocationSamples("t1", "ko")).toEqual({ deleted: 7 });
    expect(calls[0].init.method).toBe("DELETE");
    expect((calls[0].init.headers as Record<string, string>)["X-CSRF-Token"]).toBe(CSRF);
    expect(calls[0].url).toMatch(/\/v1\/web\/trips\/t1\/location$/);
    replies.push(new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }));
    expect(await deleteLocationSamples("t1", "ko")).toBeNull();
    replies.push(new Response(JSON.stringify({ error: { code: "internal_error", message: "서버 오류" } }), { status: 500 }));
    await expect(deleteLocationSamples("t1", "ko")).rejects.toMatchObject({ code: "internal_error" });
  });

  it("GET /v1/web/trips/{id}/location/stops; 404/405 → null (nothing to draw), any other refusal is a failure", async () => {
    replies.push(new Response(JSON.stringify({ stops: [], last_fix: null, computed_at: "2026-10-05T10:00:00+09:00" }), { status: 200 }));
    expect(await getLocationStops("t1", "ko")).toEqual({ stops: [], lastFix: null, computedAt: "2026-10-05T10:00:00+09:00" });
    expect(calls[0].url).toMatch(/\/v1\/web\/trips\/t1\/location\/stops$/);
    expect(calls[0].init.method ?? "GET").toBe("GET");
    replies.push(new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }));
    expect(await getLocationStops("t1", "ko")).toBeNull();
    replies.push(new Response("{}", { status: 405 }));
    expect(await getLocationStops("t1", "ko")).toBeNull();
    replies.push(new Response(JSON.stringify({ error: { code: "consent_required", message: "x" } }), { status: 403 }));
    await expect(getLocationStops("t1", "ko")).rejects.toMatchObject({ code: "consent_required" });
  });
});

describe("reading where the server found the customer stayed", () => {
  const stay = (patch: Record<string, unknown> = {}) => ({
    stop_id: "s1", lat: 37.5796, lng: 126.977, started_at: "2026-10-05T10:02:00+09:00", ended_at: "2026-10-05T10:41:00+09:00",
    radius_m: 38, points: 9, matched_item_id: "i-b", ...patch,
  });

  it("keeps what the server said: place, start, end (null while still there), radius, points, the stop it matched", () => {
    const read = readLocationStops({ stops: [stay(), stay({ stop_id: "s2", ended_at: null, matched_item_id: null })],
      last_fix: { lat: 37.57, lng: 126.99, at: "2026-10-05T11:00:00+09:00", accuracy_m: 15 }, computed_at: "2026-10-05T11:00:05+09:00" });
    expect(read.stops).toEqual([
      { stopId: "s1", lat: 37.5796, lng: 126.977, startedAt: "2026-10-05T10:02:00+09:00", endedAt: "2026-10-05T10:41:00+09:00", radiusM: 38, points: 9, matchedItemId: "i-b" },
      { stopId: "s2", lat: 37.5796, lng: 126.977, startedAt: "2026-10-05T10:02:00+09:00", endedAt: null, radiusM: 38, points: 9, matchedItemId: null },
    ]);
    expect(read.lastFix).toEqual({ lat: 37.57, lng: 126.99, at: "2026-10-05T11:00:00+09:00", accuracyM: 15 });
    expect(read.computedAt).toBe("2026-10-05T11:00:05+09:00");
  });

  it("leaves out a stay it cannot place (no id, no place, a place out of range, no start) — never a guess; no points → nothing", () => {
    const read = readLocationStops({ stops: [stay({ stop_id: "" }), stay({ lat: null }), stay({ lng: 200 }), stay({ started_at: "soon" }), stay({ stop_id: "ok", radius_m: -1, points: "9" }), null] });
    expect(read.stops.map((entry) => entry.stopId)).toEqual(["ok"]);
    expect(read.stops[0]).toMatchObject({ radiusM: null, points: null });
    expect(readLocationStops({ stops: [], last_fix: null })).toEqual({ stops: [], lastFix: null, computedAt: null });
    expect(readLocationStops(null)).toEqual({ stops: [], lastFix: null, computedAt: null });
    expect(readLocationStops({ last_fix: { lat: 37.5, lng: 127, at: "" } }).lastFix).toBeNull();
  });
});
