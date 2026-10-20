import { describe, expect, it } from "vitest";
import type { IntakeQuestion } from "@/lib/live/intake";
import {
  allAnswered, complete, CUSTOM, draftOf, EMPTY_DRAFT, nextOpen, openIndexes, payloadOf, pickArea, pickChoice, pickDetail, pickPart, pickSize, questionsOf, sizeOf, startAnswers,
  unanswered, type PairQuestion, type PriorityQuestion, type SingleQuestion,
} from "./model";

// The server's four loading questions as `GET /v1/web/trip-intakes/{id}` sends them (`survey_answers.questions`, question set "3").
const INDOOR = [{ id: "indoor", label: "실내" }, { id: "outdoor", label: "실외" }, { id: "any", label: "상관없음" }];
const party: IntakeQuestion = {
  id: "party", kind: "single", title: "누구와 함께 떠나나요?", why: "함께 떠나는 사람을 하나 골라 주세요.",
  options: [{ id: "alone", label: "혼자" }, { id: "partner", label: "연인" }, { id: "friends", label: "친구" }, { id: "family", label: "가족" }],
  allow_custom: true, custom_max_length: 1000, custom_label: "기타", answer: null, custom_answer: null,
};
const priority: IntakeQuestion = {
  id: "priority", kind: "priority", title: "어떤 것을 더 중요하게 생각하나요?", why: "중요한 순서대로 분야와 세부 항목을 선택해 주세요.",
  options: [{ id: "food", label: "음식" }, { id: "activity", label: "활동" }, { id: "mobility", label: "이동" }],
  groups: [
    { id: "food", label: "음식", read: null, options: [{ id: "taste", label: "맛" }, { id: "kindness", label: "친절" }, { id: "clean", label: "청결" }, { id: "michelin", label: "미쉐린" }, { id: "nopo", label: "노포" }] },
    { id: "activity", label: "활동", read: null, options: [["EV", "축제/공연/행사"], ["EX", "체험관광"], ["HS", "역사관광"], ["LS", "레저스포츠"], ["NA", "자연관광"], ["SH", "쇼핑"], ["VE", "문화관광"]].map(([id, label]) => ({ id, label })) },
    { id: "mobility", label: "이동", read: { key: "survey.priority_details.mobility", value: ["taxi"], text: "택시", quotes: ["웬만하면 택시로"] },
      options: [{ id: "public", label: "대중교통" }, { id: "walk", label: "도보" }, { id: "car", label: "렌트카" }, { id: "taxi", label: "택시" }] },
  ],
  answer: null,
};
const indoorOutdoor: IntakeQuestion = {
  id: "indoor_outdoor", kind: "pair", title: "실내와 실외 중 어디가 좋으세요?", why: "식당과 액티비티에서 각각 하나씩 골라 주세요.",
  parts: [{ id: "dining", label: "식당", options: INDOOR, read: null }, { id: "activity", label: "액티비티", options: INDOOR, read: { key: "survey.indoor_outdoor.activity", value: "indoor", text: "실내", quotes: ["비 오면 실내"] } }],
  answer: null,
};
const pace: IntakeQuestion = {
  id: "pace", kind: "single", title: "여행할 때 어느 정도 여유가 좋으세요?", why: "하루에 담을 일정의 양을 정할 때 쓰여요.",
  options: [{ id: "relaxed", label: "여유롭게" }, { id: "moderate", label: "적당히" }, { id: "packed", label: "꽉 차게" }], allow_custom: false, custom_label: null, answer: null,
};

const drawn = () => questionsOf([party, priority, indoorOutdoor, pace], "ko");
const [Party, Priority, Pair] = drawn() as [SingleQuestion, PriorityQuestion, PairQuestion, SingleQuestion];

