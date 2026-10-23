import { describe, expect, it } from "vitest";
import { answerCard, answerLook, coveredLines, serverDayLabel, shownText, UNDO_SENTENCE } from "./chat-cards";
import { diffStops } from "./chat-diff";
import type { TripMessage, TripStop } from "./model";

const MAP = "https://www.google.com/maps/search/?api=1&query=%EA%B2%BD%EB%B3%B5%EA%B6%81+%EC%84%9C%EC%9A%B8";
const palace: TripStop = { id: "s1", date: "2026-10-24", time: "09:00", endTime: "11:00", title: "경복궁 관람", booking: "unknown", notes: "", kind: "activity", kindLabel: "활동",
  place: "경복궁", mapUrl: MAP, placeInfo: { address: "서울특별시 종로구 사직로 161", hours: [], hoursNotes: [], tags: [] } };
const lunch: TripStop = { id: "s2", date: "2026-10-24", time: "11:30", endTime: "12:30", title: "광장시장 점심", booking: "unknown", notes: "", kind: "dining", kindLabel: "식사", place: "광장시장" };
const walk: TripStop = { id: "s3", date: "2026-10-24", time: "14:00", endTime: "16:00", title: "북촌한옥마을 산책", booking: "unknown", notes: "", kind: "activity", kindLabel: "활동" };
const answer = (fields: Partial<TripMessage>): TripMessage => ({ id: "a", role: "assistant", text: "", createdAt: "2026-10-24T08:40:00+09:00", ...fields });

