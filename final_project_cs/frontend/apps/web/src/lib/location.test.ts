import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { currentLocation, forgetLocation, locationFailureText, locationPermission } from "./location";

type Success = (position: { coords: { latitude: number; longitude: number; accuracy: number }; timestamp: number }) => void;
type Failure = (error: { code: number }) => void;

describe("the customer's current position (browser Geolocation API)", () => {
  let asked: number;
  let answer: (ok: Success, fail: Failure) => void;

  beforeEach(() => {
    asked = 0;
    forgetLocation();
    vi.stubGlobal("window", { isSecureContext: true });
    vi.stubGlobal("navigator", { geolocation: { getCurrentPosition: (ok: Success, fail: Failure) => { asked += 1; answer(ok, fail); } } });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("reads the browser's fix, and reuses it for two minutes instead of asking again", async () => {
    const at = Date.parse("2026-09-30T06:00:00Z");
    answer = (ok) => ok({ coords: { latitude: 37.5796, longitude: 126.977, accuracy: 18.4 }, timestamp: at });
    expect(await currentLocation({ now: at })).toEqual({ ok: true, fix: { lat: 37.5796, lng: 126.977, accuracyM: 18, at: "2026-09-30T06:00:00.000Z" } });
    expect((await currentLocation({ now: at + 60_000 })).ok).toBe(true);
    expect(asked).toBe(1);
    await currentLocation({ now: at + 3 * 60_000 });
    expect(asked).toBe(2);
  });

  it("returns why it failed instead of throwing", async () => {
    answer = (_ok, fail) => fail({ code: 1 });
    expect(await currentLocation()).toEqual({ ok: false, reason: "denied" });
    answer = (_ok, fail) => fail({ code: 3 });
    expect(await currentLocation()).toEqual({ ok: false, reason: "timeout" });
    answer = (_ok, fail) => fail({ code: 2 });
    expect(await currentLocation()).toEqual({ ok: false, reason: "unavailable" });
  });

  it("does not ask on an insecure page or a browser without it", async () => {
    answer = (ok) => ok({ coords: { latitude: 1, longitude: 1, accuracy: 1 }, timestamp: Date.now() });
    vi.stubGlobal("window", { isSecureContext: false });
    expect(await currentLocation()).toEqual({ ok: false, reason: "insecure" });
    vi.stubGlobal("window", { isSecureContext: true });
    vi.stubGlobal("navigator", {});
    expect(await currentLocation()).toEqual({ ok: false, reason: "unsupported" });
    expect(asked).toBe(0);
  });

  it("shares one request between presses that come at once", async () => {
    let finish: Success = () => {};
    answer = (ok) => { finish = ok; };
    const both = Promise.all([currentLocation(), currentLocation()]);
    finish({ coords: { latitude: 37.5, longitude: 127, accuracy: 30 }, timestamp: Date.now() });
    const [first, second] = await both;
    expect(first).toEqual(second);
    expect(asked).toBe(1);
  });

  it("says whether permission was given without asking, and 'unknown' where the browser cannot say", async () => {
    vi.stubGlobal("navigator", { permissions: { query: async () => ({ state: "denied" }) } });
    expect(await locationPermission()).toBe("denied");
    vi.stubGlobal("navigator", {});
    expect(await locationPermission()).toBe("unknown");
  });

  it("tells the customer what to do for each failure", () => {
    const ko = (text: string) => text;
    expect(locationFailureText("denied", ko)).toContain("사이트 설정");
    expect(locationFailureText("timeout", ko)).toContain("밖에서");
    expect(locationFailureText("insecure", ko)).toContain("https");
  });
});