describe("the questions the page draws", () => {
  it("draws the three kinds the server sends, in its order, with the parts the plan told", () => {
    const questions = drawn();
    expect(questions.map((question) => [question.id, question.kind])).toEqual([["party", "single"], ["priority", "priority"], ["indoor_outdoor", "pair"], ["pace", "single"]]);
    expect(Party).toMatchObject({ allowCustom: true, customLabel: "기타", answer: null });
    expect(Priority.groups.map((group) => [group.id, group.read?.text ?? null])).toEqual([["food", null], ["activity", null], ["mobility", "택시"]]);
    expect(Priority.groups[2].read?.quotes).toEqual(["웬만하면 택시로"]);
    expect(Pair.parts.map((part) => [part.id, Boolean(part.read)])).toEqual([["dining", false], ["activity", true]]);
  });

  it("reads the answers the server holds, of every kind, and keeps an unknown one out", () => {
    const [p, r, i, q] = questionsOf([
      { ...party, custom_answer: "직장 동료" },
      { ...priority, answer: { areas: ["activity", "food"], details: { activity: ["HS", "NA", "VE"], food: ["nopo", "zzz"], mobility: ["taxi"] } } },
      { ...indoorOutdoor, answer: { dining: "indoor", activity: "sky" } },
      { ...pace, answer: "slow" },
    ], "ko");
    expect(p.answer).toBe("custom:직장 동료");
    expect(r.answer).toEqual({ areas: ["activity", "food"], details: { activity: ["HS", "NA", "VE"], food: ["nopo"] } });
    expect(i.answer).toEqual({ dining: "indoor" });
    expect(q.answer).toBeNull();
  });

  it("leaves out only the question it cannot draw", () => {
    const bad: unknown[] = [
      { ...pace, id: "a", kind: "multi" },
      { ...pace, id: "b", title: "" },
      { ...pace, id: "c", options: [] },
      { ...priority, id: "d", groups: (priority.groups ?? []).slice(0, 2) },                       // an area without its details
      { ...indoorOutdoor, id: "e", parts: (indoorOutdoor.parts ?? []).map((part) => ({ ...part, read: { key: "k", value: "indoor", text: "실내", quotes: [] } })) }, // nothing left to ask
      { ...pace, id: "party" },                                                                   // a repeated id
      null, "text", 3,
    ];
    expect(questionsOf([party, ...(bad as IntakeQuestion[]), pace], "ko").map((question) => question.id)).toEqual(["party", "pace"]);
    expect(questionsOf(undefined, "ko")).toEqual([]);
    expect(questionsOf(null, "ko")).toEqual([]);
  });

  it("speaks the start survey's English for the ids it knows, and leaves an id it does not know in the server's words", () => {
    const [p, r, i, q, other] = questionsOf([party, priority, indoorOutdoor, pace, { ...pace, id: "future_question", options: [{ id: "x", label: "엑스" }] }], "en") as
      [SingleQuestion, PriorityQuestion, PairQuestion, SingleQuestion, SingleQuestion];
    expect(p.title).toBe("Who’s coming along?");
    expect([...p.options.map((option) => option.label), p.customLabel]).toEqual(["Solo", "Partner", "Friends", "Family", "Other"]);
    expect(r.options.map((option) => option.label)).toEqual(["Food", "Activities", "Getting around"]);
    expect(r.groups[1].options.map((option) => option.label)).toEqual(["Festivals/Performances/Events", "Hands-on experiences", "History", "Leisure sports", "Nature", "Shopping", "Culture"]);
    expect(i.parts.map((part) => part.label)).toEqual(["Dining", "Activities"]);
    expect(i.parts[0].options.map((option) => option.label)).toEqual(["Indoors", "Outdoors", "Either is fine"]);
    expect(q.why).toBe("We use this to decide how much to fit into each day.");
    expect(other.title).toBe("여행할 때 어느 정도 여유가 좋으세요?");
    expect(other.options[0].label).toBe("엑스");
  });
});

