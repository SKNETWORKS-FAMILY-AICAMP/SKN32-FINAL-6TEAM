import { describe, expect, it } from "vitest";
import { guideSteps } from "@/features/intro/guide-steps";
import { FAQ, FAQ_CATEGORIES, SCREENS, type Pair } from "./content";
import { faqCount, openingOf, ruleOf, searchHelp, shown, stepDetail, type Features } from "./model";

const ko = (pair: Pair) => pair[0];
const en = (pair: Pair) => pair[1];
const server: Features = { guardian: true, riskPanel: false };          // the server's defaults
const off: Features = { guardian: false, riskPanel: false };
const all: Features = { guardian: true, riskPanel: true };

describe("「이용 방법」 content (ST4F-717)", () => {
  it("has the intro's seven steps, each opening its own screen, in both languages", () => {
    expect(guideSteps).toHaveLength(7);
    expect(SCREENS.slice(0, 7).map((screen) => screen.shot)).toEqual(guideSteps.map((step) => step.shot));
  });

  it("names everything in Korean and English", () => {
    const pairs: Pair[] = [...SCREENS.flatMap((screen) => [screen.name, screen.where, ...(screen.note ? [screen.note] : []), ...[...screen.points, ...(screen.more ?? [])].flatMap((point) => [point.label, point.desc, ...(point.rule ? [point.rule] : [])]),
      ...(screen.board ?? []).flatMap((row) => [row.title, row.note])]), ...FAQ.flatMap((faq) => [faq.q, faq.a]), ...FAQ_CATEGORIES.map(([, name]) => name)];
    expect(pairs.filter(([kor, eng]) => !kor.trim() || !eng.trim())).toEqual([]);
  });

  it("points a question only at screens that exist, and gives every question its own id", () => {
    const ids = new Set(SCREENS.map((screen) => screen.id));
    expect(FAQ.flatMap((faq) => faq.screens).filter((id) => !ids.has(id))).toEqual([]);
    expect(new Set(FAQ.map((faq) => faq.id)).size).toBe(FAQ.length);
  });

  it("places every point on its capture, or numbers it on the board of a screen without one", () => {
    for (const screen of SCREENS) {
      if (screen.shot) expect(screen.points.every((point) => point.at && point.at[0] < 780 && point.at[1] < 1594)).toBe(true);
      else expect((screen.board ?? []).flatMap((row) => row.point ?? []).sort()).toEqual(screen.points.map((_, index) => index));
    }
  });
});

describe("what the operator switched off is not explained (D4)", () => {
  it("hides the Course Keeper's points, questions and sentence when it is off", () => {
    const reading = SCREENS.find((screen) => screen.id === "reading")!;
    expect(shown(reading.points, server)).toHaveLength(reading.points.length);
    expect(shown(reading.points, off)).toHaveLength(reading.points.length - 1);
    expect(shown(FAQ, off).some((faq) => faq.needs === "guardian")).toBe(false);
    expect(ko(stepDetail(guideSteps[5], server))).toContain("항로 지킴이");
    expect(ko(stepDetail(guideSteps[5], off))).not.toContain("항로 지킴이");
    const menuPoint = SCREENS.find((screen) => screen.id === "trip")!.points.find((point) => point.ruleNeeds === "guardian")!;
    expect(ruleOf(menuPoint, server)).toBeDefined();
    expect(ruleOf(menuPoint, off)).toBeUndefined();
  });

  it("shows the risk panel's question only while the operator has the panel on", () => {
    expect(faqCount("all", all)).toBe(faqCount("all", server) + 1);
    expect(searchHelp("현재 일정 위험 확인", ko, server)).toEqual([]);
    expect(searchHelp("현재 일정 위험 확인", ko, all).length).toBeGreaterThan(0);
  });
});

describe("search", () => {
  it("finds words across the three tabs, ignoring the marks around the app's words", () => {
    const hits = searchHelp("「문의 작성」", ko, server);
    expect(hits.map((hit) => hit.kind)).toEqual(expect.arrayContaining(["point", "faq"]));
    expect(searchHelp("항로 지킴이", ko, off)).toEqual([]);
    expect(searchHelp("Course Keeper", en, server).length).toBeGreaterThan(0);
    expect(searchHelp("   ", ko, server)).toEqual([]);
  });

  it("leads each result to its place", () => {
    expect(searchHelp("예시 불러오기", ko, server)[0].target).toEqual({ tab: "screens", screen: "input", point: 2 });
    expect(searchHelp("로그아웃은 어디서", ko, server)[0].target).toEqual({ tab: "faq", faq: "sign-out" });
  });
});

describe("the address", () => {
  it("opens a screen's part from the (?) and the questions from the inquiries", () => {
    expect(openingOf(undefined, "input")).toEqual({ tab: "screens", screen: "input" });
    expect(openingOf("faq", undefined)).toEqual({ tab: "faq", screen: "input" });
    expect(openingOf("nonsense", "nowhere")).toEqual({ tab: "start", screen: "input" });
  });
});
