import { describe, expect, it } from "vitest";
import { guidanceOf } from "./extras";
import { safetyOf } from "./gateway";

describe("the trip's safety (rest-endpoints 「재난 시 일정 정지」)", () => {
  it("is null for a server that says nothing, and paused:false for a trip with no pause", () => {
    expect(safetyOf(undefined)).toBeNull();
    expect(safetyOf(null)).toBeNull();
    expect(safetyOf({ paused: false })).toMatchObject({ paused: false, level: null, label: null, resume: null, released: false });
  });

  it("reads a day's pause with its words, its times (Seoul time) and the resume the server offers", () => {
    const safety = safetyOf({
      paused: true, level: "day", label: "지진 — 오늘 남은 일정 정지", since: "2026-10-06T05:05:00Z", until: "2026-10-06T15:00:00Z", day: "2026-10-06", released: false,
      resume: { label: "일정 다시 시작", path: "/safety/resume" },
    })!;
    expect(safety.paused).toBe(true);
    expect(safety.level).toBe("day");
    expect(safety.label).toBe("지진 — 오늘 남은 일정 정지");
    expect(safety.since).toBe("2026-10-06 14:05");
    expect(safety.until).toBe("2026-10-07 00:00");
    expect(safety.resume).toEqual({ label: "일정 다시 시작" });
  });

  it("tells a trip that has not started from one under way (and reads nothing it was not given)", () => {
    expect(safetyOf({ paused: true, level: "trip", phase: "upcoming", until: null, resume: { label: "일정 다시 시작" } })).toMatchObject({ phase: "upcoming", until: null, level: "trip" });
    expect(safetyOf({ paused: true, phase: "in_progress" })!.phase).toBe("in_progress");
    expect(safetyOf({ paused: true, phase: "someday" })!.phase).toBeNull();
    expect(safetyOf({ paused: true })!.phase).toBeNull();                 // an older server: not said
    expect(guidanceOf({ phase: "upcoming", shelters: [], shelter_status: "not_applicable" })).toMatchObject({ phase: "upcoming", shelters: [], shelterStatus: "not_applicable" });
  });

  it("keeps a value that is not an instant as it came, and does not invent a level or a resume", () => {
    const safety = safetyOf({ paused: true, level: "weird", until: "2026-10-06" })!;
    expect(safety.level).toBeNull();
    expect(safety.until).toBe("2026-10-06");
    expect(safety.resume).toBeNull();
  });
});

describe("the guidance of a safety alert", () => {
  const raw = {
    level: "day", label: "지진", official: { source: "행정안전부", text: "안전한 곳으로 대피하세요", at: "2026-10-06T05:05:00Z" }, emergency_call: "119", portal: "국민재난안전포털",
    reference: { place: "경복궁", latitude: 37.5796, longitude: 126.977, note: "일정에 적힌 장소 기준이에요. 지금 계신 곳과 다를 수 있어요." },
    shelters: [
      { name: "경복궁 옥외대피장소", address: "서울 종로구 사직로", distance_m: 320, walk_minutes_estimate: 5, underground: false, capacity: 1200, map_url: "https://www.google.com/maps/dir/?api=1&destination=1,2&travelmode=walking" },
      { name: "", address: "이름 없음", distance_m: 10 },
      { name: "수상한 링크", map_url: "javascript:alert(1)" },
    ],
    shelter_status: "ok",
  };

  it("reads the places to go to, drops one with no name, and opens only https links", () => {
    const guidance = guidanceOf(raw)!;
    expect(guidance.shelters.map((shelter) => shelter.name)).toEqual(["경복궁 옥외대피장소", "수상한 링크"]);
    expect(guidance.shelters[0]).toMatchObject({ distanceM: 320, walkMinutes: 5, underground: false, capacity: 1200 });
    expect(guidance.shelters[0].mapUrl).toMatch(/^https:\/\//);
    expect(guidance.shelters[1].mapUrl).toBeNull();                      // not https: never offered as a link
    expect(guidance.shelterStatus).toBe("ok");
  });

  it("keeps the server's note that the reference is the planned place, and a phone number only when it is digits", () => {
    expect(guidanceOf(raw)!.reference?.note).toContain("지금 계신 곳과 다를 수 있어요");
    expect(guidanceOf(raw)!.emergencyCall).toBe("119");
    expect(guidanceOf({ ...raw, emergency_call: "tel:evil" })!.emergencyCall).toBeNull();
  });

  it("is null for a notice that has no guidance, and an empty list with the status when the shelter table is empty", () => {
    expect(guidanceOf(undefined)).toBeNull();
    expect(guidanceOf("text")).toBeNull();
    const empty = guidanceOf({ shelters: [], shelter_status: "no_data" })!;
    expect(empty.shelters).toEqual([]);
    expect(empty.shelterStatus).toBe("no_data");
  });
});