describe("the card being answered — the start survey's rules", () => {
  it("asks how many travel under the companions: 혼자 · 연인 set it, 친구 · 가족 start at 2, 기타 needs its words and a size", () => {
    expect(sizeOf(pickChoice(EMPTY_DRAFT, "alone"))).toBe(1);
    expect(sizeOf(pickChoice(EMPTY_DRAFT, "partner"))).toBe(2);
    const friends = pickChoice(EMPTY_DRAFT, "friends");
    expect(sizeOf(friends)).toBe(2);
    expect(sizeOf(pickSize(friends, 1))).toBe(2);                          // 1 is not offered to friends
    expect(sizeOf(pickSize(friends, 4))).toBe(4);
    expect(complete(Party, friends)).toBe(true);
    const other = pickChoice(EMPTY_DRAFT, CUSTOM);
    expect(complete(Party, other)).toBe(false);
    expect(complete(Party, { ...other, custom: "직장 동료" })).toBe(false); // no size yet
    expect(complete(Party, pickSize({ ...other, custom: "직장 동료" }, 3))).toBe(true);
    expect(complete(Party, pickChoice(friends, "friends"))).toBe(false);     // tapped again: un-picked
  });

  it("sends the companions with how many travel, in one call", () => {
    expect(payloadOf(Party, pickSize(pickChoice(EMPTY_DRAFT, "family"), 3))).toEqual({ answers: { party: "family", party_size: "3" }, value: "family" });
    expect(payloadOf(Party, pickChoice(EMPTY_DRAFT, "alone")).answers).toEqual({ party: "alone", party_size: "1" });
    expect(payloadOf(Party, pickSize({ ...pickChoice(EMPTY_DRAFT, CUSTOM), custom: " 직장 동료 " }, 2))).toEqual({ answers: { party: { custom: "직장 동료" }, party_size: "2" }, value: "custom:직장 동료" });
    expect(payloadOf(drawn()[3], pickChoice(EMPTY_DRAFT, "packed"))).toEqual({ answers: { pace: "packed" }, value: "packed" });
  });

  it("ranks areas and details in tapping order; activities take exactly three; a part the plan told needs nothing and is not sent", () => {
    let draft = pickArea(pickArea(EMPTY_DRAFT, "activity"), "mobility");
    for (const code of ["NA", "HS"]) draft = pickDetail(Priority, draft, "activity", code);
    expect(complete(Priority, draft)).toBe(false);
    draft = pickDetail(Priority, draft, "activity", "VE");
    expect(pickDetail(Priority, draft, "activity", "SH")).toBe(draft);       // full: a fourth waits
    expect(complete(Priority, draft)).toBe(true);                            // mobility's details were read from the plan
    expect(payloadOf(Priority, draft).answers).toEqual({ priority: { areas: ["activity", "mobility"], details: { activity: ["NA", "HS", "VE"] } } });
    const food = pickArea(draft, "food");
    expect(complete(Priority, food)).toBe(false);                             // food needs one or more
    expect(complete(Priority, pickDetail(Priority, food, "food", "nopo"))).toBe(true);
    const dropped = pickArea(draft, "activity");
    expect(dropped).toMatchObject({ areas: ["mobility"], details: { activity: [] } });
  });

  it("asks one pick per part the plan did not tell", () => {
    expect(complete(Pair, EMPTY_DRAFT)).toBe(false);
    const dining = pickPart(EMPTY_DRAFT, "dining", "outdoor");
    expect(complete(Pair, dining)).toBe(true);
    expect(payloadOf(Pair, dining)).toEqual({ answers: { indoor_outdoor: { dining: "outdoor" } }, value: { dining: "outdoor" } });
    expect(complete(Pair, pickPart(dining, "dining", "outdoor"))).toBe(false); // tapped again: un-picked
  });

  it("starts from the answer held", () => {
    expect(draftOf(Party, "custom:직장 동료")).toMatchObject({ choice: CUSTOM, custom: "직장 동료" });
    expect(draftOf(Priority, { areas: ["food"], details: { food: ["taste"] } })).toMatchObject({ areas: ["food"], details: { food: ["taste"] } });
    expect(draftOf(Pair, { dining: "any" }).parts).toEqual({ dining: "any" });
    expect(draftOf(Pair, null)).toBe(EMPTY_DRAFT);
  });
});

describe("the start survey's answers laid on the intake", () => {
  it("turns the registration's survey into the loading questions' answers — not the Course Keeper's choice", () => {
    expect(startAnswers({
      version: "2026-09-24.v1", party: "friends", party_size: 3, priority: ["activity", "food"], priority_details: { activity: ["EV", "EX", "HS"], food: ["clean"] },
      indoor_outdoor: { dining: "indoor", activity: "any" }, pace: "relaxed", on_disruption: "replace",
    })).toEqual({
      party: "friends", party_size: "3", priority: { areas: ["activity", "food"], details: { activity: ["EV", "EX", "HS"], food: ["clean"] } },
      indoor_outdoor: { dining: "indoor", activity: "any" }, pace: "relaxed",
    });
  });

  it("sends 기타's words as words, and only what was answered", () => {
    expect(startAnswers({ version: "2026-09-24.v1", party: "직장 동료", party_size: 2 })).toEqual({ party: { custom: "직장 동료" }, party_size: "2" });
    expect(startAnswers({ version: "2026-09-24.v1", pace: "moderate", on_disruption: "ask_first" })).toEqual({ pace: "moderate" });
    expect(startAnswers(undefined)).toEqual({});
  });
});

describe("what is left to ask", () => {
  const questions = questionsOf([pace, { ...party, answer: "alone" }, { ...pace, id: "third" }], "ko");        // party already answered by the server

  it("lists the open ones: not answered and not skipped; a saved answer counts", () => {
    expect(openIndexes(questions, {}, new Set())).toEqual([0, 2]);
    expect(openIndexes(questions, { pace: "packed" }, new Set())).toEqual([2]);
    expect(openIndexes(questions, {}, new Set(["third"]))).toEqual([0]);
    expect(openIndexes(questions, { party: null }, new Set())).toEqual([0, 1, 2]);                        // taken back
    expect(unanswered(questions, {})).toBe(2);
    expect(unanswered(questions, { pace: "packed", third: "relaxed" })).toBe(0);
  });

  it("is all answered only when every question has an answer and there is something to ask", () => {
    expect(allAnswered(questions, { pace: "packed", third: "relaxed" })).toBe(true);
    expect(allAnswered(questions, { pace: "packed" })).toBe(false);
    expect(allAnswered([], {})).toBe(false);
  });

  it("goes to the next open one after the answered one, else the first open one before it, else nowhere", () => {
    expect(nextOpen([0, 2], 0)).toBe(2);
    expect(nextOpen([0, 2], 2)).toBe(0);
    expect(nextOpen([0, 1, 3], 1)).toBe(3);
    expect(nextOpen([1], 1)).toBeNull();
    expect(nextOpen([], 0)).toBeNull();
  });
});