describe("`[2026-10-22 ST4F-719]` the chat answer card", () => {
  it("names the day as the server does — 「10월 24일(토)」, no zero padding", () => {
    expect(serverDayLabel("2026-10-24")).toBe("10월 24일(토)");
    expect(serverDayLabel("2026-10-04")).toBe("10월 4일(일)");
  });

  it("badges what the server did; an answer read back from the record (no status) has none", () => {
    expect(answerLook(answer({ status: "answered" }), false)).toEqual({ tone: "primary", kind: "answer" });
    expect(answerLook(answer({ status: "adjusted", changedTo: 8 }), false)?.kind).toBe("changed");
    expect(answerLook(answer({ status: "adjusted", changedTo: 8 }), true)?.kind).toBe("undone");
    expect(answerLook(answer({ status: "still_fits" }), false)?.kind).toBe("kept");
    expect(answerLook(answer({ status: "clarify", awaitingReply: true }), false)?.kind).toBe("waiting");
    expect(answerLook(answer({ status: "answered", needsLocation: true }), false)?.kind).toBe("location");
    expect(answerLook(answer({ status: "edit_refused", pick: { mode: "add", itemId: null, query: "익선동 카페", prefill: {}, blocked: false } }), false)?.kind).toBe("pick");
    expect(answerLook(answer({}), false)).toBeNull();
  });

  it("draws the stop the answer is about, the day of a summary, or what a change changed (this tab only)", () => {
    const trip = { stops: [palace, lunch, walk] };
    expect(answerCard(answer({ focusId: "s1" }), trip, {})).toEqual({ kind: "place", stop: palace });
    expect(answerCard(answer({ focusId: "gone" }), trip, {})).toBeNull();
    expect(answerCard(answer({ summaryDay: "2026-10-24" }), trip, {})).toEqual({ kind: "day", date: "2026-10-24", stops: [palace, lunch, walk] });
    const diff = { rows: [{ id: "s2", title: "광장시장 점심", before: "11:30~12:30", after: "12:00~13:00", kind: "time" as const, line: "· 10월 24일(토) 12:00~13:00 광장시장 점심" }], keep: [] };
    expect(answerCard(answer({ changedTo: 8 }), trip, { 8: diff })).toEqual({ kind: "diff", diff });
    expect(answerCard(answer({ changedTo: 8, focusId: "s2" }), trip, {})).toBeNull();          // another tab: the text only
  });

  it("leaves out the detail answer's lines the place card shows — only when they are the same to the letter", () => {
    // trip_facts._detail_answer (2026-10-22): header · 어디 · 지도 · 그날 영업 · 다음 일정
    const text = [`경복궁 관람 일정이에요 — 10월 24일(토) 09:00~11:00 · 활동`, `· 어디: 경복궁 · 서울특별시 종로구 사직로 161`, `· 지도: ${MAP}`, `· 그날 영업: 09:00~18:00 (입장·주문 마감 17:00)`,
      `· 다음 일정: 10월 24일(토) 11:30~12:30 광장시장 점심(식사)`].join("\n");
    const covered = coveredLines({ kind: "place", stop: palace });
    expect(shownText(text, covered, false)).toBe([`경복궁 관람 일정이에요 — 10월 24일(토) 09:00~11:00 · 활동`, `· 그날 영업: 09:00~18:00 (입장·주문 마감 17:00)`,
      `· 다음 일정: 10월 24일(토) 11:30~12:30 광장시장 점심(식사)`].join("\n"));
    // the server looked up another address (its own lookup) or wrote another map link: the lines stay
    const other = text.replace("사직로 161", "세종로 1-1").replace(MAP, `${MAP}%2C`);
    expect(shownText(other, covered, false)).toBe(other);
    // the address answer's map line
    expect(shownText(`경복궁 주소는 서울특별시 종로구 사직로 161이에요(출처 관광공사).\n지도에서 보기: ${MAP}`, covered, false)).toBe("경복궁 주소는 서울특별시 종로구 사직로 161이에요(출처 관광공사).");
  });

  it("leaves out a summary's stop lines the timeline shows, keeps its heading and the moves", () => {
    // trip_facts._day_answer: 「· {_stop_line}」 and 「   ↳ 이동: …」 (the move's mode is not in the trip view)
    const text = ["10월 24일(토) 일정은 3곳이에요.", "· 09:00~11:00 경복궁 관람(활동)", "   ↳ 이동: 11:00 출발 · 대중교통 · 약 20분", "· 11:30~12:30 광장시장 점심(식사)", "· 14:00~16:00 북촌한옥마을 산책(활동)"].join("\n");
    expect(shownText(text, coveredLines({ kind: "day", date: "2026-10-24", stops: [palace, lunch, walk] }), false))
      .toBe(["10월 24일(토) 일정은 3곳이에요.", "   ↳ 이동: 11:00 출발 · 대중교통 · 약 20분"].join("\n"));
    // a kind the server does not name keeps its own word ("flight"), a line of another title stays
    const flight: TripStop = { ...walk, id: "f", title: "제주행", kind: "flight", kindLabel: "항공" };
    expect(coveredLines({ kind: "day", date: "2026-10-24", stops: [flight] })).toEqual(new Set(["· 14:00~16:00 제주행(flight)"]));
  });

  it("leaves out a time change's new-time line the card shows, and the undo sentence only while the undo button is drawn", () => {
    // chat_edit.done_text (2026-10-22)
    const text = ["시각을 옮겼어요.", "· 10월 24일(토) 12:00~13:00 광장시장 점심", `변경한 일정과 확인 상태는 계획서에 반영했어요. ${UNDO_SENTENCE}`].join("\n");
    const after = { ...lunch, time: "12:00", endTime: "13:00" };
    const diff = diffStops([palace, lunch, walk], [palace, after, walk])!;
    expect(diff).toEqual({ rows: [{ id: "s2", title: "광장시장 점심", before: "11:30~12:30", after: "12:00~13:00", kind: "time", line: "· 10월 24일(토) 12:00~13:00 광장시장 점심" }],
      keep: [{ id: "s3", title: "북촌한옥마을 산책", time: "14:00~16:00" }] });
    const covered = coveredLines({ kind: "diff", diff });
    expect(shownText(text, covered, true)).toBe("시각을 옮겼어요.\n변경한 일정과 확인 상태는 계획서에 반영했어요.");
    expect(shownText(text, covered, false)).toBe(`시각을 옮겼어요.\n변경한 일정과 확인 상태는 계획서에 반영했어요. ${UNDO_SENTENCE}`);
  });

  it("compares the plan before and after: a stop replaced at the same time is one place change; nothing visible changed is no diff", () => {
    const other: TripStop = { ...lunch, id: "s9", title: "광장시장 점심", place: "부촌육회" };
    expect(diffStops([palace, lunch, walk], [palace, other, walk])?.rows).toEqual([{ id: "s9", title: "광장시장 점심", before: "광장시장", after: "부촌육회", kind: "place", line: "· 10월 24일(토) 11:30~12:30 광장시장 점심" }]);
    expect(diffStops([palace, lunch], [palace, { ...lunch, notes: "메모" }])).toBeNull();
  });
});
