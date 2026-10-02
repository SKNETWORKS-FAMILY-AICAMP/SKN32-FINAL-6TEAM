import type { Translate } from "@/lib/i18n";

/** Areas of the priority question — the backend survey's `Area` (`food` · `activity` · `mobility`). */
export type Area = "food" | "activity" | "mobility";
/** The areas' fixed order on screen; the picking order is shown as numbers, never by moving the cards. */
export const areas: readonly Area[] = ["food", "activity", "mobility"];

/**
 * Onboarding answers, kept in page state. The trip registration sends them as the
 * backend's `constraints.survey` (see payload.ts); the questions follow wiki D-020.
 */
export interface Answers {
  theme: string;
  party: string;
  /** Typed for `party: other`. Kept while another choice is picked, so choosing `other` again brings it back; sent only with `other`. */
  partyOther: string;
  /** Areas in the order they were picked: the order is the ranking. */
  priority: Area[];
  /** Each area's details in the order they were picked, ranked the same way and kept per area. */
  details: Record<Area, string[]>;
  indoorDining: string;
  indoorActivity: string;
  onDisruption: string;
  pace: string;
  /** Questions (by position) skipped without an answer. They still count toward progress. */
  skipped: number[];
}

export const initialAnswers: Answers = {
  theme: "", party: "", partyOther: "", priority: [], details: { food: [], activity: [], mobility: [] },
  indoorDining: "", indoorActivity: "", onDisruption: "", pace: "", skipped: [],
};

export type Option = readonly [value: string, ko: string, en: string];
export type ChoiceKey = "theme" | "party" | "indoorDining" | "indoorActivity" | "onDisruption" | "pace";

const indoorOutdoor: readonly Option[] = [["indoor", "실내", "Indoors"], ["outdoor", "실외", "Outdoors"], ["any", "상관없음", "Either is fine"]];

export const options: Record<ChoiceKey, readonly Option[]> = {
  theme: [["food", "맛집 탐방", "Food discoveries"], ["nature", "자연과 힐링", "Nature & rest"], ["culture", "문화와 역사", "Culture & history"], ["activity", "액티비티", "Adventure"], ["shopping", "쇼핑", "Shopping"], ["local", "로컬 일상", "Local life"]],
  party: [["alone", "혼자", "Solo"], ["partner", "연인", "Partner"], ["friends", "친구", "Friends"], ["family", "가족", "Family"], ["other", "기타", "Other"]],
  indoorDining: indoorOutdoor,
  indoorActivity: indoorOutdoor,
  onDisruption: [["replace", "비슷한 곳으로 바꿔줘", "Swap in something similar"], ["ask_first", "먼저 물어봐줘", "Ask me first"]],
  pace: [["relaxed", "여유롭게", "Relaxed"], ["moderate", "적당히", "Balanced"], ["packed", "꽉 차게", "Packed"]],
};

export const areaNames: Record<Area, readonly [ko: string, en: string]> = { food: ["음식", "Food"], activity: ["활동", "Activities"], mobility: ["이동", "Getting around"] };

/** Details per area. Mobility keeps its codes: `car` is now shown as a rental car, and taxi is added. */
export const detailOptions: Record<Area, readonly Option[]> = {
  food: [["taste", "맛", "Taste"], ["kindness", "친절", "Kindness"], ["clean", "청결", "Cleanliness"]],
  activity: [["extreme", "익스트림", "Extreme"], ["healing", "힐링", "Relaxation"], ["diy", "DIY", "DIY"], ["shopping", "쇼핑", "Shopping"]],
  mobility: [["public", "대중교통", "Public transit"], ["walk", "도보", "Walking"], ["car", "렌트카", "Rental car"], ["taxi", "택시", "Taxi"]],
};

export type QuestionId = "theme" | "party" | "priority" | "indoor" | "onDisruption" | "pace";
type Pair = readonly [ko: string, en: string];

interface Question {
  id: QuestionId;
  /** Short name in the card head. */
  name: Pair;
  title: Pair;
  helper: Pair;
  /** The answer fields this question owns: skipping resets exactly these. */
  fields: readonly (keyof Answers)[];
  answered: (a: Answers) => boolean;
}

