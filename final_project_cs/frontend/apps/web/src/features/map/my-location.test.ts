import { describe, expect, it } from "vitest";
import type { LocationStay } from "@/lib/live/location-samples";
import { ACCURACY_CIRCLE_MAX_M, accuracyRadius, meKey, staysKey } from "./providers/me";
import { stayLabel, toStayPoints } from "./stays";

/** `[2026-10-05 사용자 지시]` 「내 위치」 and the places the customer stayed, as the map draws them (the drawing itself is checked in the browser suite). */
describe("「내 위치」 on the map", () => {
  const at = (accuracyM: number | null) => ({ coordinates: { lat: 37.5796, lng: 126.977 }, accuracyM });

  it("draws the accuracy circle only for a known radius up to 500 m — the dot alone otherwise", () => {
    expect(accuracyRadius(at(35))).toBe(35);
    expect(accuracyRadius(at(ACCURACY_CIRCLE_MAX_M))).toBe(500);
    expect(accuracyRadius(at(501))).toBeNull();           // would cover the day's map and say nothing
    expect(accuracyRadius(at(null))).toBeNull();
    expect(accuracyRadius(at(0))).toBeNull();
    expect(accuracyRadius(at(Number.NaN))).toBeNull();
    expect(accuracyRadius(null)).toBeNull();
  });

  it("redraws only when the place or the circle changes", () => {
    expect(meKey(at(35))).toBe(meKey(at(35)));
    expect(meKey(at(35))).not.toBe(meKey(at(36)));
    expect(meKey(at(600))).toBe(meKey(at(900)));          // no circle either way: nothing to redraw
    expect(meKey(null)).toBe("");
  });
});

describe("where the customer stayed, as grey dots", () => {
  const stay = (patch: Partial<LocationStay> = {}): LocationStay => ({
    stopId: "s1", lat: 37.5796, lng: 126.977, startedAt: "2026-10-01T10:02:00+09:00", endedAt: "2026-10-01T10:41:00+09:00",
    radiusM: 38, points: 9, matchedItemId: null, ...patch,
  });

  it("names a stay by its Seoul times, and by the stop it is near only when that stop is on this map", () => {
    expect(stayLabel(stay(), {})).toBe("머문 곳 · 10:02–10:41");
    expect(stayLabel(stay({ matchedItemId: "i-b" }), { "i-b": "경복궁 관람" })).toBe("머문 곳 · 경복궁 관람 근처 · 10:02–10:41");
    expect(stayLabel(stay({ matchedItemId: "i-x" }), { "i-b": "경복궁 관람" })).toBe("머문 곳 · 10:02–10:41");
    expect(stayLabel(stay({ endedAt: null }), {})).toBe("머문 곳 · 10:02부터 머무는 중");
    expect(stayLabel(stay({ startedAt: "2026-10-01T01:02:00Z", endedAt: "2026-10-01T01:41:00Z" }), {})).toBe("머문 곳 · 10:02–10:41");   // UTC from the server, Seoul on screen
  });

  it("keeps only the stays of the day the map shows (Seoul date), or all of them without a day", () => {
    const stays = [stay(), stay({ stopId: "s2", startedAt: "2026-10-01T23:30:00+09:00", endedAt: null }), stay({ stopId: "s3", startedAt: "2026-09-30T15:10:00Z", endedAt: null })];
    expect(toStayPoints(stays, "2026-10-01", {}).map((point) => point.id)).toEqual(["s1", "s2", "s3"]);     // 15:10Z on 09-30 is 00:10 on 10-01 in Seoul
    expect(toStayPoints(stays, "2026-10-02", {})).toEqual([]);
    expect(toStayPoints(stays, undefined, {})).toHaveLength(3);
    expect(toStayPoints([stay()], "2026-10-01", {})[0]).toEqual({ id: "s1", coordinates: { lat: 37.5796, lng: 126.977 }, label: "머문 곳 · 10:02–10:41" });
    expect(staysKey(toStayPoints(stays, undefined, {}))).toBe(staysKey(toStayPoints(stays, undefined, {})));
  });
});
