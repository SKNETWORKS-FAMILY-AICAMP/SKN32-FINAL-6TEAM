import { describe, expect, it } from "vitest";
import { progress, type PlanCheckView, type ServerProgress } from "./model";
import { serverProgressText } from "./plan-check";

const view = (patch: Partial<PlanCheckView> = {}): PlanCheckView =>
  ({ stage: "checking", title: null, days: [], lines: [], items: [], moves: [], dirty: false, rechecking: null, ...patch });
const at = (phase: ServerProgress["phase"], done: number, total = 10): ServerProgress => ({ phase, done, total, title: null });
const ko = (korean: string) => korean;
const third = 100 / 3;

describe("the bar when the server says how far it is", () => {
  it("counts the places the server finds while it still reads, up to the first third", () => {
    expect(progress(view({ stage: "reading", serverProgress: at("places", 0) }))).toBe(0);
    expect(progress(view({ stage: "reading", serverProgress: at("places", 5) }))).toBeCloseTo(third / 2);
    expect(progress(view({ stage: "reading", serverProgress: at("places", 10) }))).toBeCloseTo(third);
  });

  it("then takes the hours and the legs as the second and third thirds", () => {
    expect(progress(view({ serverProgress: at("hours", 0) }))).toBeCloseTo(third);          // checking starts at the first third
    expect(progress(view({ serverProgress: at("hours", 10) }))).toBeCloseTo(third * 2);
    expect(progress(view({ serverProgress: at("moves", 5) }))).toBeCloseTo(third * 2.5);
  });

  it("never goes back below what the rows drawn already show, and goes forward from phase to phase", () => {
    const earlier = (phase: ServerProgress["phase"], done: number) => progress(view({ serverProgress: at(phase, done) }));
    expect(earlier("places", 3)).toBeCloseTo(third);                                         // checking stage: the rows say at least a third
    expect(earlier("hours", 10)).toBeLessThanOrEqual(earlier("moves", 0) + 1e-9);
    expect(earlier("moves", 0)).toBeLessThanOrEqual(earlier("moves", 10) + 1e-9);
  });

  it("is 100 only when the check is done — the last leg counted is 99 at most, whatever the packet said", () => {
    expect(progress(view({ serverProgress: at("moves", 10) }))).toBe(99);
    expect(progress(view({ stage: "done", serverProgress: at("places", 1, 14) }))).toBe(100);
  });

  it("says 'x/y · name step in progress' and leaves the name out when the packet names none", () => {
    expect(serverProgressText({ phase: "hours", done: 3, total: 14, title: "광장시장" }, ko)).toBe("3/14 · 광장시장 운영시간 확인 중");
    expect(serverProgressText({ phase: "places", done: 1, total: 6, title: "경복궁" }, ko)).toBe("1/6 · 경복궁 장소 확인 중");
    expect(serverProgressText({ phase: "moves", done: 1, total: 12, title: null }, ko)).toBe("1/12 · 이동 확인 중");
  });
});