/**
 * The six questions, in order. Everything about a question — its fields, its check and its text — is in its one
 * entry, and the survey is built by `id`, so no position is shared by two questions. Nationality is not asked
 * (nothing uses it; the backend's `domestic` stays optional).
 */
export const questions: readonly Question[] = [
  {
    id: "theme", name: ["여행 테마", "Travel theme"], fields: ["theme"], answered: (a) => Boolean(a.theme),
    title: ["어떤 여행을 좋아하세요?", "What’s your kind of trip?"], helper: ["가장 마음에 드는 테마 하나를 골라 주세요.", "Choose the one theme that suits you best."],
  },
  {
    id: "party", name: ["여행자 구성", "Your companions"], fields: ["party", "partyOther"],
    answered: (a) => Boolean(a.party) && (a.party !== "other" || Boolean(a.partyOther.trim())),
    title: ["누구와 함께 떠나나요?", "Who’s coming along?"], helper: ["함께 떠나는 사람을 하나 골라 주세요.", "Choose who you’re traveling with."],
  },
  {
    id: "priority", name: ["여행 우선순위", "Your priorities"], fields: ["priority", "details"],
    // At least one area, and at least one detail in every area picked. Areas left out need nothing.
    answered: (a) => a.priority.length > 0 && a.priority.every((area) => a.details[area].length > 0),
    title: ["어떤 것을 더 중요하게 생각하나요?", "What matters more to you?"], helper: ["중요한 순서대로 분야와 세부 항목을 선택해 주세요.", "Pick areas and details in order of importance."],
  },
  {
    id: "indoor", name: ["실내·실외", "Indoors or out"], fields: ["indoorDining", "indoorActivity"], answered: (a) => Boolean(a.indoorDining && a.indoorActivity),
    title: ["실내와 실외 중 어디가 좋으세요?", "Indoors or outdoors?"], helper: ["식당과 액티비티에서 각각 하나씩 골라 주세요.", "Choose one for dining and one for activities."],
  },
  {
    id: "onDisruption", name: ["일정 변경 방식", "When plans change"], fields: ["onDisruption"], answered: (a) => Boolean(a.onDisruption),
    title: ["갑자기 일정이 꼬이면 어떻게 했으면 좋겠어요?", "If plans suddenly go wrong, what should we do?"], helper: ["일정을 바꿔야 하는 일이 생겼을 때의 방식을 정해요.", "Choose how we handle it when something forces a change."],
  },
  {
    id: "pace", name: ["여행 여유", "Your pace"], fields: ["pace"], answered: (a) => Boolean(a.pace),
    title: ["여행할 때 어느 정도 여유가 좋으세요?", "How much breathing room do you like?"], helper: ["하루에 담을 일정의 양을 정할 때 쓰여요.", "We use this to decide how much to fit into each day."],
  },
];

/** The survey explanation card, shown before the first question. */
export const INTRO_STEP = -1;
export const LAST_STEP = questions.length - 1;

export const valid = (index: number, a: Answers): boolean => questions[index]?.answered(a) ?? false;

/** Answered, looked up by name rather than position. */
export const isAnswered = (id: QuestionId, a: Answers): boolean => questions.some((question) => question.id === id && question.answered(a));

/** A question is done once it is answered or skipped. */
export const done = (index: number, a: Answers) => valid(index, a) || a.skipped.includes(index);

export function answeredCount(a: Answers): number {
  return questions.filter((_, index) => done(index, a)).length;
}

/** Clear a question's answer — its own fields only — and mark it skipped. */
export function skip(a: Answers, index: number): Answers {
  const cleared = Object.fromEntries(questions[index].fields.map((field) => [field, initialAnswers[field]]));
  return { ...a, ...cleared, skipped: a.skipped.includes(index) ? a.skipped : [...a.skipped, index] };
}

/** Answering a skipped question takes the skip back. */
export const unskip = (a: Answers, index: number): Answers => ({ ...a, skipped: a.skipped.filter((item) => item !== index) });

