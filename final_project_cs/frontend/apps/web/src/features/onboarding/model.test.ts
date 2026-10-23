import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import {
  ACTIVITY_PICKS, answeredCount, answerLines, canPickPartySize, discordWebhookProblem, done, initialAnswers, PARTY_SIZES, partyLabel, partySizeOf, pickPartySize, priorityLines, questions,
  skip, toggle, toggleArea, toggleDetail, unskip, valid, type Answers,
} from "./model";

const ko = translator("ko");
/** Every question answered, with a picked "other" draft kept aside. */
const full: Answers = {
  ...initialAnswers, party: "family", partyOther: "직장 동료", partySize: 3, priority: ["food", "mobility"],
  details: { food: ["clean", "taste"], activity: [], mobility: ["taxi"] }, indoorDining: "indoor", indoorActivity: "any", pace: "relaxed",
};

describe("onboarding preferences", () => {
  it("asks four questions in order, without the theme, plan-change, transport or nationality question", () => {
    expect(questions.map((question) => question.id)).toEqual(["party", "priority", "indoor", "pace"]);
    for (const title of ["어떤 여행을 좋아하세요?", "일정에 문제가 생기면 어떻게 할까요?", "어떻게 이동하고 싶나요?", "한국 국적이신가요?"]) {
      expect(questions.map((question) => question.title[0])).not.toContain(title);
    }
    expect(questions[1].title[0]).toBe("어떤 것을 더 중요하게 생각하나요?");
    expect(questions[1].helper[0]).toBe("중요한 순서대로 분야와 세부 항목을 선택해 주세요.");
    expect(questions.every((_, index) => valid(index, full))).toBe(true);
  });

  it("skipping one question clears only its own fields, whichever position it has", () => {
    questions.forEach((question, index) => {
      const skipped = skip(full, index);
      for (const field of Object.keys(full) as (keyof Answers)[]) {
        if (field === "skipped") continue;
        if (question.fields.includes(field)) expect(skipped[field], `${question.id}.${field}`).toEqual(initialAnswers[field]);
        else expect(skipped[field], `${question.id} must keep ${field}`).toEqual(full[field]);
      }
      expect(valid(index, skipped)).toBe(false);
      expect(done(index, skipped)).toBe(true);
      expect(answeredCount(skipped)).toBe(questions.length);
    });
    expect(answeredCount(unskip(skip(initialAnswers, 3), 3))).toBe(0);
  });

  it("companions: `other` needs typed words (not spaces); another choice hides it but keeps the draft; skipping clears both", () => {
    const other = pickPartySize(toggle(initialAnswers, "party", "other"), 3);
    expect(valid(0, other)).toBe(false);
    expect(valid(0, { ...other, partyOther: "   " })).toBe(false);
    const typed = { ...other, partyOther: "  직장 동료 " };
    expect(valid(0, typed)).toBe(true);
    expect(partyLabel(typed, ko)).toBe("직장 동료");
    const family = toggle(typed, "party", "family");
    expect(valid(0, family)).toBe(true);
    expect(partyLabel(family, ko)).toBe("가족");
    expect(toggle(family, "party", "other").partyOther).toBe("  직장 동료 ");
    expect(skip(typed, 0)).toMatchObject({ party: "", partyOther: "", partySize: null });
  });

  it("companions' size: 혼자 · 연인 set 1 · 2; 친구 · 가족 start at 2 and never take 1; 기타 needs one of 1–4 picked", () => {
    expect(PARTY_SIZES).toEqual([1, 2, 3, 4]);
    expect(partySizeOf(initialAnswers)).toBeNull();
    for (const [party, size] of [["alone", 1], ["partner", 2]] as const) {
      const a = toggle(initialAnswers, "party", party);
      expect(partySizeOf(a), party).toBe(size);
      expect(valid(0, a), party).toBe(true);
      expect(PARTY_SIZES.filter((n) => canPickPartySize(party, n)), party).toEqual([]);
      // A size picked for another choice does not change the set one.
      expect(partySizeOf({ ...a, partySize: 4 }), party).toBe(size);
    }
    for (const party of ["friends", "family"]) {
      const a = toggle(initialAnswers, "party", party);
      expect(partySizeOf(a), party).toBe(2);
      expect(a.partySize, `${party}: the start of 2 is not stored as picked`).toBeNull();
      expect(valid(0, a), party).toBe(true);
      expect(PARTY_SIZES.filter((n) => canPickPartySize(party, n)), party).toEqual([2, 3, 4]);
      expect(partySizeOf(pickPartySize(a, 4)), party).toBe(4);
    }
    const other = toggle(initialAnswers, "party", "other");
    expect(partySizeOf(other)).toBeNull();
    expect(PARTY_SIZES.filter((n) => canPickPartySize("other", n))).toEqual([1, 2, 3, 4]);
    expect(partySizeOf(pickPartySize(other, 1))).toBe(1);
  });

  it("companions' size: tapping the picked size keeps it; a size kept from another choice counts only where it can be picked", () => {
    const three = pickPartySize(toggle(initialAnswers, "party", "friends"), 3);
    expect(pickPartySize(three, 3).partySize).toBe(3);
    const alone = toggle(three, "party", "alone");
    expect(partySizeOf(alone)).toBe(1);
    expect(partySizeOf(toggle(alone, "party", "family"))).toBe(3);
    expect(partySizeOf(toggle(three, "party", "friends"))).toBeNull();
    // 기타 with 1, then 친구: 1 is not offered there, so it starts at 2; back on 기타 the 1 is still there.
    const one = pickPartySize(toggle(initialAnswers, "party", "other"), 1);
    const friends = toggle(one, "party", "friends");
    expect(partySizeOf(friends)).toBe(2);
    expect(partySizeOf(toggle(friends, "party", "other"))).toBe(1);
  });

  it("areas rank in tapping order; un-picking pulls the ones behind up and clears its details; picking again goes last", () => {
    let a = toggleArea(toggleArea(toggleArea(initialAnswers, "food"), "mobility"), "activity");
    expect(a.priority).toEqual(["food", "mobility", "activity"]);
    a = toggleDetail(toggleDetail(a, "mobility", "taxi"), "mobility", "public");
    a = toggleDetail(a, "food", "clean");
    a = toggleArea(a, "mobility");
    expect(a.priority).toEqual(["food", "activity"]);
    expect(a.details).toEqual({ food: ["clean"], activity: [], mobility: [] });
    expect(toggleArea(a, "mobility").priority).toEqual(["food", "activity", "mobility"]);
  });

  it("details rank per area the same way and never change the area pick", () => {
    let a = toggleArea(toggleArea(initialAnswers, "food"), "activity");
    a = toggleDetail(toggleDetail(toggleDetail(a, "food", "taste"), "food", "kindness"), "food", "clean");
    a = toggleDetail(a, "activity", "HS");
    expect(a.details.food).toEqual(["taste", "kindness", "clean"]);
    a = toggleDetail(a, "food", "taste");
    expect(a.details.food).toEqual(["kindness", "clean"]);
    expect(toggleDetail(a, "food", "taste").details.food).toEqual(["kindness", "clean", "taste"]);
    expect(a.details.activity).toEqual(["HS"]);
    expect(a.priority).toEqual(["food", "activity"]);
  });

  it("priorities are answered with at least one area and at least one detail in every picked area", () => {
    const food = toggleArea(initialAnswers, "food");
    expect(valid(1, initialAnswers)).toBe(false);
    expect(valid(1, food)).toBe(false);
    expect(valid(1, toggleDetail(food, "food", "taste"))).toBe(true);
    const both = toggleArea(toggleDetail(food, "food", "taste"), "mobility");
    expect(valid(1, both)).toBe(false);
    expect(valid(1, toggleDetail(both, "mobility", "car"))).toBe(true);
    expect(skip(both, 1)).toMatchObject({ priority: [], details: { food: [], activity: [], mobility: [] } });
  });

  it("a picked activity area needs exactly three of the seven tourism classes, ranked in tapping order; a fourth is not taken", () => {
    expect(ACTIVITY_PICKS).toBe(3);
    let a = toggleArea(initialAnswers, "activity");
    for (const [value, ok] of [["NA", false], ["EV", false], ["HS", true]] as const) {
      a = toggleDetail(a, "activity", value);
      expect(valid(1, a), value).toBe(ok);
    }
    expect(toggleDetail(a, "activity", "SH")).toBe(a);
    a = toggleDetail(toggleDetail(a, "activity", "EV"), "activity", "SH");
    expect(a.details.activity).toEqual(["NA", "HS", "SH"]);
    expect(valid(1, a)).toBe(true);
  });

  it("the summary lines follow the picking order and name mobility's four details", () => {
    let a = toggleArea(toggleArea(initialAnswers, "mobility"), "food");
    for (const value of ["taxi", "public", "walk", "car"]) a = toggleDetail(a, "mobility", value);
    a = toggleDetail(toggleDetail(a, "food", "clean"), "food", "taste");
    expect(priorityLines(a, ko)).toEqual(["1. 이동 — 택시 → 대중교통 → 도보 → 렌트카", "2. 음식 — 청결 → 맛"]);
    expect(priorityLines(a, translator("en"))[0]).toBe("1. Getting around — Taxi → Public transit → Walking → Rental car");
  });

  it("the finished-survey cards word every answer, keep `상관없음` as an answer, and say `응답하지 않음` only for skipped questions", () => {
    const lines = (a: Answers) => questions.map((question) => answerLines(question.id, a, ko));
    // `full` picked family after typing an "other" draft: the draft is not shown. `[2026-10-20]` The size follows the companions.
    expect(lines(full)).toEqual([["가족 · 3명"], ["1. 음식 — 청결 → 맛", "2. 이동 — 택시"], ["식당 · 실내", "액티비티 · 상관없음"], ["여유롭게"]]);
    expect(lines(skip(skip(full, 0), 2))).toEqual([["응답하지 않음"], ["1. 음식 — 청결 → 맛", "2. 이동 — 택시"], ["응답하지 않음"], ["여유롭게"]]);
    const none = questions.reduce((a, _, index) => skip(a, index), initialAnswers);
    expect(lines(none)).toEqual(questions.map(() => ["응답하지 않음"]));
    expect(answerLines("indoor", full, translator("en"))).toEqual(["Dining · Indoors", "Activities · Either is fine"]);
  });

  it("the finished-survey cards show every area and every detail picked, in picking order, with a long typed companion in full", () => {
    let a: Answers = { ...full, party: "other", partyOther: "  대학 동기 여섯 명과 그 가족들, 그리고 반려견 두 마리  ", priority: [], details: { food: [], activity: [], mobility: [] } };
    for (const area of ["activity", "food", "mobility"] as const) a = toggleArea(a, area);
    for (const value of ["SH", "EV", "HS"]) a = toggleDetail(a, "activity", value);
    for (const value of ["kindness", "taste", "clean"]) a = toggleDetail(a, "food", value);
    for (const value of ["walk", "car", "taxi", "public"]) a = toggleDetail(a, "mobility", value);
    expect(answerLines("party", a, ko)).toEqual(["대학 동기 여섯 명과 그 가족들, 그리고 반려견 두 마리 · 3명"]);
    expect(answerLines("priority", a, ko)).toEqual([
      "1. 활동 — 쇼핑 → 축제/공연/행사 → 역사관광", "2. 음식 — 친절 → 맛 → 청결", "3. 이동 — 도보 → 렌트카 → 택시 → 대중교통",
    ]);
  });
});

