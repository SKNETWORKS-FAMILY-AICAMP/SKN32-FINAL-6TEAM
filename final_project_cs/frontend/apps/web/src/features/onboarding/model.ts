import type { Translate } from "@/lib/i18n";

/** Onboarding answers. They stay in the page state only (see the terms copy). */
export interface Answers {
  themes: string[];
  companions: string[];
  adults: number;
  children: number;
  infants: number;
  allergies: string[];
  diet: string[];
  foodReligion: string[];
  foodNone: boolean;
  foodSkip: boolean;
  transport: string[];
  budget: string;
  budgetCustom: string;
  citizen: string;
  priority: string;
  detailFood: string;
  detailActivity: string;
  detailTransport: string;
  religion: string;
}

export const initialAnswers: Answers = {
  themes: [], companions: [], adults: 1, children: 0, infants: 0, allergies: [], diet: [], foodReligion: [],
  foodNone: false, foodSkip: false, transport: [], budget: "", budgetCustom: "", citizen: "", priority: "",
  detailFood: "", detailActivity: "", detailTransport: "", religion: "",
};

export type Option = readonly [value: string, ko: string, en: string];
export type ListKey = "themes" | "companions" | "allergies" | "diet" | "foodReligion" | "transport";
export type ChoiceKey = "budget" | "citizen" | "priority" | "detailFood" | "detailActivity" | "detailTransport" | "religion";
export type CountKey = "adults" | "children" | "infants";

export const options: Record<ListKey | ChoiceKey, readonly Option[]> = {
  themes: [["food", "맛집 탐방", "Food discoveries"], ["nature", "자연과 힐링", "Nature & rest"], ["culture", "문화와 역사", "Culture & history"], ["activity", "액티비티", "Adventure"], ["shopping", "쇼핑", "Shopping"], ["local", "로컬 일상", "Local life"]],
  companions: [["alone", "혼자", "Solo"], ["partner", "연인", "Partner"], ["friends", "친구", "Friends"], ["family", "가족", "Family"], ["other", "기타", "Other"]],
  allergies: [["nuts", "견과류", "Nuts"], ["shellfish", "갑각류", "Shellfish"], ["milk", "우유", "Milk"], ["egg", "달걀", "Eggs"], ["wheat", "밀", "Wheat"], ["other", "기타", "Other"]],
  diet: [["vegetarian", "채식", "Vegetarian"], ["vegan", "비건", "Vegan"]],
  foodReligion: [["pork", "돼지고기", "Pork"], ["beef", "소고기", "Beef"], ["alcohol", "술", "Alcohol"], ["other", "기타", "Other"]],
  transport: [["public", "대중교통", "Public transit"], ["walk", "도보", "Walking"], ["car", "렌터카", "Rental car"], ["taxi", "택시", "Taxi"]],
  budget: [["low", "30만 원 이하", "Up to ₩300k"], ["mid", "30–60만 원", "₩300k–600k"], ["high", "60–100만 원", "₩600k–1m"], ["premium", "100만 원 이상", "Over ₩1m"], ["custom", "직접 입력", "Enter an amount"]],
  citizen: [["domestic", "내국인", "Korean national"], ["foreign", "외국인", "Foreign national"]],
  priority: [["food", "음식", "Food"], ["activity", "활동", "Activities"], ["transport", "이동", "Getting around"]],
  detailFood: [["taste", "맛", "Taste"], ["kindness", "친절", "Kindness"], ["clean", "청결", "Cleanliness"]],
  detailActivity: [["extreme", "익스트림", "Extreme"], ["healing", "힐링", "Relaxation"], ["diy", "DIY", "DIY"], ["shopping", "쇼핑", "Shopping"]],
  detailTransport: [["public", "대중교통", "Public transit"], ["walk", "도보", "Walking"], ["car", "차", "Car"]],
  religion: [["none", "없음", "None"], ["christian", "기독교", "Protestant"], ["catholic", "천주교", "Catholic"], ["buddhist", "불교", "Buddhist"], ["muslim", "이슬람교", "Muslim"], ["hindu", "힌두교", "Hindu"], ["other", "기타", "Other"], ["skip", "응답하지 않음", "Prefer not to say"]],
};

export const stepNames = [["여행 테마", "Travel themes"], ["여행자 구성", "Your companions"], ["기피 음식", "Food preferences"], ["선호 이동수단", "Transport"], ["예산", "Budget"], ["내국인 여부", "Nationality"], ["여행 우선순위", "Your priority"], ["세부 우선순위", "The finer details"], ["종교", "Religious considerations"]] as const;