export function chosenLabel(key: ChoiceKey, value: string, t: Translate) {
  const option = options[key].find((item) => item[0] === value);
  return option ? t(option[1], option[2]) : t("미선택", "Not selected");
}

/** Companions in words: what was typed for `other`, otherwise the choice. */
export const partyLabel = (a: Answers, t: Translate) => a.party === "other" && a.partyOther.trim() ? a.partyOther.trim() : chosenLabel("party", a.party, t);

/** Priorities in picking order, one line per area: "1. 음식 — 청결 → 맛". */
export function priorityLines(a: Answers, t: Translate): string[] {
  const detail = (area: Area, value: string) => {
    const option = detailOptions[area].find((item) => item[0] === value);
    return option ? t(option[1], option[2]) : value;
  };
  return a.priority.map((area, index) => `${index + 1}. ${t(...areaNames[area])} — ${a.details[area].map((value) => detail(area, value)).join(" → ")}`);
}

/**
 * One question's answer in words for the finished-survey cards, one string per line. A skipped question says so
 * instead of showing a choice; `상관없음` is a real answer and shows as picked.
 */
export function answerLines(id: QuestionId, a: Answers, t: Translate): string[] {
  if (a.skipped.includes(questions.findIndex((question) => question.id === id))) return [t("응답하지 않음", "Not answered")];
  switch (id) {
    case "theme": return [chosenLabel("theme", a.theme, t)];
    case "party": return [partyLabel(a, t)];
    case "priority": return a.priority.length ? priorityLines(a, t) : [t("미선택", "Not selected")];
    case "indoor": return [`${t("식당", "Dining")} · ${chosenLabel("indoorDining", a.indoorDining, t)}`, `${t("액티비티", "Activities")} · ${chosenLabel("indoorActivity", a.indoorActivity, t)}`];
    case "onDisruption": return [chosenLabel("onDisruption", a.onDisruption, t)];
    case "pace": return [chosenLabel("pace", a.pace, t)];
  }
}

/** Tap a single-choice chip: it toggles on and off. */
export function toggle(a: Answers, key: ChoiceKey, value: string): Answers {
  return { ...a, [key]: a[key] === value ? "" : value };
}

/** Tap an area: picked areas rank in tapping order. Un-picking drops the area and its details; the ones behind move up. */
export function toggleArea(a: Answers, area: Area): Answers {
  if (!a.priority.includes(area)) return { ...a, priority: [...a.priority, area] };
  return { ...a, priority: a.priority.filter((item) => item !== area), details: { ...a.details, [area]: [] } };
}

/** Tap a detail: the same ranking, kept per area. The area's own pick is not touched. */
export function toggleDetail(a: Answers, area: Area, value: string): Answers {
  const picked = a.details[area];
  return { ...a, details: { ...a.details, [area]: picked.includes(value) ? picked.filter((item) => item !== value) : [...picked, value] } };
}

/**
 * The server's webhook rule (`customer_profile.parse_webhook`, `PUT /v1/web/profile`): https, a Discord host (discord.com
 * or discordapp.com, or their canary./ptb. builds), then exactly `/api/webhooks/<15–25 digit id>/<20–120 char token>` —
 * no port, version, trailing slash, query or fragment. Lower case only: Discord's copied URLs are, and being stricter
 * than the server never lets through a value it would refuse.
 */
const DISCORD_WEBHOOK = /^https:\/\/(?:(?:canary|ptb)\.)?discord(?:app)?\.com\/api\/webhooks\/\d{15,25}\/[A-Za-z0-9_-]{20,120}$/;

/**
 * The optional Discord webhook on the alerts & recovery card. Only the ends are trimmed: blank (or spaces only) means
 * "not entered", anything else must pass the server's rule above. It does not tell whether the webhook exists.
 */
export function discordWebhookProblem(url: string): "format" | undefined {
  const value = url.trim();
  return value && !DISCORD_WEBHOOK.test(value) ? "format" : undefined;
}