describe("discord webhook rule (alerts & recovery card) — the server's `parse_webhook`", () => {
  const id = "123456789012345678";
  const token = "AbC-def_123456789012345";

  it("treats blank and spaces-only as not entered", () => {
    expect(discordWebhookProblem("")).toBeUndefined();
    expect(discordWebhookProblem("   ")).toBeUndefined();
  });

  it("trims only the ends and accepts Discord's webhook URLs on each Discord host", () => {
    for (const host of ["discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com", "ptb.discordapp.com", "canary.discordapp.com"]) {
      expect(discordWebhookProblem(`https://${host}/api/webhooks/${id}/${token}`), host).toBeUndefined();
    }
    expect(discordWebhookProblem(` https://discord.com/api/webhooks/${id}/${token} `)).toBeUndefined();
    expect(discordWebhookProblem(`https://discord.com/api/webhooks/${"1".repeat(15)}/${"a".repeat(20)}`)).toBeUndefined();
    expect(discordWebhookProblem(`https://discord.com/api/webhooks/${"1".repeat(25)}/${"a".repeat(120)}`)).toBeUndefined();
  });

  it("rejects what the server refuses: other schemes, hosts, ports, versions, slashes, queries, and ids or tokens out of range", () => {
    for (const url of [
      "discord.com/api/web" + "hooks/1/x", `http://discord.com/api/webhooks/${id}/${token}`, `https://discord.com:443/api/webhooks/${id}/${token}`,
      `https://evil.com/api/webhooks/${id}/${token}`, `https://discord.com.evil.com/api/webhooks/${id}/${token}`, `https://xdiscord.com/api/webhooks/${id}/${token}`,
      `https://user@discord.com/api/webhooks/${id}/${token}`, `https://discord.com./api/webhooks/${id}/${token}`,
      `https://canary.discord.com/api/v10/webhooks/${id}/${token}`, `https://discord.com/api/webhooks/${id}/${token}/`,
      `https://discord.com/api/webhooks/${id}/${token}?thread_id=1`, `https://discord.com/api/webhooks/${id}/${token}#x`,
      `https://discord.com/api/webhooks/${id}`, `https://discord.com/api/webhooks/abc/${token}`, `https://discord.com/channels/${id}/${id}`,
      `https://discord.com/api/webhooks/${id}/${token}/extra`, `https://discord.com/api/webhooks/${id}/to ken`, `https://discord.com/api/webhooks/${id}/${token}%41`,
      `https://discord.com/api/webhooks/${"1".repeat(14)}/${token}`, `https://discord.com/api/webhooks/${"1".repeat(26)}/${token}`,
      `https://discord.com/api/webhooks/${id}/${"a".repeat(19)}`, `https://discord.com/api/webhooks/${id}/${"a".repeat(121)}`,
      "name@example.com",
    ]) {
      expect(discordWebhookProblem(url), url).toBe("format");
    }
  });
});
