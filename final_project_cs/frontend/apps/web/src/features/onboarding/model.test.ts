import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import {
  answeredCount, answerLines, discordWebhookProblem, done, initialAnswers, partyLabel, priorityLines, questions, skip, toggle, toggleArea, toggleDetail, unskip, valid, type Answers,
} from "./model";

const ko = translator("ko");
/** Every question answered, with a picked "other" draft kept aside. */
const full: Answers = {
  ...initialAnswers, theme: "food", party: "family", partyOther: "직장 동료", priority: ["food", "mobility"],
  details: { food: ["clean", "taste"], activity: [], mobility: ["taxi"] }, indoorDining: "indoor", indoorActivity: "any", onDisruption: "ask_first", pace: "relaxed",
};

describe("onboarding preferences", () => {
  it("asks six questions in order, without the separate transport or nationality question", () => {
    expect(questions.map((question) => question.id)).toEqual(["theme", "party", "priority", "indoor", "onDisruption", "pace"]);
    expect(questions.map((question) => question.title[0])).not.toContain("어떻게 이동하고 싶나요?");
    expect(questions.map((question) => question.title[0])).not.toContain("한국 국적이신가요?");
    expect(questions[2].title[0]).toBe("어떤 것을 더 중요하게 생각하나요?");
    expect(questions[2].helper[0]).toBe("중요한 순서대로 분야와 세부 항목을 선택해 주세요.");
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
    expect(answeredCount(unskip(skip(initialAnswers, 4), 4))).toBe(0);
  });

  it("companions: `other` needs typed words (not spaces); another choice hides it but keeps the draft; skipping clears both", () => {
    const other = toggle(initialAnswers, "party", "other");
    expect(valid(1, other)).toBe(false);
    expect(valid(1, { ...other, partyOther: "   " })).toBe(false);
    const typed = { ...other, partyOther: "  직장 동료 " };
    expect(valid(1, typed)).toBe(true);
    expect(partyLabel(typed, ko)).toBe("직장 동료");
    const family = toggle(typed, "party", "family");
    expect(valid(1, family)).toBe(true);
    expect(partyLabel(family, ko)).toBe("가족");
    expect(toggle(family, "party", "other").partyOther).toBe("  직장 동료 ");
    expect(skip(typed, 1)).toMatchObject({ party: "", partyOther: "" });
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
    a = toggleDetail(a, "activity", "diy");
    expect(a.details.food).toEqual(["taste", "kindness", "clean"]);
    a = toggleDetail(a, "food", "taste");
    expect(a.details.food).toEqual(["kindness", "clean"]);
    expect(toggleDetail(a, "food", "taste").details.food).toEqual(["kindness", "clean", "taste"]);
    expect(a.details.activity).toEqual(["diy"]);
    expect(a.priority).toEqual(["food", "activity"]);
  });

  it("priorities are answered with at least one area and at least one detail in every picked area", () => {
    const food = toggleArea(initialAnswers, "food");
    expect(valid(2, initialAnswers)).toBe(false);
    expect(valid(2, food)).toBe(false);
    expect(valid(2, toggleDetail(food, "food", "taste"))).toBe(true);
    const both = toggleArea(toggleDetail(food, "food", "taste"), "mobility");
    expect(valid(2, both)).toBe(false);
    expect(valid(2, toggleDetail(both, "mobility", "car"))).toBe(true);
    expect(skip(both, 2)).toMatchObject({ priority: [], details: { food: [], activity: [], mobility: [] } });
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
    // `full` picked family after typing an "other" draft: the draft is not shown.
    expect(lines(full)).toEqual([["맛집 탐방"], ["가족"], ["1. 음식 — 청결 → 맛", "2. 이동 — 택시"], ["식당 · 실내", "액티비티 · 상관없음"], ["먼저 물어봐줘"], ["여유롭게"]]);
    expect(lines(skip(skip(full, 1), 3))).toEqual([["맛집 탐방"], ["응답하지 않음"], ["1. 음식 — 청결 → 맛", "2. 이동 — 택시"], ["응답하지 않음"], ["먼저 물어봐줘"], ["여유롭게"]]);
    const none = questions.reduce((a, _, index) => skip(a, index), initialAnswers);
    expect(lines(none)).toEqual(questions.map(() => ["응답하지 않음"]));
    expect(answerLines("indoor", full, translator("en"))).toEqual(["Dining · Indoors", "Activities · Either is fine"]);
  });

  it("the finished-survey cards show every area and every detail picked, in picking order, with a long typed companion in full", () => {
    let a: Answers = { ...full, party: "other", partyOther: "  대학 동기 여섯 명과 그 가족들, 그리고 반려견 두 마리  ", priority: [], details: { food: [], activity: [], mobility: [] } };
    for (const area of ["activity", "food", "mobility"] as const) a = toggleArea(a, area);
    for (const value of ["shopping", "diy", "healing", "extreme"]) a = toggleDetail(a, "activity", value);
    for (const value of ["kindness", "taste", "clean"]) a = toggleDetail(a, "food", value);
    for (const value of ["walk", "car", "taxi", "public"]) a = toggleDetail(a, "mobility", value);
    expect(answerLines("party", a, ko)).toEqual(["대학 동기 여섯 명과 그 가족들, 그리고 반려견 두 마리"]);
    expect(answerLines("priority", a, ko)).toEqual([
      "1. 활동 — 쇼핑 → DIY → 힐링 → 익스트림", "2. 음식 — 친절 → 맛 → 청결", "3. 이동 — 도보 → 렌트카 → 택시 → 대중교통",
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
      "discord.com/api/webhooks/1/x", `http://discord.com/api/webhooks/${id}/${token}`, `https://discord.com:443/api/webhooks/${id}/${token}`,
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
