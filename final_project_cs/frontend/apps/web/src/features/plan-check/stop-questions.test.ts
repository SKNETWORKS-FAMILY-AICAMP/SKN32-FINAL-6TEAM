import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import type { PlanAsk, PlanCandidate, PlanCheckView, PlanItem } from "./model";
import { arrivalQuestion, basisTag, interpretationQuestion, pickMyselfAnswer, placeQuestion, stopKindOf } from "./stop-questions";
import type { MoveOption, MoveOptions } from "@/lib/live/move-options";
import { exampleDone } from "./test-views";

// `[2026-10-20 사용자 결정 — 계획 확인 C안]` 검사가 멈춘 카드 안의 질문 — 서버 값(place_state · 휴무 줄 · prefill 질문 · 대안)으로 만들고 문장으로 가르지 않는다.
const t = translator("ko");
const stop = (fields: Partial<PlanItem>): PlanItem => ({ ...exampleDone.items[1], ...fields });
const plan = (item: PlanItem): PlanCheckView => ({ ...exampleDone, items: exampleDone.items.map((entry) => entry.id === item.id ? item : entry) });
const candidate = (name: string, fields: Partial<PlanCandidate> = {}): PlanCandidate => ({
  id: `cand-${name}`, name, source: "candidate", rank: 1, distance: { km: 0.6, from: "경복궁" }, coordinates: { lat: 37.57, lng: 126.98 }, info: null,
  checks: [{ kind: "hours", result: "ok", text: "10:00–17:00 안에 머물러요" }], reason: "같은 중분류(관광공사 분류)의 곳이에요",
  legs: { before: { with: "경복궁", minutes: 9, modeLabel: "도보", estimated: false, slackMin: 21 }, after: { with: "광장시장", minutes: 18, modeLabel: "지하철", estimated: false, slackMin: -3 } }, ...fields,
});

