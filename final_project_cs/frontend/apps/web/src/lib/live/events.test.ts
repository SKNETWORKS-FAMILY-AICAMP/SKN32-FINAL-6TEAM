import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { eventStreamParser, toTripEvent, watchTrip, type TripEvent } from "./events";
import { answeringSession } from "./session-kit";

function memory(initial: Record<string, string> = {}) {
  const items = new Map<string, string>(Object.entries(initial));
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({ start(controller) { chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk))); controller.close(); } });
}

describe("the server's change bell", () => {
  it("splits a stream into events across chunk boundaries and drops the heartbeat", () => {
    const seen: [string, string][] = [];
    const feed = eventStreamParser((name, data) => seen.push([name, data]));
    feed(": ping\n\nevent: ready\ndata: {\"vers");
    feed("ion\": 3}\n\nevent: trip.changed\r\ndata: {\"kinds\":[\"notice\"]}\r\n\r\n: ping\n\n");
    expect(seen).toEqual([["ready", "{\"version\": 3}"], ["trip.changed", "{\"kinds\":[\"notice\"]}"]]);
  });

  it("reads a change's kinds, and treats missing or unknown kinds as 'everything changed'", () => {
    expect(toTripEvent("trip.changed", '{"trip_id":"t1","kinds":["notice","proposal"],"version":4}')).toEqual({ type: "changed", kinds: ["notice", "proposal"], version: 4 });
    expect(toTripEvent("trip.changed", '{"kinds":["weather"]}')).toEqual({ type: "changed", kinds: ["itinerary", "notice", "proposal"], version: null });
    expect(toTripEvent("trip.changed", "not json")).toEqual({ type: "changed", kinds: ["itinerary", "notice", "proposal"], version: null });
    expect(toTripEvent("ready", '{"version":2}')).toEqual({ type: "ready", version: 2 });
    expect(toTripEvent("message", "{}")).toBeNull();
  });

  describe("watching a trip", () => {
    let calls: { url: string; init: RequestInit }[];
    let reply: () => Response;

    beforeEach(() => {
      calls = [];
      vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
      vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return reply(); }));
    });
    afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

    it("sends the session cookie (credentials, never the URL or a key header) and passes the server's events on", async () => {
      reply = () => new Response(streamOf(["event: ready\ndata: {\"version\":1}\n\n", "event: trip.changed\ndata: {\"kinds\":[\"itinerary\"],\"version\":2}\n\n"]), { status: 200, headers: { "Content-Type": "text/event-stream" } });
      const events: TripEvent[] = [];
      const end = await watchTrip("trip 1", "ko", (event) => events.push(event), new AbortController().signal);
      expect(end).toBe("closed");
      expect(calls[0].url).toMatch(/\/v1\/web\/trips\/trip%201\/events$/);
      expect(calls[0].init.credentials).toBe("include");
      expect(new Headers(calls[0].init.headers).get("X-User-Key")).toBeNull();
      expect(new Headers(calls[0].init.headers).get("Accept")).toBe("text/event-stream");
      expect(events).toEqual([{ type: "ready", version: 1 }, { type: "changed", kinds: ["itinerary"], version: 2 }]);
    });

    it("says 'unsupported' for a server without the bell, and 'failed' when it cannot connect", async () => {
      reply = () => new Response("{}", { status: 404 });
      expect(await watchTrip("t1", "ko", () => {}, new AbortController().signal)).toBe("unsupported");
      reply = () => new Response("{}", { status: 405 });
      expect(await watchTrip("t1", "ko", () => {}, new AbortController().signal)).toBe("unsupported");
      reply = () => new Response("{}", { status: 503 });
      expect(await watchTrip("t1", "ko", () => {}, new AbortController().signal)).toBe("failed");
      reply = () => { throw new TypeError("network down"); };
      expect(await watchTrip("t1", "ko", () => {}, new AbortController().signal)).toBe("failed");
    });
  });
});
