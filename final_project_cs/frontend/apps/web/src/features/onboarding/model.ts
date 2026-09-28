import type { Translate } from "@/lib/i18n";

/**
 * Onboarding answers, kept in page state. The trip registration sends them as the
 * backend's `constraints.survey` (see survey.ts); the questions follow wiki D-020.
 */
export interface Answers {
  theme: string;
  party: string;
  transport: string[];
  priority: string;
  detailFood: string;
  detailActivity: string;
  detailTransport: string;
  indoorDining: string;
  indoorActivity: string;
  onDisruption: string;
  pace: string;
  /** Questions skipped without an answer. They still count toward progress. */
  skipped: number[];
}

export const initialAnswers: Answers = {
  theme: "", party: "", transport: [], priority: "", detailFood: "", detailActivity: "", detailTransport: "",
  indoorDining: "", indoorActivity: "", onDisruption: "", pace: "", skipped: [],
};

/** The answer fields each question owns, in question order. */
const questionFields: readonly (readonly (keyof Answers)[])[] = [
  ["theme"], ["party"], ["transport"], ["priority"], ["detailFood", "detailActivity", "detailTransport"],
  ["indoorDining", "indoorActivity"], ["onDisruption"], ["pace"],
];

export type Option = readonly [value: string, ko: string, en: string];
export type ListKey = "transport";
export type ChoiceKey = "theme" | "party" | "priority" | "detailFood" | "detailActivity" | "detailTransport" | "indoorDining" | "indoorActivity" | "onDisruption" | "pace";

const indoorOutdoor: readonly Option[] = [["indoor", "실내", "Indoors"], ["outdoor", "실외", "Outdoors"], ["any", "상관없음", "Either is fine"]];

export const options: Record<ListKey | ChoiceKey, readonly Option[]> = {
  theme: [["food", "맛집 탐방", "Food discoveries"], ["nature", "자연과 힐링", "Nature & rest"], ["culture", "문화와 역사", "Culture & history"], ["activity", "액티비티", "Adventure"], ["shopping", "쇼핑", "Shopping"], ["local", "로컬 일상", "Local life"]],
  party: [["alone", "혼자", "Solo"], ["partner", "연인", "Partner"], ["friends", "친구", "Friends"], ["family", "가족", "Family"], ["other", "기타", "Other"]],
  transport: [["public", "대중교통", "Public transit"], ["walk", "도보", "Walking"], ["car", "렌터카", "Rental car"], ["taxi", "택시", "Taxi"]],
  priority: [["food", "음식", "Food"], ["activity", "활동", "Activities"], ["transport", "이동", "Getting around"]],
  detailFood: [["taste", "맛", "Taste"], ["kindness", "친절", "Kindness"], ["clean", "청결", "Cleanliness"]],
  detailActivity: [["extreme", "익스트림", "Extreme"], ["healing", "힐링", "Relaxation"], ["diy", "DIY", "DIY"], ["shopping", "쇼핑", "Shopping"]],
  detailTransport: [["public", "대중교통", "Public transit"], ["walk", "도보", "Walking"], ["car", "차", "Car"]],
  indoorDining: indoorOutdoor,
  indoorActivity: indoorOutdoor,
  onDisruption: [["replace", "비슷한 곳으로 바꿔줘", "Swap in something similar"], ["ask_first", "먼저 물어봐줘", "Ask me first"]],
  pace: [["relaxed", "여유롭게", "Relaxed"], ["moderate", "적당히", "Balanced"], ["packed", "꽉 차게", "Packed"]],
};

export const stepNames = [["여행 테마", "Travel theme"], ["여행자 구성", "Your companions"], ["선호 이동수단", "Transport"], ["여행 우선순위", "Your priority"], ["세부 우선순위", "The finer details"], ["실내·실외", "Indoors or out"], ["일정 변경 방식", "When plans change"], ["여행 여유", "Your pace"]] as const;

export const questions = [
  ["어떤 여행을 좋아하세요?", "What’s your kind of trip?", "가장 마음에 드는 테마 하나를 골라 주세요.", "Choose the one theme that suits you best."],
  ["누구와 함께 떠나나요?", "Who’s coming along?", "함께 떠나는 사람을 하나 골라 주세요.", "Choose who you’re traveling with."],
  ["어떻게 이동하고 싶나요?", "How will you get around?", "편한 이동수단을 모두 골라 주세요.", "Choose all the ways you enjoy getting around."],
  ["가장 중요한 것은 무엇인가요?", "What matters most to you?", "여행에서 중요한 한 가지를 골라 주세요.", "Choose the one thing that matters most."],
  ["어떤 점을 더 중요하게 보나요?", "It’s all in the details.", "음식 · 활동 · 이동에서 각각 하나씩 골라 주세요.", "Choose one preference in each category."],
  ["실내와 실외 중 어디가 좋으세요?", "Indoors or outdoors?", "식당과 액티비티에서 각각 하나씩 골라 주세요.", "Choose one for dining and one for activities."],
  ["갑자기 일정이 꼬이면 어떻게 했으면 좋겠어요?", "If plans suddenly go wrong, what should we do?", "일정을 바꿔야 하는 일이 생겼을 때의 방식을 정해요.", "Choose how we handle it when something forces a change."],
  ["여행할 때 어느 정도 여유가 좋으세요?", "How much breathing room do you like?", "하루에 담을 일정의 양을 정할 때 쓰여요.", "We use this to decide how much to fit into each day."],
] as const;

/** The survey explanation card, shown before the first question. */
export const INTRO_STEP = -1;
export const LAST_STEP = questions.length - 1;

export function valid(index: number, a: Answers): boolean {
  switch (index) {
    case 0: return Boolean(a.theme);
    case 1: return Boolean(a.party);
    case 2: return a.transport.length > 0;
    case 3: return Boolean(a.priority);
    case 4: return Boolean(a.detailFood && a.detailActivity && a.detailTransport);
    case 5: return Boolean(a.indoorDining && a.indoorActivity);
    case 6: return Boolean(a.onDisruption);
    case 7: return Boolean(a.pace);
    default: return false;
  }
}

/** A question is done once it is answered or skipped. */
export const done = (index: number, a: Answers) => valid(index, a) || a.skipped.includes(index);

export function answeredCount(a: Answers): number {
  return questions.filter((_, index) => done(index, a)).length;
}

/** Clear a question's answer and mark it skipped. */
export function skip(a: Answers, index: number): Answers {
  const cleared = Object.fromEntries(questionFields[index].map((field) => [field, initialAnswers[field]]));
  return { ...a, ...cleared, skipped: a.skipped.includes(index) ? a.skipped : [...a.skipped, index] };
}

/** Answering a skipped question takes the skip back. */
export const unskip = (a: Answers, index: number): Answers => ({ ...a, skipped: a.skipped.filter((item) => item !== index) });

export function chosenLabel(key: ListKey | ChoiceKey, value: string, t: Translate) {
  const option = options[key].find((item) => item[0] === value);
  return option ? t(option[1], option[2]) : t("미선택", "Not selected");
}

/** Tap a chip: a single choice toggles on and off, a list adds or removes the value. */
export function toggle(a: Answers, key: ListKey | ChoiceKey, value: string, multiple: boolean): Answers {
  if (!multiple) {
    const choice = key as ChoiceKey;
    return { ...a, [choice]: a[choice] === value ? "" : value };
  }
  const list = key as ListKey;
  return { ...a, [list]: a[list].includes(value) ? a[list].filter((item) => item !== value) : [...a[list], value] };
}