describe("the question asked at a card the check stopped at", () => {
  it("asks the server's own question for a place it could not find, with its candidates and 「장소 없이 두기」", () => {
    const item = stop({ unfound: { question: "「을지로 그 집」을 지도에서 찾지 못했어요 — 후보에서 고르거나 직접 골라 주세요", blocked: false } });
    const ask = placeQuestion(item, plan(item), [candidate("을지면옥")], t, "ko");
    expect(stopKindOf(item)).toBe("unfound");
    expect(ask).toMatchObject({ need: "fix", question: item.unfound!.question });
    expect(ask.options.map((option) => option.label)).toEqual(["「을지면옥」으로 정하기", "장소 없이 두기"]);
    expect(ask.options[0].reason).toBe("같은 중분류(관광공사 분류)의 곳이에요 · 경복궁에서 0.6km · 10:00–17:00 안에 머물러요");
    expect(ask.options[0].effect).toBe("바뀐 장소와 앞뒤 이동을 다시 확인해요");
    expect(ask.options[1]).toMatchObject({ reason: null, effect: "앞뒤 이동은 장소가 정해지면 확인해요", act: { type: "noplace" } });
  });

  // `[2026-10-21 사용자 지적]` 「호텔 조식」: 서버는 같은 숙소를 묵을 곳 · 그 안 식사로 두 번 준다 — 바꾸기 화면과 같은 꼬리표로 가른다
  it("tags each alternative with the step the server took it from, so a stay and a meal at it are told apart", () => {
    const item = stop({ title: "호텔 조식", checks: [{ kind: "place", result: "bad", text: "숙소를 정해야 해요" }] });
    const ask = placeQuestion(item, plan(item), [candidate("호텔 더 디자이너스 종로점", { basis: "lodging" }), candidate("호텔 더 디자이너스 종로점", { id: "cand-meal", basis: "lodging_meal" }), candidate("롯데시티호텔 명동")], t, "ko");
    expect(ask.options.map((option) => option.tag?.text ?? null)).toEqual(["숙소", "숙소 안 식사", null]);
  });

  it("says the closed day for a stop on its day off", () => {
    const item = stop({ title: "창덕궁 관람", date: "2026-10-26", checks: [{ kind: "closed", result: "bad", text: "월요일 휴궁" }] });
    const ask = placeQuestion(item, plan(item), [candidate("북촌한옥마을")], t, "ko");
    expect(stopKindOf(item)).toBe("closed");
    expect(ask.question).toBe("「창덕궁 관람」은 10.26(월) 쉬는 날이에요. 어떻게 할까요?");
    expect(ask.options.map((option) => option.label)).toEqual(["「북촌한옥마을」로 바꾸기"]);
  });

  it("asks whether the place taken for now (one of several) is the one, keeping it first", () => {
    const item = stop({ title: "광화문 근처 한식", place: "두레에프엔씨", placeState: "picked_nearest", placeChoices: 10, coordinates: { lat: 37.5715, lng: 126.9768 }, checks: [] });
    const ask = placeQuestion(item, plan(item), [candidate("광화문미진 본점")], t, "ko");
    expect(stopKindOf(item)).toBe("nearest");
    expect(ask.need).toBe("confirm");
    expect(ask.question).toBe("「광화문 근처 한식」은 맞는 곳이 10곳이라 가까운 「두레에프엔씨」로 임시로 골랐어요. 어디로 갈까요?");
    expect(ask.options.map((option) => option.label)).toEqual(["「두레에프엔씨」 그대로", "「광화문미진 본점」으로 바꾸기"]);
    expect(ask.options[0]).toMatchObject({ effect: "「두레에프엔씨」로 확정하고 다시 확인해요", act: { type: "confirm" } });
    expect(ask.options[0].reason).toMatch(/^앞뒤 일정에서 평균 \d+m$/);
  });

  it("does not offer to keep a place that has no position", () => {
    const item = stop({ place: "올리브영", placeState: "picked_nearest", placeChoices: null, coordinates: null, checks: [] });
    const ask = placeQuestion(item, plan(item), [], t, "ko");
    expect(ask.question).toBe("「올리브영」은 이름이 여러 곳이라 가까운 「올리브영」으로 임시로 골랐어요. 어디로 갈까요?");
    expect(ask.options).toEqual([]);
  });

  it("says the server's first red or amber line for anything else", () => {
    const ask = placeQuestion(exampleDone.items[1], exampleDone, [], t, "ko");
    expect(stopKindOf(exampleDone.items[1])).toBe("other");
    expect(ask.question).toBe("「올리브영」은 확인이 필요해요 — 지점이 여러 곳이라 정하지 못했어요. 어떻게 할까요?");
  });

  it("shows at most three alternatives", () => {
    const ask = placeQuestion(exampleDone.items[1], exampleDone, ["가", "나", "다", "라"].map((name) => candidate(name)), t, "ko");
    expect(ask.options).toHaveLength(3);
  });
});

