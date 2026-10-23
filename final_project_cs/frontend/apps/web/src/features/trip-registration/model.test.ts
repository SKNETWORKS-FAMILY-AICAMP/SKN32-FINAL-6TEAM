import { describe, expect, it } from "vitest";
import { askProblem, emptyAsk, isRealDate, paneOfSending, paneReady, paneReason, seoulToday, type PaneValues } from "./model";

const TODAY = "2026-10-03";
const full = { start: "2026-10-05", days: 3, party: 2, wish: "" };
const values = (change: Partial<PaneValues> = {}): PaneValues => ({ text: "", files: 0, ask: emptyAsk, ...change });

describe("the panel the customer chose decides whether 「계획 확인하기」 can go on", () => {
  it("text: one letter besides spaces is enough, spaces alone are not", () => {
    expect(paneReady("text", values({ text: "" }), TODAY)).toBe(false);
    expect(paneReady("text", values({ text: " \n\t " }), TODAY)).toBe(false);
    expect(paneReady("text", values({ text: " a " }), TODAY)).toBe(true);
  });

  it("files: at least one file", () => {
    expect(paneReady("files", values({ files: 0 }), TODAY)).toBe(false);
    expect(paneReady("files", values({ files: 1 }), TODAY)).toBe(true);
  });

  it("plan: all three of first day, days (1-7) and travelers (1-4) are chosen", () => {
    expect(paneReady("plan", values({ ask: emptyAsk }), TODAY)).toBe(false);
    expect(paneReady("plan", values({ ask: full }), TODAY)).toBe(true);
    expect(paneReady("plan", values({ ask: { ...full, start: "" } }), TODAY)).toBe(false);
    expect(paneReady("plan", values({ ask: { ...full, days: 0 } }), TODAY)).toBe(false);
    expect(paneReady("plan", values({ ask: { ...full, party: 0 } }), TODAY)).toBe(false);
    expect(paneReady("plan", values({ ask: { ...full, days: 8 } }), TODAY)).toBe(false);
    expect(paneReady("plan", values({ ask: { ...full, party: 5 } }), TODAY)).toBe(false);
    expect(paneReady("plan", values({ ask: { ...full, days: 7, party: 4 } }), TODAY)).toBe(true);
  });

  it("only the chosen panel counts: a full text does not open the planning panel, and the other way round", () => {
    expect(paneReady("plan", values({ text: "경복궁", files: 2 }), TODAY)).toBe(false);
    expect(paneReady("text", values({ files: 2, ask: full }), TODAY)).toBe(false);
    expect(paneReady("files", values({ text: "경복궁", ask: full }), TODAY)).toBe(false);
  });

  it("the wish is optional: the planning panel is ready without it", () => {
    expect(paneReady("plan", values({ ask: { ...full, wish: "" } }), TODAY)).toBe(true);
    expect(paneReady("plan", values({ ask: { ...full, wish: "조용한 곳" } }), TODAY)).toBe(true);
  });
});

describe("the first day", () => {
  it("is today (Seoul) or later; a day before today is refused, and says so", () => {
    expect(askProblem({ ...full, start: "2026-10-03" }, TODAY)).toBeNull();
    expect(askProblem({ ...full, start: "2026-10-02" }, TODAY)).toBe("past");
    expect(paneReason("plan", values({ ask: { ...full, start: "2026-10-02" } }), TODAY)?.[0]).toContain("오늘");
  });

  it("is not checked against today until today is known", () => {
    expect(askProblem({ ...full, start: "2020-01-01" }, "")).toBeNull();
  });

  it("must be a real calendar date", () => {
    expect(isRealDate("2026-10-03")).toBe(true);
    expect(isRealDate("2026-02-30")).toBe(false);
    expect(isRealDate("2026-1-3")).toBe(false);
    expect(isRealDate("")).toBe(false);
    expect(askProblem({ ...full, start: "2026-02-30" }, TODAY)).toBe("start");
  });

  it("seoulToday reads the date in Seoul, not the machine's", () => {
    // 2026-10-02 16:30 UTC is already 10-03 01:30 in Seoul; 15:00 UTC is exactly midnight there
    expect(seoulToday(new Date("2026-10-02T16:30:00Z"))).toBe("2026-10-03");
    expect(seoulToday(new Date("2026-10-02T14:59:00Z"))).toBe("2026-10-02");
    expect(seoulToday(new Date("2026-10-02T15:00:00Z"))).toBe("2026-10-03");
  });
});

describe("the reason line", () => {
  it("is absent when the panel is ready and names the chosen panel when it is not", () => {
    expect(paneReason("text", values({ text: "a" }), TODAY)).toBeNull();
    expect(paneReason("text", values(), TODAY)?.[0]).toContain("직접 입력");
    expect(paneReason("files", values(), TODAY)?.[0]).toContain("파일 선택");
    expect(paneReason("plan", values(), TODAY)?.[0]).toContain("계획 짜 주기");
    expect(paneReason("plan", values(), TODAY)?.[0]).toContain("위에서 고른");
  });

  it("has an English line for each", () => {
    for (const pane of ["text", "files", "plan"] as const) expect(paneReason(pane, values(), TODAY)?.[1]).toMatch(/[a-z]/);
  });
});

describe("a refused sending gives its highlight back", () => {
  it("plan → plan, files → files, otherwise the text", () => {
    expect(paneOfSending({ plan: { start_date: "2026-10-05" }, files: [] })).toBe("plan");
    expect(paneOfSending({ plan: null, files: [1] })).toBe("files");
    expect(paneOfSending({ plan: null, files: [] })).toBe("text");
  });
});