export const questions = [
  ["어떤 여행을 좋아하세요?", "What’s your kind of trip?", "마음에 드는 테마를 모두 골라 주세요.", "Choose all the themes that speak to you."],
  ["누구와 함께 떠나나요?", "Who’s coming along?", "동행인과 아이를 포함해 알려 주세요.", "Tell us who’s joining, including little ones."],
  ["피하고 싶은 음식이 있나요?", "Any foods to avoid?", "필요한 식사 조건만 선택해 주세요.", "Share only the food preferences you want to."],
  ["어떻게 이동하고 싶나요?", "How will you get around?", "편한 이동수단을 모두 골라 주세요.", "Choose all the ways you enjoy getting around."],
  ["여행 예산은 얼마인가요?", "What’s your travel budget?", "1인 기준 전체 여행 예산이에요.", "Your total trip budget, per person."],
  ["한국 국적이신가요?", "Are you a Korean national?", "여행에 필요한 안내를 맞춰 드릴게요.", "This helps tailor the travel information."],
  ["가장 중요한 것은 무엇인가요?", "What matters most to you?", "여행에서 중요한 한 가지를 골라 주세요.", "Choose the one thing that matters most."],
  ["어떤 점을 더 중요하게 보나요?", "It’s all in the details.", "음식 · 활동 · 이동에서 각각 하나씩 골라 주세요.", "Choose one preference in each category."],
  ["종교적 고려가 필요한가요?", "Any religious considerations?", "여행에 반영하고 싶을 때만 알려 주세요.", "Share only if you’d like this considered."],
] as const;

export const FOOD_STEP = 2;
export const LAST_STEP = questions.length - 1;
export const isOptional = (index: number) => index === FOOD_STEP || index === LAST_STEP;

export function valid(index: number, a: Answers): boolean {
  switch (index) {
    case 0: return a.themes.length > 0;
    case 1: return a.companions.length > 0 && a.adults >= 1 && (a.companions.includes("alone") ? a.adults === 1 && a.children === 0 && a.infants === 0 : a.adults + a.children + a.infants >= 2);
    case 2: return true;
    case 3: return a.transport.length > 0;
    case 4: return Boolean(a.budget) && (a.budget !== "custom" || (Number.isFinite(Number(a.budgetCustom)) && Number(a.budgetCustom) > 0));
    case 5: return Boolean(a.citizen);
    case 6: return Boolean(a.priority);
    case 7: return Boolean(a.detailFood && a.detailActivity && a.detailTransport);
    case 8: return true;
    default: return false;
  }
}

export function validationHint(index: number, a: Answers, t: Translate): string {
  if (index === 1 && a.companions.length && !a.companions.includes("alone") && a.adults + a.children + a.infants < 2) return t("동행하는 여행은 총인원을 2명 이상으로 설정해 주세요.", "Set at least two travelers when traveling with others.");
  return "";
}

export function answeredCount(a: Answers): number {
  return questions.filter((_, index) => {
    if (index === FOOD_STEP) return a.foodNone || a.allergies.length || a.diet.length || a.foodReligion.length;
    if (index === LAST_STEP) return Boolean(a.religion);
    return valid(index, a);
  }).length;
}

export function chosenLabel(key: ListKey | ChoiceKey, value: string, t: Translate) {
  const option = options[key].find((item) => item[0] === value);
  return option ? t(option[1], option[2]) : t("미선택", "Not selected");
}

/** Toggle a chip the way the mockup does, keeping companions and headcount consistent. */
export function toggle(a: Answers, key: ListKey | ChoiceKey, value: string, multiple: boolean): Answers {
  if (!multiple) {
    const choice = key as ChoiceKey;
    return { ...a, [choice]: a[choice] === value ? "" : value };
  }
  if (key === "companions") {
    if (value === "alone") return { ...a, companions: a.companions.includes("alone") ? [] : ["alone"], adults: 1, children: 0, infants: 0 };
    const others = a.companions.filter((item) => item !== "alone");
    const companions = others.includes(value) ? others.filter((item) => item !== value) : [...others, value];
    const alone = a.adults + a.children + a.infants === 1;
    return { ...a, companions, ...(companions.length && alone ? { adults: 2 } : {}) };
  }
  const list = key as ListKey;
  const next = { ...a, [list]: a[list].includes(value) ? a[list].filter((item) => item !== value) : [...a[list], value] };
  return list === "allergies" || list === "diet" || list === "foodReligion" ? { ...next, foodNone: false, foodSkip: false } : next;
}

export function count(a: Answers, key: CountKey, delta: number): Answers {
  const next = { ...a, [key]: Math.max(key === "adults" ? 1 : 0, Math.min(20, a[key] + delta)) };
  return next.companions.includes("alone") && next.adults + next.children + next.infants > 1 ? { ...next, companions: [] } : next;
}