describe("`[2026-10-20 이동 확인 C안]` the question asked when the way into the card arrives late", () => {
  const move = { ...exampleDone.moves[0], slackMin: -42 };
  const way = (fields: Partial<MoveOption>): MoveOption => ({ mode: "taxi", label: "택시", minutes: 7, km: 0.8, fareKrw: 6800, fareIsFloor: false, fareIsEstimate: true,
    depart: "11:30", arrive: "11:37", slackMin: -37, fits: false, whyNot: null, basis: "estimate", grade: "추정", ...fields });
  const ways = (option: MoveOption): MoveOptions => ({ revision: 1, currentMode: "walk", recommendedMode: "walk", options: [option] });

  it("says the leg and how late, and offers a taxi with its time, spare and fare, and the later start", () => {
    const ask = arrivalQuestion(exampleDone.items[1], move, exampleDone.items[0], ways(way({ slackMin: 4, fits: true })), { start: "12:15", end: "13:00" }, t);
    expect(ask).toMatchObject({ need: "fix", question: "「경복궁 → 올리브영」 이동이 일정보다 42분 늦어요. 어떻게 할까요?" });
    expect(ask.options.map((option) => option.label)).toEqual(["택시로 바꾸기", "「올리브영」 12:15 시작으로 늦추기"]);
    expect(ask.options[0]).toMatchObject({ reason: "택시 7분 · 4분 여유 · 예상 6,800원", effect: "이 구간만 다시 계산해요", why: null, act: { type: "taxi", moveId: "a-b" } });
    expect(ask.options[1]).toMatchObject({ reason: null, effect: "시작 시각을 바꾸고 뒤 일정과 이동을 다시 확인해요", act: { type: "later", start: "12:15", end: "13:00" } });
  });

  it("greys a taxi that does not reach, with the server's reason (or the travel box's own words)", () => {
    expect(arrivalQuestion(exampleDone.items[1], move, exampleDone.items[0], ways(way({ whyNot: "택시로도 5분 늦어요" })), null, t).options[0].why).toBe("택시로도 5분 늦어요");
    expect(arrivalQuestion(exampleDone.items[1], move, exampleDone.items[0], ways(way({})), null, t).options[0].why).toBe("다음 일정 시작 안에 닿지 않아요");
    expect(arrivalQuestion(exampleDone.items[1], move, exampleDone.items[0], ways(way({ fits: null })), null, t).options[0].why).toBe("계산이 오래 걸려 확인하지 못했어요");
  });

  it("offers nothing it was not given (no ways, no later start): 「직접 수정」 is left", () => {
    expect(arrivalQuestion(exampleDone.items[1], move, exampleDone.items[0], null, null, t).options).toEqual([]);
  });
});

describe("`[2026-10-21 사용자 결정 — P6]` the question of what a line of the plan means", () => {
  const ask: PlanAsk = { id: "q-0-5", itemId: "0-3", day: 1, date: "2026-10-01", startsAt: "14:00", title: "정도", question: "계획서의 「14시~16시 정도 시간이 비는데」를 어떻게 이해할까요?", quote: "14시~16시 정도 시간이 비는데",
    options: [
      { id: "reading", label: "14:00~16:00 빈 시간", recommended: true, reason: "읽기 AI 가 「14시~16시 정도 시간이 비는데」를 빈 시간으로 읽었어요", effect: "일정에 넣지 않고 14:00~16:00 빈 시간으로 둬요", pickMyself: false, query: null },
      { id: "item", label: "「정돈 대학로본점」 14:00 일정(「정도」을 오타로 볼 때)", recommended: false, reason: null, effect: "14:00 일정으로 넣고 영업시간 · 이동을 확인해요", pickMyself: false, query: null },
      { id: "item_search", label: "「정도」 이름 그대로 찾기", recommended: false, reason: null, effect: "14:00 일정으로 넣고 「정도」을 장소 검색에서 직접 골라요", pickMyself: true, query: "정도" },
    ] };

  it("asks the server's question with its options as they are, in its order — the first marked as recommended", () => {
    const asked = interpretationQuestion(ask);
    expect(asked.question).toBe(ask.question);
    expect(asked.options.map((option) => [option.label, option.reason, option.effect, option.recommended])).toEqual(ask.options.map((option) => [option.label, option.reason, option.effect, option.recommended]));
    expect(asked.options.map((option) => option.act)).toEqual([
      { type: "interpret", option: "reading", search: null }, { type: "interpret", option: "item", search: null }, { type: "interpret", option: "item_search", search: "정도" }]);
  });

  it("「직접 선택」 puts the stop in with the option that lets the customer pick its place, else the stop's own option — searched by the words either way", () => {
    expect(pickMyselfAnswer(ask)).toEqual({ option: "item_search", search: "정도" });
    expect(pickMyselfAnswer({ ...ask, options: ask.options.slice(0, 2) })).toEqual({ option: "item", search: "정도" });
    expect(pickMyselfAnswer({ ...ask, options: ask.options.slice(0, 1) })).toBeNull();
  });
});

describe("`[2026-10-21]` the tag of an alternative's step", () => {
  it("says the same words as the change screen, and none for a step it does not know", () => {
    expect([basisTag("lodging", t), basisTag("lodging_meal", t), basisTag("same_kind", t), basisTag(null, t)]).toEqual(["숙소", "숙소 안 식사", "같은 종류", null]);
  });
});
