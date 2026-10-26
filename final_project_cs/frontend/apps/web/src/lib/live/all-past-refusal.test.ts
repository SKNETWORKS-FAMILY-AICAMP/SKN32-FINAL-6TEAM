import { describe, expect, it } from "vitest";
import { LiveError, refusal } from "./client";
import { ALL_PAST_TEXT, checkLineText, REFUSAL_TEXT, refusalSentence } from "./error-text";
import { translator } from "../i18n";

// `[2026-10-26]` 신규 계획의 모든 일정이 오늘 이전 — 서버(d2ab93a65 `trip_api`)의 등록 거절이 화면 언어로 어떻게 읽히는지.
const SERVER = "모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요";
const ENGLISH = "Every stop is before today. Please check the trip dates.";
/** The body the server sends (`_error(422, "itinerary_infeasible", …, violations=[…])`, unwrapped by `install_error_handlers`). */
const allPastBody = () => ({ error: { code: "itinerary_infeasible", message: SERVER,
  violations: [{ code: "all_dates_in_past", items: [1, 2], reason: SERVER, remedy: "여행 날짜를 확인해주세요" }] } });
const answer = (body: unknown, status = 422) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("a registration refused because every stop is before today", () => {
  it("keeps the server's Korean sentence as it is on the Korean screen", async () => {
    const error = await refusal(answer(allPastBody()), "ko");
    expect(error).toBeInstanceOf(LiveError);
    expect(error).toMatchObject({ code: "itinerary_infeasible", message: SERVER, status: 422 });
    // The server's words and the violation stay in `detail` for the screen.
    expect(error.detail).toMatchObject({ message: SERVER, violations: [{ code: "all_dates_in_past" }] });
  });

  it("says it in English on the English screen instead of the general 「could not be completed」 sentence", async () => {
    const error = await refusal(answer(allPastBody()), "en");
    expect(error.message).toBe(ENGLISH);
    expect(error.message).not.toContain("itinerary_infeasible");
    expect(error.message).not.toContain(SERVER);
  });

  it("uses the server's sentence word for word for Korean when only the code and violation came", () => {
    const detail = { violations: [{ code: "all_dates_in_past" }] };
    expect(refusalSentence("itinerary_infeasible", undefined, detail, "ko")).toBe(SERVER);
    expect(ALL_PAST_TEXT[0]).toBe(SERVER);
  });

  it("gives another unworkable plan its own general sentence, not the all-past one", () => {
    const detail = { violations: [{ code: "closed_day", reason: "휴무일이다" }] };
    expect(refusalSentence("itinerary_infeasible", "이 일정은 그대로 수행할 수 없습니다: 휴무일이다", detail, "en"))
      .toBe("This plan can't go ahead as it is. Please fix the stops that don't work.");
    expect(refusalSentence("itinerary_infeasible", undefined, undefined, "ko")).toBe("이 일정은 그대로 진행할 수 없어요. 문제가 된 일정을 고쳐 주세요.");
    expect(refusalSentence("itinerary_infeasible", undefined, { violations: "all_dates_in_past" }, "en")).not.toBe(ENGLISH);
  });

  it("has the code in the sentence table, both readings polite", () => {
    const text = REFUSAL_TEXT.itinerary_infeasible;
    expect(typeof text).toBe("function");
    for (const detail of [allPastBody().error, undefined]) {
      const [ko, en] = (text as (detail: Record<string, unknown> | undefined) => readonly [string, string])(detail);
      expect(ko).toMatch(/(요|니다)[.!?]?$/);
      expect(en.length).toBeGreaterThan(5);
    }
  });
});

describe("the review's all-past date line, in the screen's language", () => {
  it("is the server's sentence on the Korean screen and the web's on the English one", () => {
    expect(checkLineText({ kind: "date", text: SERVER }, translator("ko"))).toBe(SERVER);
    expect(checkLineText({ kind: "date", text: SERVER }, translator("en"))).toBe(ENGLISH);
    // A closing full stop or spacing the server may add does not change which sentence it is.
    expect(checkLineText({ kind: "date", text: `${SERVER}.` }, translator("en"))).toBe(ENGLISH);
  });

  it("leaves a line it has no words for as the server wrote it", () => {
    expect(checkLineText({ kind: "date", text: "날짜가 비어 있어요" }, translator("en"))).toBe("날짜가 비어 있어요");
    expect(checkLineText({ kind: "place", text: SERVER }, translator("en"))).toBe(SERVER);
  });
});
