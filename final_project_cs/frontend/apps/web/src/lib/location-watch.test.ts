import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { distanceM, FOLLOW_KEEPALIVE_MS, FOLLOW_MIN_MS, forgetLocation, isNewFix, watchLocation, type LocationFix, type LocationFailure } from "./location";

type Position = { coords: { latitude: number; longitude: number; accuracy: number }; timestamp: number };
type Success = (position: Position) => void;
type Failure = (error: { code: number }) => void;

/** `[2026-10-05]` Following the position while a map shows (`watchLocation`): one shared browser watch, thinned out, paused while the page is hidden. */
describe("following the customer's position on a map", () => {
  let watches: { ok: Success; fail: Failure; id: number }[];
  let cleared: number[];
  let visibility: "visible" | "hidden";
  let onVisibility: (() => void) | null;
  const T0 = Date.parse("2026-10-05T01:00:00Z");
  /** A browser fix `north` metres north of a point in Seoul, taken at the page clock now. */
  const position = (north = 0, accuracy = 12): Position => ({ coords: { latitude: 37.5796 + north / 111_195, longitude: 126.977, accuracy }, timestamp: Date.now() });
  const give = (north = 0, accuracy = 12) => watches.filter((watch) => !cleared.includes(watch.id)).forEach((watch) => watch.ok(position(north, accuracy)));

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(T0);
    watches = [];
    cleared = [];
    visibility = "visible";
    onVisibility = null;
    forgetLocation();
    vi.stubGlobal("window", { isSecureContext: true });
    vi.stubGlobal("document", {
      get visibilityState() { return visibility; },
      addEventListener: (name: string, handler: () => void) => { if (name === "visibilitychange") onVisibility = handler; },
      removeEventListener: (name: string) => { if (name === "visibilitychange") onVisibility = null; },
    });
    vi.stubGlobal("navigator", { geolocation: {
      watchPosition: (ok: Success, fail: Failure) => { const id = watches.length + 1; watches.push({ ok, fail, id }); return id; },
      clearWatch: (id: number) => { cleared.push(id); },
      getCurrentPosition: () => {},
    } });
  });
  afterEach(() => { forgetLocation(); vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("measures metres between two points", () => {
    expect(distanceM({ lat: 37.5, lng: 127 }, { lat: 37.5 + 100 / 111_195, lng: 127 })).toBeCloseTo(100, 0);
    expect(distanceM({ lat: 37.5, lng: 127 }, { lat: 37.5, lng: 127 })).toBe(0);
  });

  it("decides what is a new position: moved 5 m, surer, or 30 s later — never the same fix again", () => {
    const at = (seconds: number) => new Date(T0 + seconds * 1000).toISOString();
    const base: LocationFix = { lat: 37.5, lng: 127, accuracyM: 20, at: at(0) };
    const north = (metres: number) => base.lat + metres / 111_195;
    expect(isNewFix(null, base)).toBe(true);
    expect(isNewFix(base, { ...base })).toBe(false);                                   // the same fix handed back
    expect(isNewFix(base, { ...base, at: at(-1), lat: north(50) })).toBe(false);        // older
    expect(isNewFix(base, { ...base, at: at(3), lat: north(3) })).toBe(false);          // 3 m: GPS wobble
    expect(isNewFix(base, { ...base, at: at(3), lat: north(6) })).toBe(true);
    expect(isNewFix(base, { ...base, at: at(3), accuracyM: 8 })).toBe(true);            // much surer: the circle shrinks
    expect(isNewFix(base, { ...base, at: at(3), accuracyM: 18 })).toBe(false);
    expect(isNewFix(base, { ...base, at: at(FOLLOW_KEEPALIVE_MS / 1000), lat: north(1) })).toBe(true);   // standing still, but 30 s later
  });

  it("shares one browser watch between two maps, hands the last fix to a map that comes later, and ends the watch when the last one stops", async () => {
    const first: LocationFix[] = [], second: LocationFix[] = [];
    const stopFirst = watchLocation((fix) => first.push(fix));
    give();
    expect(first).toHaveLength(1);
    const stopSecond = watchLocation((fix) => second.push(fix));
    expect(watches).toHaveLength(1);                                                   // one watch for both
    await Promise.resolve();
    expect(second).toEqual(first);                                                     // the latest fix, at once
    stopFirst();
    expect(cleared).toEqual([]);
    stopSecond();
    expect(cleared).toEqual([1]);
  });

  it("thins the browser's fixes: a small move is dropped, a quick one waits out the 2 s and the newest goes", () => {
    const seen: number[] = [];
    watchLocation((fix) => seen.push(Math.round(distanceM({ lat: 37.5796, lng: 126.977 }, fix))));
    give(0);
    vi.advanceTimersByTime(500);
    give(3);                                                                           // 3 m: dropped
    vi.advanceTimersByTime(500);
    give(20);                                                                          // 20 m but 1 s after the last one: held
    vi.advanceTimersByTime(300);
    give(40);                                                                          // newer: replaces the held one
    expect(seen).toEqual([0]);
    vi.advanceTimersByTime(FOLLOW_MIN_MS);
    expect(seen).toEqual([0, 40]);                                                     // the map ends where the customer is
    vi.advanceTimersByTime(5_000);
    give(41);                                                                          // 1 m: dropped
    expect(seen).toEqual([0, 40]);
    vi.advanceTimersByTime(FOLLOW_KEEPALIVE_MS);
    give(41);                                                                          // standing still, 30 s later: handed out (the server needs it to see a stay)
    expect(seen).toEqual([0, 40, 41]);
  });

  it("stops while the page is hidden and starts again when it shows", () => {
    const stop = watchLocation(() => {});
    expect(watches).toHaveLength(1);
    visibility = "hidden";
    onVisibility?.();
    expect(cleared).toEqual([1]);
    visibility = "visible";
    onVisibility?.();
    expect(watches).toHaveLength(2);
    stop();
    expect(cleared).toEqual([1, 2]);
    expect(onVisibility).toBeNull();                                                   // nothing left listening
  });

  it("does not start while the page is hidden", () => {
    visibility = "hidden";
    watchLocation(() => {});
    expect(watches).toHaveLength(0);
    visibility = "visible";
    onVisibility?.();
    expect(watches).toHaveLength(1);
  });

  it("says why it cannot: refused (and stops the watch), too slow (and goes on)", () => {
    const reasons: LocationFailure[] = [];
    watchLocation(() => {}, (reason) => reasons.push(reason));
    watches[0].fail({ code: 3 });
    expect(reasons).toEqual(["timeout"]);
    expect(cleared).toEqual([]);
    watches[0].fail({ code: 1 });
    expect(reasons).toEqual(["timeout", "denied"]);
    expect(cleared).toEqual([1]);
  });

  it("does not ask on an insecure page or a browser without it, and says so", async () => {
    const reasons: LocationFailure[] = [];
    vi.stubGlobal("window", { isSecureContext: false });
    watchLocation(() => {}, (reason) => reasons.push(reason));
    vi.stubGlobal("window", { isSecureContext: true });
    vi.stubGlobal("navigator", {});
    watchLocation(() => {}, (reason) => reasons.push(reason));
    const stopped = watchLocation(() => {}, (reason) => reasons.push(reason));
    stopped();                                                                         // stopped before it could say: says nothing
    await Promise.resolve();
    expect(reasons).toEqual(["insecure", "unsupported"]);
    expect(watches).toHaveLength(0);
  });
});
